process TAXPASTA_TO_BIOBOXES {
    tag "$meta.id"
    label 'process_single'

    conda "${moduleDir}/environment.yml"
    // Frozen Seqera Wave community image built from environment.yml (python 3.11, pandas, ete3).
    // NOTE: ete3 3.1.3 does not work on python >= 3.13 (removed 'cgi' module).
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'oras://community.wave.seqera.io/library/python_pandas_ete3:5b8b0209dd78f973' :
        'community.wave.seqera.io/library/python_pandas_ete3:0aabbd50f04018cb' }"

    input:
    tuple val(meta), path(taxpasta_tsv)
    path taxdb                              // optional: ete3 taxa.sqlite (+ .traverse.pkl) from ETE3_BUILD_TAXDB, or []

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
    // MetaPhlAn reports clade-cumulative relative abundances for every level of the
    // lineage; every other taxpasta-supported profiler reports reads assigned directly
    // to a taxon, which have to be summed over descendants to obtain clade abundances.
    def clade_profilers = ['metaphlan']
    def abundance_mode = meta.abundance_mode ?: (clade_profilers.contains((meta.classifier ?: '').toString().toLowerCase()) ? 'clade' : 'direct')
    def taxdb_files = taxdb instanceof List ? taxdb : (taxdb ? [taxdb] : [])
    def sqlite = taxdb_files.find { it.name.endsWith('.sqlite') }
    def taxdb_arg = sqlite ? "--ete3-db ${sqlite}" : ''

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

    echo "[TAXPASTA_TO_BIOBOXES] ${meta.id}: classifier=${meta.classifier ?: 'n/a'} abundance_mode=${abundance_mode} taxonomy=${sqlite ? sqlite : 'ete3 default database'}" >&2

    # Run conversion with error handling
    if ! taxpasta_to_bioboxes.py \\
        -i ${taxpasta_tsv} \\
        -o ${prefix}.bioboxes \\
        -s ${sample_id} \\
        -r "${ranks}" \\
        -d ${taxonomy_db} \\
        --abundance-mode ${abundance_mode} \\
        --version-bioboxes ${version_bioboxes} \\
        ${taxdb_arg} \\
        ${args}; then
        echo "ERROR: Conversion from taxpasta to bioboxes failed for ${meta.id}" >&2
        echo "Input: ${taxpasta_tsv}" >&2
        echo "Taxonomy DB: ${taxonomy_db}" >&2
        exit 1
    fi

    # Verify output was created, is not empty and contains data rows
    if [ ! -s ${prefix}.bioboxes ]; then
        echo "ERROR: Output file ${prefix}.bioboxes was not created or is empty" >&2
        exit 1
    fi
    N_ROWS=\$(grep -vc '^@' ${prefix}.bioboxes || true)
    echo "[TAXPASTA_TO_BIOBOXES] Successfully converted ${meta.id} to bioboxes format (\$N_ROWS data rows)" >&2

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
        taxpasta_to_bioboxes: 2.0.0
    END_VERSIONS
    """
}
