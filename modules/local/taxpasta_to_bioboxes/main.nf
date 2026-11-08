process TAXPASTA_TO_BIOBOXES {
    tag "$meta.id"
    label 'process_single'

    conda "${moduleDir}/environment.yml"
    // The taxpasta biocontainer ships pandas and taxopy (taxpasta's own taxonomy library),
    // so the conversion needs no extra image.
    container "${ workflow.containerEngine in ['singularity', 'apptainer'] && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/taxpasta:0.7.0--pyhdfd78af_0':
        'quay.io/biocontainers/taxpasta:0.7.0--pyhdfd78af_0' }"

    input:
    tuple val(meta), path(taxpasta_tsv)
    path taxdump                            // optional: extracted taxdump directory from PREPARE_TAXDUMP, or []

    output:
    tuple val(meta), path("*.bioboxes"), emit: bioboxes
    tuple val("${task.process}"), val('python'), eval('python --version | sed "s/Python //"'), topic: versions, emit: versions_python
    tuple val("${task.process}"), val('pandas'), eval('python -c "import pandas; print(pandas.__version__)"'), topic: versions, emit: versions_pandas
    tuple val("${task.process}"), val('taxopy'), eval('python -c "import taxopy; print(taxopy.__version__)"'), topic: versions, emit: versions_taxopy
    tuple val("${task.process}"), val('taxpasta_to_bioboxes'), eval('taxpasta_to_bioboxes.py --version | sed "s/taxpasta_to_bioboxes.py //"'), topic: versions, emit: versions_taxpasta_to_bioboxes

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
    // Any MetaPhlAn version (metaphlan, metaphlan4, MetaPhlAn_4.1, ...); a samplesheet
    // abundance_mode column overrides the guess for other cumulative profilers.
    def is_metaphlan = (meta.classifier ?: '').toString().toLowerCase().startsWith('metaphlan')
    def abundance_mode = meta.abundance_mode ?: (is_metaphlan ? 'clade' : 'direct')
    def taxdump_dir = taxdump instanceof List ? (taxdump ? taxdump[0] : null) : taxdump
    def taxdump_arg = taxdump_dir ? "--taxdump ${taxdump_dir}" : ''

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

    echo "[TAXPASTA_TO_BIOBOXES] ${meta.id}: classifier=${meta.classifier ?: 'n/a'} abundance_mode=${abundance_mode} taxonomy=${taxdump_dir ?: 'download of the current NCBI taxdump'}" >&2

    # Run conversion with error handling
    if ! taxpasta_to_bioboxes.py \\
        -i ${taxpasta_tsv} \\
        -o ${prefix}.bioboxes \\
        -s ${sample_id} \\
        -r "${ranks}" \\
        -d ${taxonomy_db} \\
        --abundance-mode ${abundance_mode} \\
        --version-bioboxes ${version_bioboxes} \\
        ${taxdump_arg} \\
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
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    touch ${prefix}.bioboxes
    """
}
