process TAXPASTA_TO_BIOBOXES {
    tag "$meta.id"
    label 'process_single'

    conda "${moduleDir}/environment.yml"
    // Container automatically built by Wave from environment.yml (use -profile wave)
    // For Docker/Singularity without Wave: requires custom container with pandas and ete3
    // Conda profile recommended for this module
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'oras://community.wave.seqera.io/library/pandas_python_pip:d3ab4533ebd816a9' :
        'community.wave.seqera.io/library/pandas_python_pip:d3ab4533ebd816a9' }"

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
    taxpasta_to_bioboxes.py \\
        -i ${taxpasta_tsv} \\
        -o ${prefix}.bioboxes \\
        -s ${sample_id} \\
        -r "${ranks}" \\
        -d ${taxonomy_db} \\
        --version-bioboxes ${version_bioboxes} \\
        ${args}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: \$(python --version | sed 's/Python //g')
        taxpasta_to_bioboxes: \$(taxpasta_to_bioboxes.py --version | sed 's/taxpasta_to_bioboxes.py //g')
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
