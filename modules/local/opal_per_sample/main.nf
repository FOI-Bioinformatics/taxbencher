process OPAL_PER_SAMPLE {
    tag "$meta.id"
    label 'process_low'

    conda "${moduleDir}/../opal/environment.yml"
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/cami-opal:1.0.13--pyhdfd78af_0' :
        'quay.io/biocontainers/cami-opal:1.0.13--pyhdfd78af_0' }"

    input:
    tuple val(meta), path(gold_standard), path(predictions)

    output:
    tuple val(meta), path("${prefix}/"), emit: results
    path "versions.yml"                , emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    def prefix = task.ext.prefix ?: "${meta.id}"

    // Handle labels for predictions
    def labels = meta.labels ?: predictions.collect { it.baseName }.join(',')
    def label_arg = labels ? "-l \"${labels}\"" : ''

    // Handle optional filtering and normalization
    def filter_arg = meta.filter ? "-f ${meta.filter}" : ''
    def normalize_arg = meta.normalize ? '-n' : ''

    // Handle rank range if specified
    def rank_arg = meta.rank ? "-r ${meta.rank}" : ''

    // Convert predictions to list if it's a single file
    def pred_files = predictions instanceof List ? predictions : [predictions]

    """
    opal.py \\
        -g ${gold_standard} \\
        -o ${prefix} \\
        ${label_arg} \\
        ${filter_arg} \\
        ${normalize_arg} \\
        ${rank_arg} \\
        ${args} \\
        ${pred_files.join(' ')}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        opal: \$(opal.py --version 2>&1 | sed 's/OPAL //g')
    END_VERSIONS
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    mkdir -p ${prefix}
    touch ${prefix}/results.html
    touch ${prefix}/metrics.txt

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        opal: 1.0.13
    END_VERSIONS
    """
}
