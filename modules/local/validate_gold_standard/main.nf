process VALIDATE_GOLD_STANDARD {
    tag "$gold_standard.name"
    label 'process_single'

    conda "${moduleDir}/environment.yml"
    container "${ workflow.containerEngine in ['singularity', 'apptainer'] && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/python:3.11' :
        'quay.io/biocontainers/python:3.11' }"

    input:
    path gold_standard
    val  sample_ids          // list of sample IDs that must be present as @SampleID blocks

    output:
    path gold_standard        , emit: gold_standard   // the same file, emitted after successful validation
    path "*_validation.txt"   , emit: report
    tuple val("${task.process}"), val('python'), eval('python --version | sed "s/Python //"'), topic: versions, emit: versions_python
    tuple val("${task.process}"), val('validate_bioboxes'), eval('validate_bioboxes.py --version | sed "s/validate_bioboxes.py //"'), topic: versions, emit: versions_validate_bioboxes

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    def prefix = task.ext.prefix ?: gold_standard.baseName
    def ids = sample_ids instanceof List ? sample_ids : [sample_ids]
    def sample_args = ids.collect { id -> "--sample-id '${id}'" }.join(' ')
    """
    # Validate the CAMI profiling format (per-rank sums, TAXPATH structure, required headers)
    # and make sure every sample of the samplesheet has a gold standard block.
    if ! validate_bioboxes.py --strict ${sample_args} ${args} ${gold_standard} > ${prefix}_validation.txt 2>&1; then
        echo "ERROR: gold standard ${gold_standard} failed validation:" >&2
        cat ${prefix}_validation.txt >&2
        echo "" >&2
        echo "See docs/troubleshooting-gold-standard.md; bin/fix_gold_standard.py can repair most issues." >&2
        exit 1
    fi
    echo "[VALIDATE_GOLD_STANDARD] ${gold_standard} is a valid CAMI profile for sample(s): ${ids.join(', ')}" >&2
    """

    stub:
    def prefix = task.ext.prefix ?: gold_standard.baseName
    """
    echo "stub validation" > ${prefix}_validation.txt
    """
}
