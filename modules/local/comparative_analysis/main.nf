process COMPARATIVE_ANALYSIS {
    tag "$meta.id"
    label 'process_single'

    // Frozen Seqera Wave community image built from environment.yml
    // (python 3.11, pandas, scikit-learn, plotly, scipy, statsmodels, numpy, python-kaleido)
    conda "${moduleDir}/environment.yml"
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'oras://community.wave.seqera.io/library/python_pandas_scikit-learn_plotly_pruned:24c8063ae8d7b157' :
        'community.wave.seqera.io/library/python_pandas_scikit-learn_plotly_pruned:afa623fee18ad8e0' }"

    input:
    tuple val(meta), path(opal_dir), path(bioboxes)   // bioboxes: prediction profiles of this sample (same order as meta.labels), or []
    path(gold_standard)

    output:
    tuple val(meta), path("*_pca.html")          , emit: pca_plot
    tuple val(meta), path("*_diff_taxa.tsv")     , emit: diff_taxa
    tuple val(meta), path("*_comparison.html")   , emit: comparison_report
    tuple val(meta), path("*_metrics_wide.tsv")  , emit: metrics_wide
    tuple val(meta), path("*_mqc.tsv")           , emit: multiqc
    path "versions.yml"                          , emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    def prefix = task.ext.prefix ?: "${meta.id}"
    def sample_id = meta.sample_id ?: meta.id
    def bioboxes_files = bioboxes instanceof List ? bioboxes : (bioboxes ? [bioboxes] : [])
    def labels = meta.labels ?: bioboxes_files.collect { it.baseName }.join(',')
    def bioboxes_arg = bioboxes_files ? "--bioboxes ${bioboxes_files.join(' ')}" : ''

    """
    comparative_analysis.py \\
        --opal-dir ${opal_dir} \\
        --gold-standard ${gold_standard} \\
        --sample-id ${sample_id} \\
        --labels "${labels}" \\
        ${bioboxes_arg} \\
        --output-prefix ${prefix} \\
        ${args}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: \$(python --version | sed 's/Python //g')
        comparative_analysis: \$(comparative_analysis.py --version | sed 's/comparative_analysis.py //g')
    END_VERSIONS
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    touch ${prefix}_pca.html
    touch ${prefix}_diff_taxa.tsv
    touch ${prefix}_comparison.html
    touch ${prefix}_metrics_wide.tsv
    touch ${prefix}_opal_summary_mqc.tsv

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: 3.11.0
        comparative_analysis: 2.0.0
    END_VERSIONS
    """
}
