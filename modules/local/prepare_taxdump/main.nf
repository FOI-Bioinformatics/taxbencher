process PREPARE_TAXDUMP {
    tag "$taxdump.name"
    label 'process_single'

    // Same biocontainer as TAXPASTA_STANDARDISE and TAXPASTA_TO_BIOBOXES (python + taxopy)
    conda "${moduleDir}/environment.yml"
    container "${ workflow.containerEngine in ['singularity', 'apptainer'] && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/taxpasta:0.7.0--pyhdfd78af_0':
        'quay.io/biocontainers/taxpasta:0.7.0--pyhdfd78af_0' }"

    input:
    path taxdump                            // taxdump.tar.gz / .tgz or a dated taxdmp_YYYY-MM-DD.zip

    output:
    path "taxdump", emit: taxdump           // directory with nodes.dmp, names.dmp and merged.dmp
    tuple val("${task.process}"), val('python'), eval('python --version | sed "s/Python //"'), topic: versions, emit: versions_python
    // Record which taxonomy was used (archive name and md5) alongside the software versions
    tuple val("${task.process}"), val("taxdump (${taxdump.name}) md5"), eval("md5sum ${taxdump} | cut -d' ' -f1"), topic: versions, emit: versions_taxdump

    when:
    task.ext.when == null || task.ext.when

    script:
    """
    # Extract the taxonomy once so that every TAXPASTA_TO_BIOBOXES task reads the same
    # pinned taxdump without network access (a missing merged.dmp becomes an empty file).
    taxbencher_taxonomy.py extract ${taxdump} taxdump
    """

    stub:
    """
    mkdir taxdump
    touch taxdump/nodes.dmp taxdump/names.dmp taxdump/merged.dmp
    """
}
