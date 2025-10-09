process TAXPASTA_STANDARDISE {
    tag "$meta.id"
    label 'process_low'

    conda "${moduleDir}/environment.yml"
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/taxpasta:0.7.0--pyhdfd78af_0':
        'biocontainers/taxpasta:0.7.0--pyhdfd78af_0' }"

    input:
    tuple val(meta), path(profiler_output)

    output:
    tuple val(meta), path("*.tsv"), emit: standardised
    path "versions.yml"           , emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    taxpasta standardise \\
        --profiler ${meta.classifier} \\
        --output ${prefix}.tsv \\
        $args \\
        $profiler_output

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        taxpasta: \$(taxpasta --version 2>&1 | sed 's/taxpasta, version //')
    END_VERSIONS
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    touch ${prefix}.tsv

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        taxpasta: \$(taxpasta --version 2>&1 | sed 's/taxpasta, version //')
    END_VERSIONS
    """
}
