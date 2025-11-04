process TAXPASTA_TO_BIOBOXES {
    tag "$meta.id"
    label 'process_single'

    // Custom Seqera Wave container with pandas + ete3 dependencies
    conda "${moduleDir}/environment.yml"
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'https://community.wave.seqera.io/library/pip_ete3_pandas:3d986008f4614a7f' :
        'community.wave.seqera.io/library/pip_ete3_pandas:3d986008f4614a7f' }"

    input:
    tuple val(meta), path(taxpasta_tsv)

    output:
    tuple val(meta), path("*.bioboxes"), emit: bioboxes
    path "versions.yml"                , emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    def prefix = task.ext.prefix ?: "${meta.id}"
    def sample_id = meta.sample_id ?: meta.id
    def ranks = meta.ranks ?: 'superkingdom|phylum|class|order|family|genus|species|strain'
    def taxonomy_db = meta.taxonomy_db ?: 'NCBI'
    def version_bioboxes = '0.9.1'

    """
    # Validate taxonomy database parameter
    VALID_DBS="NCBI GTDB"
    if ! echo "\$VALID_DBS" | grep -qw "${taxonomy_db}"; then
        echo "ERROR: Unsupported taxonomy_db: ${taxonomy_db}" >&2
        echo "Supported databases: \$VALID_DBS" >&2
        exit 1
    fi

    # Validate input file exists and is not empty
    if [ ! -s ${taxpasta_tsv} ]; then
        echo "ERROR: Input file ${taxpasta_tsv} does not exist or is empty" >&2
        exit 1
    fi

    # Run conversion with error handling
    if ! taxpasta_to_bioboxes.py \\
        -i ${taxpasta_tsv} \\
        -o ${prefix}.bioboxes \\
        -s ${sample_id} \\
        -r "${ranks}" \\
        -d ${taxonomy_db} \\
        --version-bioboxes ${version_bioboxes} \\
        ${args}; then
        echo "ERROR: Conversion from taxpasta to bioboxes failed for ${meta.id}" >&2
        echo "Input: ${taxpasta_tsv}" >&2
        echo "Taxonomy DB: ${taxonomy_db}" >&2
        exit 1
    fi

    # Verify output was created and is not empty
    if [ ! -s ${prefix}.bioboxes ]; then
        echo "ERROR: Output file ${prefix}.bioboxes was not created or is empty" >&2
        exit 1
    fi

    echo "[TAXPASTA_TO_BIOBOXES] Successfully converted ${meta.id} to bioboxes format" >&2
    echo "[TAXPASTA_TO_BIOBOXES] Output: ${prefix}.bioboxes (\$(wc -l < ${prefix}.bioboxes) lines)" >&2

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: \$(python --version | sed 's/Python //g')
        pandas: \$(python -c "import pandas; print(pandas.__version__)" 2>/dev/null || echo "unknown")
        ete3: \$(python -c "import ete3; print(ete3.__version__)" 2>/dev/null || echo "not installed")
        taxpasta_to_bioboxes: \$(taxpasta_to_bioboxes.py --version 2>/dev/null | sed 's/taxpasta_to_bioboxes.py //g' || echo "unknown")
    END_VERSIONS
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    touch ${prefix}.bioboxes

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: \$(python --version | sed 's/Python //g')
        taxpasta_to_bioboxes: 1.0.0
    END_VERSIONS
    """
}
