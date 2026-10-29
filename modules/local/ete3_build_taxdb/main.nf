process ETE3_BUILD_TAXDB {
    tag "$taxdump.name"
    label 'process_single'

    conda "${moduleDir}/environment.yml"
    // Frozen Seqera Wave community image built from environment.yml (python 3.11, pandas, ete3).
    // NOTE: ete3 3.1.3 does not work on python >= 3.13 (removed 'cgi' module).
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'oras://community.wave.seqera.io/library/python_pandas_ete3:5b8b0209dd78f973' :
        'community.wave.seqera.io/library/python_pandas_ete3:0aabbd50f04018cb' }"

    input:
    path taxdump

    output:
    path "taxa.sqlite*", emit: db        // taxa.sqlite and taxa.sqlite.traverse.pkl
    path "versions.yml", emit: versions

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

    # Record which taxonomy was used (archive name and md5) next to the software versions
    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: \$(python --version | sed 's/Python //g')
        ete3: \$(python -c "import ete3; print(ete3.__version__)")
        taxdump: ${taxdump.name}
        taxdump_md5: \$(md5sum ${taxdump} | cut -d' ' -f1)
    END_VERSIONS
    """

    stub:
    """
    touch taxa.sqlite
    touch taxa.sqlite.traverse.pkl

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: \$(python --version | sed 's/Python //g')
        ete3: 3.1.3
    END_VERSIONS
    """
}
