/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    IMPORT MODULES / SUBWORKFLOWS / FUNCTIONS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/
include { TAXPASTA_STANDARDISE   } from '../modules/local/taxpasta_standardise/main'
include { TAXPASTA_TO_BIOBOXES   } from '../modules/local/taxpasta_to_bioboxes/main'
include { OPAL                   } from '../modules/local/opal/main'
include { MULTIQC                } from '../modules/nf-core/multiqc/main'
include { paramsSummaryMap       } from 'plugin/nf-schema'
include { paramsSummaryMultiqc   } from '../subworkflows/nf-core/utils_nfcore_pipeline'
include { softwareVersionsToYAML } from '../subworkflows/nf-core/utils_nfcore_pipeline'
include { methodsDescriptionText } from '../subworkflows/local/utils_nfcore_taxbencher_pipeline'

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    RUN MAIN WORKFLOW
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

workflow TAXBENCHER {

    take:
    ch_input         // channel: [ [meta], path(input_file) ] - Can be taxpasta TSV or raw profiler output
    ch_gold_standard // channel: path(gold_standard.bioboxes)

    main:

    ch_versions = Channel.empty()
    ch_multiqc_files = Channel.empty()

    //
    // BRANCH: Separate inputs that need standardization from those that don't
    // Check file extension to determine if taxpasta standardisation is needed
    // .tsv or .txt files are already standardized, others need processing
    //
    ch_input
        .branch { meta, file ->
            standardised: file.name.endsWith('.tsv') || file.name.endsWith('.txt')
                return [meta, file]
            needs_standardisation: true
                return [meta, file]
        }
        .set { ch_branched }

    //
    // Log format detection for user visibility
    //
    ch_branched.standardised
        .subscribe { meta, file ->
            log.info "[TAXBENCHER] Sample ${meta.id} (${meta.classifier}): Using pre-standardised profile ${file.name}"
        }

    ch_branched.needs_standardisation
        .subscribe { meta, file ->
            log.info "[TAXBENCHER] Sample ${meta.id} (${meta.classifier}): Standardising raw profiler output ${file.name}"
        }

    //
    // MODULE: Standardise raw profiler outputs (optional)
    // Only runs for files that are not already in taxpasta TSV format
    //
    TAXPASTA_STANDARDISE(ch_branched.needs_standardisation)
    ch_versions = ch_versions.mix(TAXPASTA_STANDARDISE.out.versions.first())

    //
    // CHANNEL: Combine standardised and already-standardised files
    // This creates a unified channel of taxpasta TSV files for downstream processing
    //
    ch_taxpasta = ch_branched.standardised
        .mix(TAXPASTA_STANDARDISE.out.standardised)

    //
    // MODULE: Convert taxpasta profiles to CAMI Bioboxes format
    //
    TAXPASTA_TO_BIOBOXES (
        ch_taxpasta
    )
    ch_versions = ch_versions.mix(TAXPASTA_TO_BIOBOXES.out.versions.first())

    //
    // Collect all converted bioboxes files for batch OPAL evaluation
    // Extract just the file paths and collect them into a list
    //
    ch_bioboxes_collected = TAXPASTA_TO_BIOBOXES.out.bioboxes
        .map { meta, bioboxes -> bioboxes }
        .collect()

    //
    // Collect labels from metadata for OPAL predictions
    // Labels help OPAL distinguish between different classifiers/samples
    //
    ch_bioboxes_labels = TAXPASTA_TO_BIOBOXES.out.bioboxes
        .map { meta, bioboxes -> meta.id }
        .collect()
        .map { labels -> labels.join(',') }

    //
    // Create meta map for gold standard with labels
    // Combine the labels channel with the gold standard file
    //
    ch_gold_with_meta = ch_bioboxes_labels
        .combine(ch_gold_standard)
        .map { labels, gold_std -> [
            [
                id: 'benchmark',
                labels: labels
            ],
            gold_std
        ] }

    //
    // MODULE: Run OPAL evaluation against gold standard
    //
    OPAL (
        ch_gold_with_meta,
        ch_bioboxes_collected
    )
    ch_versions = ch_versions.mix(OPAL.out.versions)
    ch_multiqc_files = ch_multiqc_files.mix(OPAL.out.results.map { meta, dir -> dir })

    //
    // Collate and save software versions
    //
    softwareVersionsToYAML(ch_versions)
        .collectFile(
            storeDir: "${params.outdir}/pipeline_info",
            name:  'taxbencher_software_'  + 'mqc_'  + 'versions.yml',
            sort: true,
            newLine: true
        ).set { ch_collated_versions }


    //
    // MODULE: MultiQC
    //
    ch_multiqc_config        = Channel.fromPath(
        "$projectDir/assets/multiqc_config.yml", checkIfExists: true)
    ch_multiqc_custom_config = params.multiqc_config ?
        Channel.fromPath(params.multiqc_config, checkIfExists: true) :
        Channel.empty()
    ch_multiqc_logo          = params.multiqc_logo ?
        Channel.fromPath(params.multiqc_logo, checkIfExists: true) :
        Channel.empty()

    summary_params      = paramsSummaryMap(
        workflow, parameters_schema: "nextflow_schema.json")
    ch_workflow_summary = Channel.value(paramsSummaryMultiqc(summary_params))
    ch_multiqc_files = ch_multiqc_files.mix(
        ch_workflow_summary.collectFile(name: 'workflow_summary_mqc.yaml'))
    ch_multiqc_custom_methods_description = params.multiqc_methods_description ?
        file(params.multiqc_methods_description, checkIfExists: true) :
        file("$projectDir/assets/methods_description_template.yml", checkIfExists: true)
    ch_methods_description                = Channel.value(
        methodsDescriptionText(ch_multiqc_custom_methods_description))

    ch_multiqc_files = ch_multiqc_files.mix(ch_collated_versions)
    ch_multiqc_files = ch_multiqc_files.mix(
        ch_methods_description.collectFile(
            name: 'methods_description_mqc.yaml',
            sort: true
        )
    )

    MULTIQC (
        ch_multiqc_files.collect(),
        ch_multiqc_config.toList(),
        ch_multiqc_custom_config.toList(),
        ch_multiqc_logo.toList(),
        [],
        []
    )

    emit:
    opal_results   = OPAL.out.results            // channel: [ [meta], path(opal_results/) ]
    multiqc_report = MULTIQC.out.report.toList() // channel: /path/to/multiqc_report.html
    versions       = ch_versions                 // channel: [ path(versions.yml) ]

}

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    THE END
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/
