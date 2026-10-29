process BENCHMARK_SUMMARY {
    tag "all samples"
    label 'process_single'

    // Same frozen Seqera Wave community image as COMPARATIVE_ANALYSIS (pandas available)
    conda "${moduleDir}/environment.yml"
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'oras://community.wave.seqera.io/library/python_pandas_scikit-learn_plotly_pruned:24c8063ae8d7b157' :
        'community.wave.seqera.io/library/python_pandas_scikit-learn_plotly_pruned:afa623fee18ad8e0' }"

    input:
    path metrics            // all *_metrics_wide.tsv files from COMPARATIVE_ANALYSIS

    output:
    path "*_summary.tsv"  , emit: summary
    path "*_ranking.tsv"  , emit: ranking
    path "*_mqc.tsv"      , emit: multiqc
    path "versions.yml"   , emit: versions

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

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: \$(python --version | sed 's/Python //g')
        pandas: \$(python -c "import pandas; print(pandas.__version__)")
        summarise_benchmark: \$(summarise_benchmark.py --version | sed 's/summarise_benchmark.py //g')
    END_VERSIONS
    """

    stub:
    def prefix = task.ext.prefix ?: 'benchmark'
    """
    touch ${prefix}_summary.tsv
    touch ${prefix}_ranking.tsv
    touch ${prefix}_table_mqc.tsv
    touch ${prefix}_f1_by_rank_mqc.tsv
    touch ${prefix}_l1_by_rank_mqc.tsv

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: 3.11.0
        pandas: 2.0.0
        summarise_benchmark: 1.0.0
    END_VERSIONS
    """
}
