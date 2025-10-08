#!/usr/bin/env nextflow
/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    FOI-Bioinformatics/taxbencher
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Github : https://github.com/FOI-Bioinformatics/taxbencher
----------------------------------------------------------------------------------------
*/

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    IMPORT FUNCTIONS / MODULES / SUBWORKFLOWS / WORKFLOWS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

include { TAXBENCHER  } from './workflows/taxbencher'
include { PIPELINE_INITIALISATION } from './subworkflows/local/utils_nfcore_taxbencher_pipeline'
include { PIPELINE_COMPLETION     } from './subworkflows/local/utils_nfcore_taxbencher_pipeline'

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    NAMED WORKFLOWS FOR PIPELINE
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

//
// WORKFLOW: Run main analysis pipeline depending on type of input
//
workflow FOIBIOINFORMATICS_TAXBENCHER {

    take:
    samplesheet // channel: samplesheet read in from --input

    main:

    //
    // Create gold standard channel from parameter
    //
    ch_gold_standard = Channel.fromPath(params.gold_standard, checkIfExists: true).first()

    //
    // Parse samplesheet to create taxpasta channel
    // Samplesheet format: sample,classifier,taxpasta_file,taxonomy_db
    // Channel emits maps with column names as keys from splitCsv
    //
    ch_taxpasta = samplesheet.map { row ->
        def meta = [
            id: "${row.sample}_${row.classifier}",
            sample_id: row.sample,
            classifier: row.classifier,
            taxonomy_db: row.taxonomy_db
        ]
        // Resolve file path relative to projectDir if it's not absolute
        def taxpasta_path = row.taxpasta_file.startsWith('/') ?
            file(row.taxpasta_file) :
            file("${projectDir}/${row.taxpasta_file}")
        [meta, taxpasta_path]
    }

    //
    // WORKFLOW: Run pipeline
    //
    TAXBENCHER (
        ch_taxpasta,
        ch_gold_standard
    )

    emit:
    opal_results   = TAXBENCHER.out.opal_results   // channel: [ [meta], path(opal_results/) ]
    multiqc_report = TAXBENCHER.out.multiqc_report // channel: /path/to/multiqc_report.html
}
/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    RUN MAIN WORKFLOW
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

workflow {

    main:

    ch_versions = Channel.empty()

    //
    // SUBWORKFLOW: Run initialisation tasks
    //
    PIPELINE_INITIALISATION (
        params.version,
        params.validate_params,
        params.monochrome_logs,
        args,
        params.outdir,
        params.input
    )
    ch_versions = ch_versions.mix(PIPELINE_INITIALISATION.out.versions)

    //
    // WORKFLOW: Run main workflow
    //
    FOIBIOINFORMATICS_TAXBENCHER (
        PIPELINE_INITIALISATION.out.samplesheet
    )
    //
    // SUBWORKFLOW: Run completion tasks
    //
    PIPELINE_COMPLETION (
        params.email,
        params.email_on_fail,
        params.plaintext_email,
        params.outdir,
        params.monochrome_logs,
        params.hook_url,
        FOIBIOINFORMATICS_TAXBENCHER.out.multiqc_report
    )
}

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    THE END
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/
