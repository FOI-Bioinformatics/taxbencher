#!/usr/bin/env python3
"""
Convert taxpasta standardized format to CAMI Bioboxes profiling format.

This script converts taxonomic profiling results from taxpasta's standardized
TSV format (columns: taxonomy_id, count) to the CAMI Bioboxes format required
for OPAL evaluation.

Taxonomy resolution (rank and lineage) uses taxopy, the same library that
taxpasta uses internally. taxopy reads an offline NCBI taxdump (nodes.dmp and
names.dmp) supplied with --taxonomy, so the conversion is fully reproducible and
requires no network access at runtime.

Author: taxbencher pipeline
"""

import argparse
import csv
import logging
import sys
from pathlib import Path

try:
    import taxopy
    HAS_TAXOPY = True
except ImportError:
    HAS_TAXOPY = False


# Standard CAMI ranks supported by OPAL.
VALID_RANKS = {
    "superkingdom", "phylum", "class", "order",
    "family", "genus", "species", "strain",
}

# Map non-standard ranks onto the supported CAMI ranks.
RANK_MAPPING = {
    "subspecies": "strain",
    "domain": "superkingdom",
    "kingdom": "superkingdom",
}


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_taxonomy(taxonomy_dir: Path) -> "taxopy.TaxDb":
    """
    Load a taxopy taxonomy database from a directory of NCBI taxdump files.

    Args:
        taxonomy_dir: Directory containing at least nodes.dmp and names.dmp.

    Returns:
        A taxopy.TaxDb instance.
    """
    if not HAS_TAXOPY:
        raise RuntimeError(
            "taxopy is not installed but is required for taxonomy resolution. "
            "Install taxopy (e.g. 'conda install -c bioconda taxopy')."
        )

    nodes = taxonomy_dir / "nodes.dmp"
    names = taxonomy_dir / "names.dmp"
    missing = [str(p) for p in (nodes, names) if not p.exists()]
    if missing:
        raise FileNotFoundError(
            f"Taxonomy directory '{taxonomy_dir}' is missing required taxdump "
            f"file(s): {', '.join(missing)}. Provide a directory containing the "
            f"NCBI taxdump (at least nodes.dmp and names.dmp)."
        )

    logging.info("Loading taxonomy database from %s", taxonomy_dir)
    return taxopy.TaxDb(nodes_dmp=str(nodes), names_dmp=str(names), keep_files=True)


