/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    IMPORT MODULES / SUBWORKFLOWS / FUNCTIONS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/
include { ETE3_BUILD_TAXDB       } from '../modules/local/ete3_build_taxdb/main'
include { TAXPASTA_STANDARDISE   } from '../modules/local/taxpasta_standardise/main'
include { TAXPASTA_TO_BIOBOXES   } from '../modules/local/taxpasta_to_bioboxes/main'
include { OPAL_PER_SAMPLE        } from '../modules/local/opal_per_sample/main'
include { COMPARATIVE_ANALYSIS   } from '../modules/local/comparative_analysis/main'
include { MULTIQC                } from '../modules/nf-core/multiqc/main'
include { paramsSummaryMap       } from 'plugin/nf-schema'
include { paramsSummaryMultiqc   } from '../subworkflows/nf-core/utils_nfcore_pipeline'
include { softwareVersionsToYAML } from '../subworkflows/nf-core/utils_nfcore_pipeline'
include { methodsDescriptionText } from '../subworkflows/local/utils_nfcore_taxbencher_pipeline'

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    FUNCTIONS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

//
// Decide whether an input file is already a taxpasta standardised profile.
// A .tsv/.txt file whose header row contains the 'taxonomy_id' and 'count' columns is
// considered standardised; anything else is sent through taxpasta (DIAMOND and MEGAN6
// raw outputs are also tab separated text files, so the extension alone is not enough).
// Remote files are judged by extension only.
//
def isStandardisedProfile(input_file) {
    def name = input_file.name.toLowerCase()
    if (!(name.endsWith('.tsv') || name.endsWith('.txt'))) {
        return false
    }
    if (input_file.toString() ==~ /^[a-zA-Z][a-zA-Z0-9+.-]*:\/\/.*/ ) {
        return true
    }
    def header = null
    try {
        input_file.withReader { reader -> header = reader.readLine() }
    } catch (Exception e) {
        log.warn "[TAXBENCHER] Could not read header of ${input_file}: ${e.message}; assuming taxpasta format"
        return true
    }
    if (header == null) {
        return true
    }
    def columns = header.split('\t').collect { it.trim().toLowerCase() }
    return columns.contains('taxonomy_id') && columns.contains('count')
}

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    RUN MAIN WORKFLOW
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

workflow TAXBENCHER {

    take:
    ch_input         // channel: [ [meta], path(input_file) ] - Can be taxpasta TSV or raw profiler output
    ch_gold_standard // channel: path(gold_standard.bioboxes) (value channel)
    ch_taxdump       // channel: path(taxdump.tar.gz) (value channel) or empty

    main:

    ch_versions = Channel.empty()
    ch_multiqc_files = Channel.empty()

    //
    // BRANCH: Separate inputs that need standardisation from those that don't
    //
    ch_input
        .branch { meta, input_file ->
            standardised: isStandardisedProfile(input_file)
                return [meta, input_file]
            needs_standardisation: true
                return [meta, input_file]
        }
        .set { ch_branched }

    ch_branched.standardised
        .subscribe { meta, input_file ->
            log.info "[TAXBENCHER] Sample ${meta.sample_id} | Label ${meta.label} | Classifier ${meta.classifier}: Using pre-standardised profile ${input_file.name}"
        }

    ch_branched.needs_standardisation
        .subscribe { meta, input_file ->
            log.info "[TAXBENCHER] Sample ${meta.sample_id} | Label ${meta.label} | Classifier ${meta.classifier}: Standardising raw profiler output ${input_file.name}"
        }

    //
    // MODULE: Standardise raw profiler outputs (only for files not already in taxpasta format)
    //
    TAXPASTA_STANDARDISE(ch_branched.needs_standardisation)
    ch_versions = ch_versions.mix(TAXPASTA_STANDARDISE.out.versions.first())

    ch_taxpasta = ch_branched.standardised
        .mix(TAXPASTA_STANDARDISE.out.standardised)

    //
    // MODULE: Build the ete3 taxonomy database once from a pinned taxdump (optional).
    // Without --taxdump, ete3 uses/downloads its default database inside each task.
    //
    ETE3_BUILD_TAXDB(ch_taxdump)
    ch_versions = ch_versions.mix(ETE3_BUILD_TAXDB.out.versions)
    ch_taxdb = ETE3_BUILD_TAXDB.out.db.toList().map { files -> files ? files.flatten() : [] }

    //
    // MODULE: Convert taxpasta profiles to CAMI Bioboxes format
    //
    TAXPASTA_TO_BIOBOXES (
        ch_taxpasta,
        ch_taxdb
    )
    ch_versions = ch_versions.mix(TAXPASTA_TO_BIOBOXES.out.versions.first())

    //
    // Group bioboxes by sample_id for per-sample OPAL evaluation.
    // Labels and files are kept in the same order so OPAL's -l matches the file list.
    //
    ch_bioboxes_per_sample = TAXPASTA_TO_BIOBOXES.out.bioboxes
        .map { meta, bioboxes -> [meta.sample_id, meta.label, bioboxes] }
        .groupTuple()
        .map { sample_id, labels, bioboxes_files ->
            def order = (0..<labels.size()).toList().sort { labels[it] }
            def sorted_labels = order.collect { labels[it] }
            def sorted_files = order.collect { bioboxes_files[it] }
            def meta_grouped = [
                id: sample_id,
                sample_id: sample_id,
                labels: sorted_labels.join(','),
                num_classifiers: sorted_labels.size()
            ]
            [meta_grouped, sorted_files]
        }

    //
    // MODULE: Run OPAL evaluation per sample_id
    //
    OPAL_PER_SAMPLE (
        ch_bioboxes_per_sample
            .combine(ch_gold_standard)
            .map { meta, bioboxes_files, gold_std -> tuple(meta, gold_std, bioboxes_files) }
    )
    ch_versions = ch_versions.mix(OPAL_PER_SAMPLE.out.versions.first())

    //
    // MODULE: Comparative analysis of classifiers per sample
    // Joined with the sample's bioboxes files so that per-taxon comparisons are possible.
    //
    ch_comparative_input = OPAL_PER_SAMPLE.out.results
        .map { meta, opal_dir -> [meta.id, meta, opal_dir] }
        .join(ch_bioboxes_per_sample.map { meta, bioboxes_files -> [meta.id, bioboxes_files] }, failOnMismatch: true)
        .map { _id, meta, opal_dir, bioboxes_files -> [meta, opal_dir, bioboxes_files] }

    COMPARATIVE_ANALYSIS (
        ch_comparative_input,
        ch_gold_standard
    )
    ch_versions = ch_versions.mix(COMPARATIVE_ANALYSIS.out.versions.first())
    ch_multiqc_files = ch_multiqc_files.mix(COMPARATIVE_ANALYSIS.out.multiqc.map { _meta, mqc -> mqc })

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
