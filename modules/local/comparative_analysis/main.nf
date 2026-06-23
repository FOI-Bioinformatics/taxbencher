process COMPARATIVE_ANALYSIS {
    tag "$meta.id"
    label 'process_single'

    // Persistent Seqera community container with pandas + scikit-learn + plotly +
    // scipy + statsmodels + python-kaleido, frozen from environment.yml. Rebuild with:
    //   wave --conda-file environment.yml --freeze --platform linux/amd64 --await
    // COMPARATIVE_ANALYSIS is also configured as non-fatal (conf/modules.config) so the
    // core OPAL benchmarking still completes even if this container is unavailable.
    conda "${moduleDir}/environment.yml"
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'https://community.wave.seqera.io/library/comparative_analysis:5b956e9e3425d4ac' :
        'community.wave.seqera.io/library/comparative_analysis:5b956e9e3425d4ac' }"

    input:
    tuple val(meta), path(opal_dir), path(bioboxes)
    path(gold_standard)

    output:
    tuple val(meta), path("*_pca.html")          , emit: pca_plot
    tuple val(meta), path("*_diff_taxa.tsv")     , emit: diff_taxa
    tuple val(meta), path("*_comparison.html")   , emit: comparison_report
    path "versions.yml"                          , emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    def prefix = task.ext.prefix ?: "${meta.id}"
    def sample_id = meta.sample_id ?: meta.id
    def labels = meta.labels ?: ''

    """
    comparative_analysis.py \\
        --opal-dir ${opal_dir} \\
        --gold-standard ${gold_standard} \\
        --bioboxes-dir . \\
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
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    touch ${prefix}_pca.html
    touch ${prefix}_diff_taxa.tsv
    touch ${prefix}_comparison.html

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: 3.11.0
        comparative_analysis: 1.1.0
    END_VERSIONS
    """
}
