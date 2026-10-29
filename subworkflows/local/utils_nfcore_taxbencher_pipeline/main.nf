//
// Subworkflow with functionality specific to the FOI-Bioinformatics/taxbencher pipeline
//

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    IMPORT FUNCTIONS / MODULES / SUBWORKFLOWS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

include { UTILS_NFSCHEMA_PLUGIN     } from '../../nf-core/utils_nfschema_plugin'
include { paramsSummaryMap          } from 'plugin/nf-schema'
include { samplesheetToList         } from 'plugin/nf-schema'
include { completionEmail           } from '../../nf-core/utils_nfcore_pipeline'
include { completionSummary         } from '../../nf-core/utils_nfcore_pipeline'
include { UTILS_NFCORE_PIPELINE     } from '../../nf-core/utils_nfcore_pipeline'
include { UTILS_NEXTFLOW_PIPELINE   } from '../../nf-core/utils_nextflow_pipeline'

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    SUBWORKFLOW TO INITIALISE PIPELINE
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

workflow PIPELINE_INITIALISATION {

    take:
    version           // boolean: Display version and exit
    validate_params   // boolean: Boolean whether to validate parameters against the schema at runtime
    monochrome_logs   // boolean: Do not use coloured log outputs
    nextflow_cli_args //   array: List of positional nextflow CLI args
    outdir            //  string: The output directory where the results will be saved
    input             //  string: Path to input samplesheet
    help              // boolean: Display help message and exit
    help_full         // boolean: Show the full help message
    show_hidden       // boolean: Show hidden parameters in the help message

    main:

    ch_versions = channel.empty()

    //
    // Print version and exit if required and dump pipeline parameters to JSON file
    //
    UTILS_NEXTFLOW_PIPELINE (
        version,
        true,
        outdir,
        workflow.profile.tokenize(',').intersect(['conda', 'mamba']).size() >= 1
    )

    //
    // Validate parameters and generate parameter summary to stdout
    //

    def before_text = ""
    def after_text = ""
    if (monochrome_logs) {
        before_text = before_text.replaceAll(/\033\[[0-9;]*m/, '')
    }

    command = "nextflow run ${workflow.manifest.name} -profile <docker/singularity/.../institute> --input samplesheet.csv --outdir <OUTDIR>"

    UTILS_NFSCHEMA_PLUGIN (
        workflow,
        validate_params,
        null,
        help,
        help_full,
        show_hidden,
        before_text,
        after_text,
        command,
        null
    )

    //
    // Check config provided to the pipeline
    //
    UTILS_NFCORE_PIPELINE (
        nextflow_cli_args
    )

    //
    // Custom validation for pipeline parameters
    //
    validateInputParameters()

    //
    // Create channel from input file provided through params.input
    //
    // The samplesheet is validated against assets/schema_input.json (required columns,
    // value patterns, unique labels). Each entry becomes [ meta, input_file ] where
    //   meta = [ id: label, label: label, sample_id: sample_id, classifier: classifier, taxonomy_db: taxonomy_db ]
    // and input_file is a resolved, existing path (taxpasta TSV or raw profiler output).
    //
    def samplesheet_file = file(input, checkIfExists: true)
    ch_samplesheet = channel
        .fromList(samplesheetToList(input, "${projectDir}/assets/schema_input.json"))
        .map { meta, input_path ->
            def resolved = resolveInputFile(input_path.toString(), samplesheet_file)
            def meta_out = meta + [ taxonomy_db: meta.taxonomy_db ?: 'NCBI' ]
            return [ meta_out, resolved ]
        }

    //
    // Fail early when a biological sample has no matching @SampleID in the gold standard:
    // OPAL silently skips such profiles instead of failing.
    //
    ch_samplesheet
        .map { meta, _file -> meta.sample_id }
        .unique()
        .collect()
        .map { sample_ids -> validateSampleIdsAgainstGoldStandard(sample_ids, params.gold_standard) }

    emit:
    samplesheet = ch_samplesheet
    versions    = ch_versions
}

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    SUBWORKFLOW FOR PIPELINE COMPLETION
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

workflow PIPELINE_COMPLETION {

    take:
    email           //  string: email address
    email_on_fail   //  string: email address sent on pipeline failure
    plaintext_email // boolean: Send plain-text email instead of HTML
    outdir          //    path: Path to output directory where results will be published
    monochrome_logs // boolean: Disable ANSI colour codes in log output
    multiqc_report  //  string: Path to MultiQC report

    main:
    summary_params = paramsSummaryMap(parameters_schema: "nextflow_schema.json")
    def multiqc_reports = multiqc_report.toList()

    //
    // Completion email and summary
    //
    workflow.onComplete {
        if (email || email_on_fail) {
            completionEmail(
                summary_params,
                email,
                email_on_fail,
                plaintext_email,
                outdir,
                monochrome_logs,
                multiqc_reports.isBound() ? multiqc_reports.getVal() : [],
            )
        }

        completionSummary(monochrome_logs)

    }

    workflow.onError {
        log.error "Pipeline failed. Please refer to troubleshooting docs for common issues: https://nf-co.re/docs/running/troubleshooting"
    }
}

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    FUNCTIONS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

//
// Check and validate pipeline parameters
//
def validateInputParameters() {
    if (params.opal_filter != null && (params.opal_filter < 0 || params.opal_filter >= 100)) {
        error("--opal_filter must be a percentage in the range [0, 100), got ${params.opal_filter}")
    }
}

//
// Resolve a samplesheet file entry to an existing path.
// Order: remote URI or absolute path as given; relative to the samplesheet directory;
// relative to the launch directory; relative to the pipeline directory (bundled test data).
//
def resolveInputFile(String path_string, samplesheet_file) {
    if (path_string ==~ /^[a-zA-Z][a-zA-Z0-9+.-]*:\/\/.*/ ) {
        // s3://, gs://, az://, https://, ... - let Nextflow handle existence checks when staging
        return file(path_string)
    }
    if (path_string.startsWith('/')) {
        return file(path_string, checkIfExists: true)
    }
    def candidates = [
        samplesheet_file.parent ? samplesheet_file.parent.resolve(path_string) : null,
        file("${workflow.launchDir}/${path_string}"),
        file("${projectDir}/${path_string}"),
    ].findAll { candidate -> candidate != null }
    def found = candidates.find { candidate -> candidate.exists() }
    if (!found) {
        error(
            "Input file '${path_string}' listed in samplesheet ${samplesheet_file} was not found. Tried:\n" +
            candidates.collect { candidate -> "  - ${candidate}" }.join('\n') +
            "\nUse an absolute path, a path relative to the samplesheet, or a remote URI."
        )
    }
    return found
}

//
// Compare the sample IDs in the samplesheet with the @SampleID headers of the gold standard.
// Only local, uncompressed gold standards can be inspected; remote files are skipped.
//
def validateSampleIdsAgainstGoldStandard(List sample_ids, gold_standard_param) {
    if (!gold_standard_param) {
        return true
    }
    def gs = file(gold_standard_param)
    if (gold_standard_param.toString() ==~ /^[a-zA-Z][a-zA-Z0-9+.-]*:\/\/.*/ || !gs.exists() || gs.name.endsWith('.gz')) {
        log.info "[TAXBENCHER] Skipping gold standard sample ID pre-check for ${gold_standard_param}"
        return true
    }
    def gs_sample_ids = [] as Set
    gs.eachLine { line ->
        if (line.startsWith('@SampleID:')) {
            gs_sample_ids << line.substring('@SampleID:'.length()).trim()
        }
    }
    if (gs_sample_ids.isEmpty()) {
        error("Gold standard ${gs} contains no '@SampleID:' header. It must be in CAMI profiling (Bioboxes) format; run bin/validate_bioboxes.py on it.")
    }
    def missing = sample_ids.findAll { sample_id -> !(sample_id in gs_sample_ids) }
    if (missing) {
        error(
            "Sample ID(s) ${missing} from the samplesheet have no matching @SampleID in the gold standard ${gs} " +
            "(found: ${gs_sample_ids.sort()}). OPAL would silently skip these samples. " +
            "Rename the sample_id column or the gold standard @SampleID so they match."
        )
    }
    log.info "[TAXBENCHER] All ${sample_ids.size()} sample ID(s) have a matching @SampleID in the gold standard"
    return true
}

//
// Generate methods description for MultiQC
//
def toolCitationText() {
    def citation_text = [
            "Tools used in the workflow included:",
            "OPAL (Meyer et al. 2019),",
            "taxpasta (Beber et al. 2023),",
            "ete3 (Huerta-Cepas et al. 2016),",
            "MultiQC (Ewels et al. 2016)",
            "."
        ].join(' ').trim()

    return citation_text
}

def toolBibliographyText() {
    def reference_text = [
            "<li>Meyer, F., Bremges, A., Belmann, P., Janssen, S., McHardy, A. C., & Koslicki, D. (2019). Assessing taxonomic metagenome profilers with OPAL. Genome Biology, 20, 51. doi: 10.1186/s13059-019-1646-y</li>",
            "<li>Beber, M. E., Borry, M., Stamouli, S., & Fellows Yates, J. A. (2023). taxpasta: TAXonomic Profile Aggregation and STAndardization. Journal of Open Source Software, 8(87), 5627. doi: 10.21105/joss.05627</li>",
            "<li>Huerta-Cepas, J., Serra, F., & Bork, P. (2016). ETE 3: Reconstruction, Analysis, and Visualization of Phylogenomic Data. Molecular Biology and Evolution, 33(6), 1635–1638. doi: 10.1093/molbev/msw046</li>",
            "<li>Ewels, P., Magnusson, M., Lundin, S., & Käller, M. (2016). MultiQC: summarize analysis results from multiple tools and samples in a single report. Bioinformatics, 32(19), 3047–3048. doi: 10.1093/bioinformatics/btw354</li>"
        ].join(' ').trim()

    return reference_text
}

def methodsDescriptionText(mqc_methods_yaml) {
    // Convert  to a named map so can be used as with familiar NXF ${workflow} variable syntax in the MultiQC YML file
    def meta = [:]
    meta.workflow = workflow.toMap()
    meta["manifest_map"] = workflow.manifest.toMap()

    // Pipeline DOI
    if (meta.manifest_map.doi) {
        // Using a loop to handle multiple DOIs
        // Removing `https://doi.org/` to handle pipelines using DOIs vs DOI resolvers
        // Removing ` ` since the manifest.doi is a string and not a proper list
        def temp_doi_ref = ""
        def manifest_doi = meta.manifest_map.doi.tokenize(",")
        manifest_doi.each { doi_ref ->
            temp_doi_ref += "(doi: <a href=\'https://doi.org/${doi_ref.replace("https://doi.org/", "").replace(" ", "")}\'>${doi_ref.replace("https://doi.org/", "").replace(" ", "")}</a>), "
        }
        meta["doi_text"] = temp_doi_ref.substring(0, temp_doi_ref.length() - 2)
    } else meta["doi_text"] = ""
    meta["nodoi_text"] = meta.manifest_map.doi ? "" : "<li>If available, make sure to update the text to include the Zenodo DOI of version of the pipeline used. </li>"

    // Tool references
    meta["tool_citations"] = toolCitationText().replaceAll(", \\.", ".").replaceAll("\\. \\.", ".").replaceAll(", \\.", ".")
    meta["tool_bibliography"] = toolBibliographyText()


    def methods_text = mqc_methods_yaml.text

    def engine =  new groovy.text.SimpleTemplateEngine()
    def description_html = engine.createTemplate(methods_text).make(meta)

    return description_html.toString()
}
