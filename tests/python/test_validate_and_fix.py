"""Unit tests for bin/validate_bioboxes.py and bin/fix_gold_standard.py."""

import pytest

from conftest import rank_sums, read_profile

HEADER = "@SampleID:{sid}\n@Version:0.9.1\n@Ranks:superkingdom|phylum|class|order|family|genus|species|strain\n@TaxonomyID:NCBI\n"


def write(path, text):
    path.write_text(text)
    return path


# --------------------------------------------------------------------------- validator
def test_valid_gold_standards_pass(validator, test_data):
    for name in ("gold_standard.bioboxes", "gold_standard_raw.bioboxes", "gold_standard_realistic.bioboxes"):
        ok, errors, _warnings, stats = validator.validate_bioboxes(test_data / name)
        assert ok, (name, errors)
        assert stats["samples"]


def test_rank_sum_above_100_is_error(validator, tmp_path):
    f = write(tmp_path / "bad.bioboxes", HEADER.format(sid="s") +
              "@@TAXID\tRANK\tTAXPATH\tTAXPATHSN\tPERCENTAGE\n2\tsuperkingdom\t2\tBacteria\t80\n2157\tsuperkingdom\t2157\tArchaea\t40\n")
    ok, errors, _w, _s = validator.validate_bioboxes(f)
    assert not ok
    assert any("> 100%" in e for e in errors)


def test_rank_sum_below_100_is_only_warning(validator, tmp_path):
    f = write(tmp_path / "partial.bioboxes", HEADER.format(sid="s") +
              "@@TAXID\tRANK\tTAXPATH\tTAXPATHSN\tPERCENTAGE\n2\tsuperkingdom\t2\tBacteria\t60\n")
    ok, errors, warnings, _s = validator.validate_bioboxes(f)
    assert ok and not errors
    assert any("< 100%" in w for w in warnings)


def test_empty_taxpath_elements_allowed_but_last_must_match(validator, tmp_path):
    f = write(tmp_path / "gap.bioboxes", HEADER.format(sid="s") +
              "@@TAXID\tRANK\tTAXPATH\tTAXPATHSN\tPERCENTAGE\n1236\tclass\t2||1236\tBacteria||Gammaproteobacteria\t100\n")
    ok, errors, _w, _s = validator.validate_bioboxes(f)
    assert ok, errors
    f2 = write(tmp_path / "mismatch.bioboxes", HEADER.format(sid="s") +
               "@@TAXID\tRANK\tTAXPATH\tTAXPATHSN\tPERCENTAGE\n1236\tclass\t2|1224|999\tBacteria|P|G\t100\n")
    ok, errors, _w, _s = validator.validate_bioboxes(f2)
    assert not ok and any("does not match TAXID" in e for e in errors)


def test_multi_sample_and_expected_sample_ids(validator, tmp_path):
    block = "@@TAXID\tRANK\tTAXPATH\tTAXPATHSN\tPERCENTAGE\n2\tsuperkingdom\t2\tBacteria\t100\n"
    f = write(tmp_path / "multi.bioboxes", HEADER.format(sid="a") + block + "\n" + HEADER.format(sid="b") + block)
    ok, errors, _w, stats = validator.validate_bioboxes(f, expected_samples=["a", "b"])
    assert ok, errors
    assert stats["samples"] == ["a", "b"]
    ok, errors, _w, _s = validator.validate_bioboxes(f, expected_samples=["c"])
    assert not ok and any("not present" in e for e in errors)


def test_unsupported_rank_and_duplicate_taxid(validator, tmp_path):
    f = write(tmp_path / "ranks.bioboxes", HEADER.format(sid="s") +
              "@@TAXID\tRANK\tTAXPATH\tTAXPATHSN\tPERCENTAGE\n1\tno rank\t1\troot\t50\n2\tsuperkingdom\t2\tBacteria\t25\n2\tsuperkingdom\t2\tBacteria\t25\n")
    ok, errors, _w, _s = validator.validate_bioboxes(f)
    assert not ok
    assert any("unsupported by OPAL" in e for e in errors)
    assert any("more than once" in e for e in errors)


