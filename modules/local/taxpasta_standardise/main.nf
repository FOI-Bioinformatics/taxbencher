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
    # Log processing information
    echo "[TAXPASTA_STANDARDISE] Processing ${meta.id} with classifier: ${meta.classifier}" >&2
    echo "[TAXPASTA_STANDARDISE] Input file: $profiler_output" >&2
    echo "[TAXPASTA_STANDARDISE] File extension: \$(echo $profiler_output | sed 's/.*\\.//')" >&2

    # Validate classifier is supported by taxpasta
    SUPPORTED_PROFILERS="bracken centrifuge diamond ganon kaiju kmcp kraken2 krakenuniq megan6 metaphlan motus"
    if ! echo "\$SUPPORTED_PROFILERS" | grep -qw "${meta.classifier}"; then
        echo "ERROR: Classifier '${meta.classifier}' is not supported by taxpasta." >&2
        echo "Supported profilers: \$SUPPORTED_PROFILERS" >&2
        exit 1
    fi

    # Run taxpasta standardisation with error handling
    if ! taxpasta standardise \\
        --profiler ${meta.classifier} \\
        --output ${prefix}.tsv \\
        $args \\
        $profiler_output 2>&1 | tee taxpasta.log; then

        echo "" >&2
        echo "ERROR: taxpasta standardisation failed for ${meta.id}" >&2
        echo "Classifier: ${meta.classifier}" >&2
        echo "Input file: $profiler_output" >&2
        echo "" >&2
        echo "Common issues:" >&2
        echo "  1. File format doesn't match classifier expectation" >&2
        echo "  2. Incorrect file extension (see docs/raw-inputs.md for supported formats)" >&2
        echo "  3. Malformed input file (missing columns, wrong delimiter)" >&2
        echo "" >&2
        echo "See taxpasta.log for detailed error messages" >&2
        cat taxpasta.log >&2
        exit 1
    fi

    # Verify output was created
    if [ ! -s ${prefix}.tsv ]; then
        echo "ERROR: Output file ${prefix}.tsv was not created or is empty" >&2
        exit 1
    fi

    echo "[TAXPASTA_STANDARDISE] Successfully standardised ${meta.id}" >&2
    echo "[TAXPASTA_STANDARDISE] Output: ${prefix}.tsv (\$(wc -l < ${prefix}.tsv) lines)" >&2

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        taxpasta: \$(taxpasta --version 2>/dev/null | sed 's/taxpasta, version //')
    END_VERSIONS
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    touch ${prefix}.tsv

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        taxpasta: \$(taxpasta --version 2>/dev/null | sed 's/taxpasta, version //')
    END_VERSIONS
    """
}
