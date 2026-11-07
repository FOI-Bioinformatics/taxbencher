process BENCHMARK_SUMMARY {
    tag "all samples"
    label 'process_single'

    // Same frozen Seqera Wave community image as COMPARATIVE_ANALYSIS (pandas available)
    conda "${moduleDir}/environment.yml"
    container "${ workflow.containerEngine in ['singularity', 'apptainer'] && !task.ext.singularity_pull_docker_container ?
        'https://community-cr-prod.seqera.io/docker/registry/v2/blobs/sha256/e0/e04b00d88399791cdd132f05867b1ade1dc3966a71153eb0f40b60c0185d7e7d/data' :
        'community.wave.seqera.io/library/python_pandas_scikit-learn_plotly_pruned:afa623fee18ad8e0' }"

    input:
    path metrics            // all *_metrics_wide.tsv files from COMPARATIVE_ANALYSIS

    output:
    path "*_summary.tsv"  , emit: summary
    path "*_ranking.tsv"  , emit: ranking
    path "*_mqc.tsv"      , emit: multiqc
    tuple val("${task.process}"), val('python'), eval('python --version | sed "s/Python //"'), topic: versions, emit: versions_python
    tuple val("${task.process}"), val('pandas'), eval('python -c "import pandas; print(pandas.__version__)"'), topic: versions, emit: versions_pandas
    tuple val("${task.process}"), val('summarise_benchmark'), eval('summarise_benchmark.py --version | sed "s/summarise_benchmark.py //"'), topic: versions, emit: versions_summarise_benchmark

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    def prefix = task.ext.prefix ?: 'benchmark'
    def metric_files = metrics instanceof List ? metrics : [metrics]
    """
    summarise_benchmark.py \\
        --metrics ${metric_files.join(' ')} \\
        --output-prefix ${prefix} \\
        ${args}
    """

    stub:
    def prefix = task.ext.prefix ?: 'benchmark'
    """
    touch ${prefix}_summary.tsv
    touch ${prefix}_ranking.tsv
    touch ${prefix}_table_mqc.tsv
    touch ${prefix}_f1_by_rank_mqc.tsv
    touch ${prefix}_l1_by_rank_mqc.tsv
    """
}