# --------------------------------------------------------------------------- fixer
def test_fill_higher_ranks_from_species_and_strain(fixer, ete3_db, tmp_path):
    truth = write(tmp_path / "truth.tsv", HEADER.format(sid="demo") +
                  "@@TAXID\tRANK\tPERCENTAGE\n264\tstrain\t30\n119857\tstrain\t45\n622488\tspecies\t20\n2173\tspecies\t5\n")
    out = tmp_path / "gs.bioboxes"
    fixer.fix_gold_standard(truth, out, None, fixer.DEFAULT_RANKS, None, ete3_db,
                            fill_higher=True, renormalise=False, taxonomy_db="NCBI", version="0.9.1")
    headers, rows = read_profile(out)
    assert headers["SampleID"] == "demo"
    sums = rank_sums(rows)
    # strains of F. tularensis (263) fill the species level: 30 + 45 + 20 + 5 = 100
    assert sums["species"] == pytest.approx(100.0)
    assert sums["superkingdom"] == pytest.approx(100.0)
    species = {r["TAXID"]: float(r["PERCENTAGE"]) for r in rows if r["RANK"] == "species"}
    assert species["263"] == pytest.approx(75.0)
    # strain rank only partially covered
    assert sums["strain"] == pytest.approx(75.0)
    sk = {r["TAXID"]: float(r["PERCENTAGE"]) for r in rows if r["RANK"] == "superkingdom"}
    assert sk == {"2": pytest.approx(95.0), "2157": pytest.approx(5.0)}


def test_renormalise_is_per_rank(fixer, ete3_db, tmp_path):
    src = write(tmp_path / "scaled.tsv", HEADER.format(sid="s") +
                "@@TAXID\tRANK\tPERCENTAGE\n2\tsuperkingdom\t50\n562\tspecies\t10\n1280\tspecies\t30\n")
    out = tmp_path / "gs.bioboxes"
    fixer.fix_gold_standard(src, out, "s", fixer.DEFAULT_RANKS, None, ete3_db,
                            fill_higher=False, renormalise=True, taxonomy_db="NCBI", version="0.9.1")
    _, rows = read_profile(out)
    sums = rank_sums(rows)
    assert sums["superkingdom"] == pytest.approx(100.0)
    assert sums["species"] == pytest.approx(100.0)
    species = {r["TAXID"]: float(r["PERCENTAGE"]) for r in rows if r["RANK"] == "species"}
    assert species["562"] == pytest.approx(25.0) and species["1280"] == pytest.approx(75.0)


def test_substrain_is_aggregated_into_strain_and_unknown_dropped(fixer, ete3_db, tmp_path):
    # 401614 is a sub-strain under strain 264 in the reduced taxonomy; 999999 is unknown
    src = write(tmp_path / "sub.tsv", HEADER.format(sid="s") +
                "@@TAXID\tRANK\tPERCENTAGE\n401614\tstrain\t60\n264\tstrain\t40\n999999\tspecies\t5\n")
    out = tmp_path / "gs.bioboxes"
    fixer.fix_gold_standard(src, out, "s", fixer.DEFAULT_RANKS, None, ete3_db,
                            fill_higher=False, renormalise=False, taxonomy_db="NCBI", version="0.9.1")
    _, rows = read_profile(out)
    strains = {r["TAXID"]: float(r["PERCENTAGE"]) for r in rows if r["RANK"] == "strain"}
    assert strains == {"264": pytest.approx(100.0)}
    assert not any(r["TAXID"] == "999999" for r in rows)


def test_fixed_file_passes_validator(fixer, validator, ete3_db, tmp_path):
    src = write(tmp_path / "t.tsv", HEADER.format(sid="s") + "@@TAXID\tRANK\tPERCENTAGE\n562\tspecies\t70\n1280\tspecies\t30\n")
    out = tmp_path / "gs.bioboxes"
    fixer.fix_gold_standard(src, out, "s", fixer.DEFAULT_RANKS, None, ete3_db,
                            fill_higher=True, renormalise=False, taxonomy_db="NCBI", version="0.9.1")
    ok, errors, _w, _s = validator.validate_bioboxes(out, expected_samples=["s"])
    assert ok, errors
