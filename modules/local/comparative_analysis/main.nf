process COMPARATIVE_ANALYSIS {
    tag "$meta.id"
    label 'process_single'

    // Frozen Seqera Wave community image built from environment.yml
    // (python 3.11, pandas, scikit-learn, plotly, scipy, statsmodels, numpy, python-kaleido)
    conda "${moduleDir}/environment.yml"
    container "${ workflow.containerEngine in ['singularity', 'apptainer'] && !task.ext.singularity_pull_docker_container ?
        'https://community-cr-prod.seqera.io/docker/registry/v2/blobs/sha256/e0/e04b00d88399791cdd132f05867b1ade1dc3966a71153eb0f40b60c0185d7e7d/data' :
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
    tuple val("${task.process}"), val('python'), eval('python --version | sed "s/Python //"'), topic: versions, emit: versions_python
    tuple val("${task.process}"), val('comparative_analysis'), eval('comparative_analysis.py --version | sed "s/comparative_analysis.py //"'), topic: versions, emit: versions_comparative_analysis

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    def prefix = task.ext.prefix ?: "${meta.id}"
    def sample_id = meta.sample_id ?: meta.id
    def bioboxes_files = bioboxes instanceof List ? bioboxes : (bioboxes ? [bioboxes] : [])
    def labels = meta.labels ?: bioboxes_files.collect { bioboxes_file -> bioboxes_file.baseName }.join(',')
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
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    touch ${prefix}_pca.html
    touch ${prefix}_diff_taxa.tsv
    touch ${prefix}_comparison.html
    touch ${prefix}_metrics_wide.tsv
    touch ${prefix}_opal_summary_mqc.tsv
    """
}
