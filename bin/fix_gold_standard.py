#!/usr/bin/env python3
"""
Fix a gold standard bioboxes file by reconstructing proper TAXPATH and TAXPATHSN
from the taxonomy IDs, using taxopy and an offline NCBI taxdump.
"""

import argparse
from pathlib import Path

try:
    import taxopy
    HAS_TAXOPY = True
except ImportError:
    HAS_TAXOPY = False

VALID_RANKS = {
    "superkingdom", "phylum", "class", "order",
    "family", "genus", "species", "strain",
}
RANK_MAPPING = {"subspecies": "strain"}


def load_taxonomy(taxonomy_dir: Path) -> "taxopy.TaxDb":
    """Load a taxopy taxonomy database from a directory of NCBI taxdump files."""
    if not HAS_TAXOPY:
        raise RuntimeError(
            "taxopy is not installed but is required. "
            "Install it (e.g. 'conda install -c bioconda taxopy')."
        )
    nodes = taxonomy_dir / "nodes.dmp"
    names = taxonomy_dir / "names.dmp"
    missing = [str(p) for p in (nodes, names) if not p.exists()]
    if missing:
        raise FileNotFoundError(
            f"Taxonomy directory '{taxonomy_dir}' is missing: {', '.join(missing)}"
        )
    print(f"Loading taxonomy database from {taxonomy_dir}")
    return taxopy.TaxDb(nodes_dmp=str(nodes), names_dmp=str(names), keep_files=True)


def fix_gold_standard(input_file, output_file, taxonomy_dir, sample_id="gold_standard"):
    """Fix a gold standard file by reconstructing TAXPATH and TAXPATHSN from taxids."""
    taxdb = load_taxonomy(Path(taxonomy_dir))

    print(f"Reading input file: {input_file}")
    data_lines = []
    with open(input_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("@") or line.startswith("#"):
                continue
            data_lines.append(line)

    print(f"Processing {len(data_lines)} entries...")

    results = []
    skipped = 0
    for line in data_lines:
        parts = line.split("\t")
        # Accept either TAXID,RANK,PATH,PERCENTAGE or TAXID,RANK,TAXPATH,TAXPATHSN,PERCENTAGE
        if len(parts) == 4:
            taxid, rank, _path, percentage = parts
        elif len(parts) == 5:
            taxid, rank, _taxpath, _taxpathsn, percentage = parts
        else:
            print(f"Warning: Skipping malformed line: {line}")
            continue

        try:
            taxid = int(taxid)
        except ValueError:
            print(f"Warning: Skipping non-integer taxid: {taxid}")
            continue

        if rank not in VALID_RANKS and rank not in RANK_MAPPING:
            skipped += 1
            continue
        if rank in RANK_MAPPING:
            rank = RANK_MAPPING[rank]

        try:
            taxon = taxopy.Taxon(taxid, taxdb)
        except Exception as exc:
            print(f"Warning: No lineage found for taxid {taxid} ({exc}), skipping")
            continue

        # taxopy lineages are leaf-first incl. root; Bioboxes wants root-first.
        taxpath = "|".join(str(t) for t in reversed(taxon.taxid_lineage))
        taxpathsn = "|".join(reversed(taxon.name_lineage))

        results.append({
            "TAXID": taxid,
            "RANK": rank,
            "TAXPATH": taxpath,
            "TAXPATHSN": taxpathsn,
            "PERCENTAGE": percentage,
        })

    if skipped > 0:
        print(f"Skipped {skipped} entries with unsupported ranks (root, no rank, etc.)")

    total_percentage = sum(float(r["PERCENTAGE"]) for r in results)
    if total_percentage > 0 and abs(total_percentage - 100.0) > 0.01:
        print(f"Renormalizing percentages (current sum: {total_percentage:.2f}%)")
        for result in results:
            result["PERCENTAGE"] = f"{float(result['PERCENTAGE']) / total_percentage * 100:.6f}"

    print(f"Writing output file: {output_file}")
    with open(output_file, "w") as f:
        f.write(f"@SampleID:{sample_id}\n")
        f.write("@Version:0.9.1\n")
        f.write("@Ranks:superkingdom|phylum|class|order|family|genus|species|strain\n")
        f.write("@TaxonomyID:NCBI\n")
        f.write("@@TAXID\tRANK\tTAXPATH\tTAXPATHSN\tPERCENTAGE\n")
        for result in results:
            f.write(
                f"{result['TAXID']}\t"
                f"{result['RANK']}\t"
                f"{result['TAXPATH']}\t"
                f"{result['TAXPATHSN']}\t"
                f"{result['PERCENTAGE']}\n"
            )

    print(f"Successfully fixed {len(results)} entries")
    print(f"Output written to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Fix gold standard bioboxes file by reconstructing TAXPATH and TAXPATHSN"
    )
    parser.add_argument("-i", "--input", required=True, help="Input gold standard file")
    parser.add_argument("-o", "--output", required=True, help="Output fixed file")
    parser.add_argument(
        "-t", "--taxonomy", required=True,
        help="Directory containing NCBI taxdump files (at least nodes.dmp and names.dmp)",
    )
    parser.add_argument(
        "-s", "--sample-id", default="gold_standard",
        help="Sample ID for @SampleID header (default: gold_standard)",
    )
    args = parser.parse_args()
    fix_gold_standard(args.input, args.output, args.taxonomy, args.sample_id)


if __name__ == "__main__":
    main()
