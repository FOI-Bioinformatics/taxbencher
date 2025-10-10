process COMPARATIVE_ANALYSIS {
    tag "$meta.id"
    label 'process_single'

    conda "${moduleDir}/environment.yml"
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/python:3.11' :
        'biocontainers/python:3.11' }"

    input:
    tuple val(meta), path(opal_dir)
    path(gold_standard)

    output:
    tuple val(meta), path("${prefix}_pca.html")          , emit: pca_plot
    tuple val(meta), path("${prefix}_diff_taxa.tsv")     , emit: diff_taxa
    tuple val(meta), path("${prefix}_comparison.html")   , emit: comparison_report
    path "versions.yml"                                   , emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    prefix = task.ext.prefix ?: "${meta.id}"
    def sample_id = meta.sample_id ?: meta.id
    def labels = meta.labels ?: ''

    """
    comparative_analysis.py \\
        --opal-dir ${opal_dir} \\
        --gold-standard ${gold_standard} \\
        --sample-id ${sample_id} \\
        --labels "${labels}" \\
        --output-prefix ${prefix}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: \$(python --version | sed 's/Python //g')
        comparative_analysis: \$(comparative_analysis.py --version | sed 's/comparative_analysis.py //g')
    END_VERSIONS
    """

    stub:
    prefix = task.ext.prefix ?: "${meta.id}"
    """
    touch ${prefix}_pca.html
    touch ${prefix}_diff_taxa.tsv
    touch ${prefix}_comparison.html

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: 3.11.0
        comparative_analysis: 1.0.0
    END_VERSIONS
    """
}