def read_taxpasta_tsv(input_file: Path) -> list[tuple[int, float]]:
    """
    Read a taxpasta standardized TSV (columns taxonomy_id, count).

    Rows with a missing/non-integer taxonomy_id, a non-numeric count, or a count
    of zero or less are skipped. Uses only the standard library so the converter
    has no pandas dependency.

    Returns:
        List of (taxonomy_id, count) tuples.
    """
    try:
        with open(input_file, newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            fieldnames = reader.fieldnames or []
            if "taxonomy_id" not in fieldnames or "count" not in fieldnames:
                logging.error("Input file must contain 'taxonomy_id' and 'count' columns")
                sys.exit(1)

            rows: list[tuple[int, float]] = []
            for record in reader:
                raw_taxid = (record.get("taxonomy_id") or "").strip()
                raw_count = (record.get("count") or "").strip()
                if not raw_taxid or not raw_count:
                    continue
                try:
                    taxid = int(raw_taxid)
                except ValueError:
                    logging.warning("Invalid taxonomy_id: %s, skipping", raw_taxid)
                    continue
                try:
                    count = float(raw_count)
                except ValueError:
                    logging.warning("Invalid count for taxid %s: %s, skipping", raw_taxid, raw_count)
                    continue
                if count > 0:
                    rows.append((taxid, count))
            return rows
    except OSError as exc:
        logging.error("Error reading input file: %s", exc)
        sys.exit(1)


def get_taxonomy_info(
    taxid: int, taxdb: "taxopy.TaxDb"
) -> tuple[str, str, str] | None:
    """
    Resolve rank and full lineage for a taxid using taxopy.

    Args:
        taxid: NCBI taxonomy ID.
        taxdb: taxopy taxonomy database.

    Returns:
        Tuple of (rank, taxpath, taxpathsn) where taxpath/taxpathsn are
        pipe-separated lineages ordered from root to the taxon, or None if the
        taxid is not present in the taxonomy.
    """
    try:
        taxon = taxopy.Taxon(taxid, taxdb)
    except Exception as exc:  # taxopy raises TaxidError for unknown taxids
        logging.warning("Could not resolve taxid %s: %s", taxid, exc)
        return None

    rank = taxon.rank or "unknown"
    # taxopy lineages are leaf-first and include the root; CAMI Bioboxes expects
    # the path ordered from root down to the taxon.
    taxid_lineage = [str(t) for t in reversed(taxon.taxid_lineage)]
    name_lineage = list(reversed(taxon.name_lineage))

    taxpath = "|".join(taxid_lineage)
    taxpathsn = "|".join(name_lineage)
    return rank, taxpath, taxpathsn


def convert_taxpasta_to_bioboxes(
    input_file: Path,
    output_file: Path,
    sample_id: str,
    ranks: list[str],
    taxonomy_dir: Path,
    taxonomy_db: str = "NCBI",
    version: str = "0.9.1",
) -> int:
    """
    Convert taxpasta format to CAMI Bioboxes format.

    Args:
        input_file: Path to taxpasta TSV file.
        output_file: Path to output Bioboxes file.
        sample_id: Sample identifier.
        ranks: List of taxonomic ranks to include in the header.
        taxonomy_dir: Directory with NCBI taxdump files for taxopy.
        taxonomy_db: Taxonomy database name (default: NCBI).
        version: Bioboxes format version (default: 0.9.1).

    Returns:
        Number of entries written.
    """
    logging.info("Reading taxpasta file: %s", input_file)

    rows = read_taxpasta_tsv(input_file)
    if len(rows) == 0:
        logging.warning("No valid data found in input file")

    total_counts = sum(count for _taxid, count in rows)

    taxdb = load_taxonomy(taxonomy_dir)

    results = []
    skipped_ranks = set()
    unresolved = 0
    for taxid, count in rows:
        percentage = (count / total_counts * 100) if total_counts > 0 else 0

        info = get_taxonomy_info(taxid, taxdb)
        if info is None:
            unresolved += 1
            continue
        rank, taxpath, taxpathsn = info

        # Skip unsupported ranks (root, no rank, etc.).
        if rank not in VALID_RANKS and rank not in RANK_MAPPING:
            skipped_ranks.add(rank)
            continue

        if rank in RANK_MAPPING:
            rank = RANK_MAPPING[rank]

        results.append({
            "TAXID": taxid,
            "RANK": rank,
            "TAXPATH": taxpath,
            "TAXPATHSN": taxpathsn,
            "PERCENTAGE": f"{percentage:.6f}",
        })

    if skipped_ranks:
        logging.info(
            "Skipped %d unsupported ranks: %s",
            len(skipped_ranks), ", ".join(sorted(skipped_ranks)),
        )
    if unresolved:
        logging.warning("Skipped %d taxa not found in the taxonomy", unresolved)

    # Fail loudly if nothing usable was produced. Emitting a headers-only Bioboxes
    # file would silently break the downstream OPAL evaluation.
    if len(results) == 0:
        logging.error(
            "No taxa could be converted. None of the input taxa resolved to a "
            "supported OPAL rank (superkingdom, phylum, class, order, family, "
            "genus, species, strain). Check that the input profile contains "
            "ranked taxa and that the taxonomy database in '%s' covers them.",
            taxonomy_dir,
        )
        sys.exit(1)

    # Renormalize percentages to sum to 100%.
    total_percentage = sum(float(r["PERCENTAGE"]) for r in results)
    if total_percentage > 0 and abs(total_percentage - 100.0) > 0.01:
        logging.info("Renormalizing percentages (current sum: %.2f%%)", total_percentage)
        for result in results:
            result["PERCENTAGE"] = f"{float(result['PERCENTAGE']) / total_percentage * 100:.6f}"

    logging.info("Writing Bioboxes file: %s", output_file)
    ranks_header = ranks if isinstance(ranks, str) else "|".join(ranks)
    with open(output_file, "w") as f:
        f.write(f"@SampleID:{sample_id}\n")
        f.write(f"@Version:{version}\n")
        f.write(f"@Ranks:{ranks_header}\n")
        f.write(f"@TaxonomyID:{taxonomy_db}\n")
        f.write("@@TAXID\tRANK\tTAXPATH\tTAXPATHSN\tPERCENTAGE\n")
        for result in results:
            f.write(
                f"{result['TAXID']}\t"
                f"{result['RANK']}\t"
                f"{result['TAXPATH']}\t"
                f"{result['TAXPATHSN']}\t"
                f"{result['PERCENTAGE']}\n"
            )

    logging.info("Successfully converted %d entries", len(results))
    return len(results)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Convert taxpasta format to CAMI Bioboxes format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic conversion (requires an NCBI taxdump directory)
  taxpasta_to_bioboxes.py -i input.tsv -o output.bioboxes -s sample_1 \\
      --taxonomy /path/to/taxdump

  # With custom ranks
  taxpasta_to_bioboxes.py -i input.tsv -o output.bioboxes -s sample_1 \\
      --taxonomy /path/to/taxdump \\
      -r superkingdom,phylum,class,order,family,genus,species,strain
        """,
    )

    parser.add_argument("-i", "--input", type=Path, required=True, help="Input taxpasta TSV file")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output Bioboxes file")
    parser.add_argument("-s", "--sample-id", type=str, required=True, help="Sample identifier")
    parser.add_argument(
        "-t", "--taxonomy", type=Path, required=True,
        help="Directory containing NCBI taxdump files (at least nodes.dmp and names.dmp)",
    )
    parser.add_argument(
        "-r", "--ranks", type=str,
        default="superkingdom|phylum|class|order|family|genus|species|strain",
        help="Taxonomic ranks (pipe-separated)",
    )
    parser.add_argument("-d", "--taxonomy-db", type=str, default="NCBI", help="Taxonomy database name (default: NCBI)")
    parser.add_argument("--version-bioboxes", type=str, default="0.9.1", help="Bioboxes format version (default: 0.9.1)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--version", action="version", version="%(prog)s 2.0.0")

    args = parser.parse_args()
    setup_logging(args.verbose)

    if not args.input.exists():
        logging.error("Input file does not exist: %s", args.input)
        sys.exit(1)

    ranks = args.ranks if "|" in args.ranks else args.ranks.split(",")

    try:
        convert_taxpasta_to_bioboxes(
            input_file=args.input,
            output_file=args.output,
            sample_id=args.sample_id,
            ranks=ranks,
            taxonomy_dir=args.taxonomy,
            taxonomy_db=args.taxonomy_db,
            version=args.version_bioboxes,
        )
        logging.info("Conversion completed successfully")
    except SystemExit:
        raise
    except Exception as exc:
        logging.error("Conversion failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
