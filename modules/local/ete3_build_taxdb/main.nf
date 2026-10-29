process ETE3_BUILD_TAXDB {
    tag "$taxdump.name"
    label 'process_single'

    conda "${moduleDir}/environment.yml"
    // Frozen Seqera Wave community image built from environment.yml (python 3.11, pandas, ete3).
    // NOTE: ete3 3.1.3 does not work on python >= 3.13 (removed 'cgi' module).
    container "${ workflow.containerEngine in ['singularity', 'apptainer'] && !task.ext.singularity_pull_docker_container ?
        'https://community-cr-prod.seqera.io/docker/registry/v2/blobs/sha256/ed/ed50e74c200cc2f449192d3b3b2e444b8ab6a41a0c8f5e1af40c28583c774527/data' :
        'community.wave.seqera.io/library/python_pandas_ete3:0aabbd50f04018cb' }"

    input:
    path taxdump

    output:
    path "taxa.sqlite*", emit: db        // taxa.sqlite and taxa.sqlite.traverse.pkl
    tuple val("${task.process}"), val('python'), eval('python --version | sed "s/Python //"'), topic: versions, emit: versions_python
    tuple val("${task.process}"), val('ete3'), eval('python -c "import ete3; print(ete3.__version__)"'), topic: versions, emit: versions_ete3
    // Record which taxonomy was used (archive name and md5) alongside the software versions
    tuple val("${task.process}"), val("taxdump (${taxdump.name}) md5"), eval("md5sum ${taxdump} | cut -d' ' -f1"), topic: versions, emit: versions_taxdump

    when:
    task.ext.when == null || task.ext.when

    script:
    """
    # Build the ete3 NCBITaxa sqlite database once from a pinned taxdump so that
    # every TAXPASTA_TO_BIOBOXES task uses the same taxonomy without network access.
    python - <<'PY'
    import os, sys
    from ete3 import NCBITaxa
    taxdump = "${taxdump}"
    if not os.path.exists(taxdump):
        sys.exit(f"taxdump not found: {taxdump}")
    NCBITaxa(dbfile="taxa.sqlite", taxdump_file=taxdump)
    PY

    if [ ! -s taxa.sqlite ]; then
        echo "ERROR: taxa.sqlite was not created from ${taxdump}" >&2
        exit 1
    fi
    """

    stub:
    """
    touch taxa.sqlite
    touch taxa.sqlite.traverse.pkl
    """
}
