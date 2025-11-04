process OPAL_PER_SAMPLE {
    tag "$meta.id"
    label 'process_low'

    // NOTE: OPAL 1.0.13 has known issues with minimal datasets (<100 taxa)
    // Spider plots may fail with small test data. Use realistic datasets for production.
    // See: https://github.com/CAMI-challenge/OPAL/issues
    // NOTE: This module uses Seqera Wave for dynamic container building
    // If Wave is unavailable, use -profile conda
    conda "${moduleDir}/../opal/environment.yml"
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/cami-opal:1.0.13--pyhdfd78af_0' :
        'quay.io/biocontainers/cami-opal:1.0.13--pyhdfd78af_0' }"

    input:
    tuple val(meta), path(gold_standard), path(predictions)

    output:
    tuple val(meta), path("*", type: 'dir'), emit: results
    path "versions.yml"                     , emit: versions

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
    # Validate prediction count
    NUM_PREDICTIONS=${pred_files.size()}
    if [ \$NUM_PREDICTIONS -lt 1 ]; then
        echo "ERROR: No prediction files provided" >&2
        exit 1
    fi
    if [ \$NUM_PREDICTIONS -eq 1 ]; then
        echo "WARNING: Only 1 prediction provided. Comparison requires at least 2 for meaningful results." >&2
    fi
    echo "[OPAL_PER_SAMPLE] Evaluating \$NUM_PREDICTIONS predictions for ${meta.id}" >&2

    # Validate gold standard exists
    if [ ! -s ${gold_standard} ]; then
        echo "ERROR: Gold standard file ${gold_standard} does not exist or is empty" >&2
        exit 1
    fi

    # Create output directory explicitly
    mkdir -p ${prefix}

    # Run OPAL evaluation with error handling
    if ! opal.py \\
        -g ${gold_standard} \\
        -o ${prefix} \\
        ${label_arg} \\
        ${filter_arg} \\
        ${normalize_arg} \\
        ${rank_arg} \\
        ${args} \\
        ${pred_files.join(' ')} 2>&1 | tee opal.log; then
        echo "" >&2
        echo "ERROR: OPAL evaluation failed for ${meta.id}" >&2
        echo "Gold standard: ${gold_standard}" >&2
        echo "Predictions: ${pred_files.join(', ')}" >&2
        echo "" >&2
        echo "Common issues:" >&2
        echo "  1. Incompatible format between gold standard and predictions" >&2
        echo "  2. Missing required taxonomy ranks" >&2
        echo "  3. OPAL 1.0.13 bug with minimal datasets (<100 taxa)" >&2
        echo "" >&2
        echo "See opal.log for detailed error messages" >&2
        cat opal.log >&2
        exit 1
    fi

    # Verify OPAL created expected outputs
    if [ ! -d ${prefix} ] || [ ! -s ${prefix}/results.tsv ]; then
        echo "ERROR: OPAL did not create expected output directory or results.tsv" >&2
        ls -la ${prefix}/ 2>&1 || echo "Output directory does not exist" >&2
        exit 1
    fi

    echo "[OPAL_PER_SAMPLE] Successfully evaluated ${meta.id}" >&2
    echo "[OPAL_PER_SAMPLE] Output directory: ${prefix}" >&2
    ls -lh ${prefix}/*.{html,tsv} 2>/dev/null | head -5 || true

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
