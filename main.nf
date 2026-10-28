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
    samplesheet // channel: [ [meta], path(input_file) ] read in from --input

    main:

    //
    // Create gold standard channel from parameter (value channel, reused for every sample)
    //
    ch_gold_standard = Channel.fromPath(params.gold_standard, checkIfExists: true).first()

    //
    // Optional pinned NCBI taxonomy dump for reproducible, offline lineage lookups
    //
    ch_taxdump = params.taxdump ? Channel.fromPath(params.taxdump, checkIfExists: true).first() : Channel.empty()

    //
    // WORKFLOW: Run pipeline
    //
    TAXBENCHER (
        samplesheet,
        ch_gold_standard,
        ch_taxdump
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
