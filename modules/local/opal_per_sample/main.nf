process OPAL_PER_SAMPLE {
    tag "$meta.id"
    label 'process_low'

    // NOTE: OPAL 1.0.13 has known issues with minimal datasets (<100 taxa)
    // Spider plots may fail with small test data. Use realistic datasets for production.
    // See: https://github.com/CAMI-challenge/OPAL/issues
    conda "${moduleDir}/environment.yml"
    container "${ workflow.containerEngine in ['singularity', 'apptainer'] && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/cami-opal:1.0.13--pyhdfd78af_0' :
        'quay.io/biocontainers/cami-opal:1.0.13--pyhdfd78af_0' }"

    input:
    tuple val(meta), path(gold_standard), path(predictions)

    output:
    tuple val(meta), path("${task.ext.prefix ?: meta.id}", type: 'dir'), emit: results
    // MPLCONFIGDIR keeps matplotlib from printing a warning when HOME is read-only; the grep extracts the bare version
    tuple val("${task.process}"), val('opal'), eval('MPLCONFIGDIR=$PWD/.mplconfig opal.py --version 2>&1 | grep -oE "opal.py [0-9][0-9.]*" | head -n 1 | sed "s/opal.py //"'), topic: versions, emit: versions_opal

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    def prefix = task.ext.prefix ?: "${meta.id}"

    // Convert predictions to list if it's a single file
    def pred_files = predictions instanceof List ? predictions : [predictions]

    // Labels: meta.labels (comma separated, same order as predictions) or file basenames
    def label_list = meta.labels ? meta.labels.toString().split(',').collect { label -> label.trim() } : pred_files.collect { pred -> pred.baseName }
    if (label_list.size() != pred_files.size()) {
        error("OPAL_PER_SAMPLE ${meta.id}: ${label_list.size()} labels for ${pred_files.size()} prediction files")
    }
    def labels = label_list.join(',')
    def label_arg = "-l \"${labels}\""

    // Optional filtering, normalisation and rank range (also settable via ext.args)
    def filter_arg = meta.filter ? "-f ${meta.filter}" : ''
    def normalize_arg = meta.normalize ? '-n' : ''
    def rank_arg = meta.rank ? "-r ${meta.rank}" : ''

    """
    # Give matplotlib a writable cache directory: with a read-only HOME it prints a warning
    # on every call (including 'opal.py --version'), which would corrupt the reported version string.
    export MPLCONFIGDIR=\$PWD/.mplconfig
    mkdir -p "\$MPLCONFIGDIR"
    # OPAL iterates over Python sets of taxon IDs when it sums abundances (UniFrac, L1 norm, ...).
    # With Python's randomised string hashing the summation order, and therefore the last digits of
    # several metrics, change from run to run. A fixed hash seed makes the results reproducible.
    export PYTHONHASHSEED=0

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

    # Validate every prediction file has data rows (OPAL fails obscurely on header-only files)
    for f in ${pred_files.join(' ')}; do
        if [ ! -s "\$f" ] || [ "\$(grep -vc '^@' "\$f" || true)" -eq 0 ]; then
            echo "ERROR: Prediction file \$f is empty or contains no data rows" >&2
            exit 1
        fi
    done

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

    # OPAL silently skips profiles whose @SampleID does not match the gold standard
    # ("Skipping assessment of <label> for sample <id>"). Treat this as an error so that
    # mismatches cannot produce an empty-looking but "successful" evaluation.
    if grep -q "Skipping assessment" opal.log; then
        echo "ERROR: OPAL skipped one or more profiles because their @SampleID does not match the gold standard:" >&2
        grep "Skipping assessment" opal.log >&2
        echo "Gold standard sample IDs: \$(grep -h '^@SampleID' ${gold_standard} | cut -d: -f2- | tr '\\n' ' ')" >&2
        exit 1
    fi
    # (awk reads the file directly: 'cut | grep -q' can exit via SIGPIPE under 'pipefail')
    IFS=',' read -r -a LABEL_ARRAY <<< "${labels}"
    for label in "\${LABEL_ARRAY[@]}"; do
        if ! awk -F'\\t' -v l="\$label" '\$1 == l { found = 1 } END { exit !found }' ${prefix}/results.tsv; then
            echo "ERROR: No OPAL metrics were produced for profile '\$label' (see opal.log)" >&2
            exit 1
        fi
    done

    # Keep the OPAL log with the results
    mv opal.log ${prefix}/opal.log

    echo "[OPAL_PER_SAMPLE] Successfully evaluated ${meta.id}" >&2
    echo "[OPAL_PER_SAMPLE] Output directory: ${prefix}" >&2
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    mkdir -p ${prefix}
    touch ${prefix}/results.html
    printf 'tool\\trank\\tmetric\\tsample\\tvalue\\n' > ${prefix}/results.tsv
    touch ${prefix}/confusion.tsv
    """
}
