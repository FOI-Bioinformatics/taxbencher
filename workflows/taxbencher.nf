/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    IMPORT MODULES / SUBWORKFLOWS / FUNCTIONS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/
include { TAXPASTA_STANDARDISE   } from '../modules/local/taxpasta_standardise/main'
include { TAXPASTA_TO_BIOBOXES   } from '../modules/local/taxpasta_to_bioboxes/main'
include { OPAL                   } from '../modules/local/opal/main'
include { OPAL_PER_SAMPLE        } from '../modules/local/opal_per_sample/main'
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
            log.info "[TAXBENCHER] Sample ${meta.sample_id} | Label ${meta.label} | Classifier ${meta.classifier}: Using pre-standardised profile ${file.name}"
        }

    ch_branched.needs_standardisation
        .subscribe { meta, file ->
            log.info "[TAXBENCHER] Sample ${meta.sample_id} | Label ${meta.label} | Classifier ${meta.classifier}: Standardising raw profiler output ${file.name}"
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
    // Group bioboxes by sample_id for per-sample OPAL evaluation
    // Each biological sample gets its own OPAL run with all its classifiers
    //
    // Step 1: Map to [sample_id, label, bioboxes]
    // Step 2: Group by sample_id using groupTuple
    // Step 3: Combine with gold standard
    // Step 4: Transpose to expand bioboxes list while keeping meta+gold together
    //
    ch_bioboxes_per_sample = TAXPASTA_TO_BIOBOXES.out.bioboxes
        .map { meta, bioboxes ->
            [meta.sample_id, meta.label, bioboxes]
        }
        .groupTuple()  // Groups by sample_id: [sample_id, [labels...], [bioboxes...]]
        .combine(ch_gold_standard)
        .map { sample_id, labels, bioboxes_files, gold_std ->
            // Create meta for this sample_id group
            def meta_grouped = [
                id: sample_id,
                sample_id: sample_id,
                labels: labels.join(','),
                num_classifiers: labels.size()
            ]
            // Return: [meta, gold_standard, [bioboxes_files]]
            tuple(meta_grouped, gold_std, bioboxes_files)
        }

    //
    // MODULE: Run OPAL evaluation per sample_id
    // OPAL_PER_SAMPLE is invoked once per sample_id with that sample's bioboxes files
    //
    // The ch_bioboxes_per_sample channel already contains:
    // [meta_grouped, gold_standard, [bioboxes_files]]
    //
    // This matches OPAL_PER_SAMPLE signature:
    // tuple val(meta), path(gold_standard), path(predictions)
    //
    OPAL_PER_SAMPLE (
        ch_bioboxes_per_sample
    )
    ch_versions = ch_versions.mix(OPAL_PER_SAMPLE.out.versions.first())
    ch_multiqc_files = ch_multiqc_files.mix(OPAL_PER_SAMPLE.out.results.map { meta, dir -> dir })

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
    opal_results   = OPAL_PER_SAMPLE.out.results // channel: [ [meta], path(opal_results/) ]
    multiqc_report = MULTIQC.out.report.toList() // channel: /path/to/multiqc_report.html
    versions       = ch_versions                 // channel: [ path(versions.yml) ]

}

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    THE END
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/
