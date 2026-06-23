"""Unit tests for bin/fix_gold_standard.py (taxopy-based)."""


import fix_gold_standard as fgs


def test_fix_rebuilds_full_taxpath(tmp_path, taxonomy_dir):
    # Input with a deliberately broken single-taxid TAXPATH (the realistic bug).
    inp = tmp_path / "broken.bioboxes"
    inp.write_text(
        "@SampleID:test\n@Version:0.9.1\n"
        "@Ranks:superkingdom|phylum|class|order|family|genus|species|strain\n"
        "@TaxonomyID:NCBI\n"
        "@@TAXID\tRANK\tTAXPATH\tTAXPATHSN\tPERCENTAGE\n"
        "561\tgenus\t561\troot|...|Escherichia\t60.0\n"
        "2\tsuperkingdom\t2\troot|...|Bacteria\t40.0\n"
    )
    out = tmp_path / "fixed.bioboxes"
    fgs.fix_gold_standard(str(inp), str(out), str(taxonomy_dir), sample_id="test")

    rows = [ln.split("\t") for ln in out.read_text().splitlines() if ln and not ln.startswith("@")]
    by_taxid = {r[0]: r for r in rows}
    # TAXPATH reconstructed to a full root-first lineage.
    assert by_taxid["561"][2].startswith("1|131567|2")
    assert by_taxid["561"][2].endswith("|561")
    # TAXPATH and TAXPATHSN depths match.
    for r in rows:
        assert len(r[2].split("|")) == len(r[3].split("|"))
    # Percentages renormalised to ~100.
    assert abs(sum(float(r[4]) for r in rows) - 100.0) < 0.01


def test_fix_skips_unsupported_ranks(tmp_path, taxonomy_dir):
    inp = tmp_path / "in.bioboxes"
    inp.write_text(
        "@@TAXID\tRANK\tTAXPATH\tTAXPATHSN\tPERCENTAGE\n"
        "561\tgenus\t561\tx\t50.0\n"
        "1\tno rank\t1\troot\t50.0\n"   # unsupported rank -> dropped
    )
    out = tmp_path / "out.bioboxes"
    fgs.fix_gold_standard(str(inp), str(out), str(taxonomy_dir), sample_id="test")
    rows = [ln for ln in out.read_text().splitlines() if ln and not ln.startswith("@")]
    assert len(rows) == 1
    assert rows[0].startswith("561\t")
