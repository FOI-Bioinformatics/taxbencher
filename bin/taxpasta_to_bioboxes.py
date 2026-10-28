#!/usr/bin/env python3
"""
Convert a taxpasta standardised profile to the CAMI profiling (Bioboxes) format.

The CAMI profiling format used by OPAL describes, for every taxonomic rank
listed in the ``@Ranks`` header, the relative abundance of each taxon at that
rank.  Abundances within one rank therefore sum to (at most) 100 %.

taxpasta profiles contain one ``count`` per taxonomy ID.  Depending on the
profiler these counts have different semantics, which this script handles via
``--abundance-mode``:

* ``direct`` (default; Kraken2, Centrifuge, Kaiju, KrakenUniq, Bracken, ganon,
  KMCP, DIAMOND, MEGAN6, mOTUs): the count is the number of reads assigned
  *directly* to that taxon.  Clade abundances are obtained by summing the
  counts of a taxon and all of its descendants.
* ``clade`` (MetaPhlAn): the value already is the cumulative clade abundance
  of the taxon (MetaPhlAn reports every level of the lineage), so values are
  used as-is and must not be summed again.

Percentages are expressed relative to all *classified* reads (taxonomy ID 0 is
treated as unclassified and excluded from the denominator unless
``--include-unclassified`` is given).

Lineage information is taken, in order of preference, from

1. taxpasta lineage columns (``id_lineage`` and ``rank_lineage``, optionally
   ``lineage``), produced with
   ``taxpasta standardise --add-id-lineage --add-rank-lineage --add-lineage``;
2. the NCBI taxonomy via ete3, either from a local ``taxdump.tar.gz``
   (``--taxdump``, recommended for reproducibility) or from the ete3 default
   database (downloaded from NCBI on first use).

TAXPATH/TAXPATHSN are restricted to the ranks in ``@Ranks`` (empty fields for
ranks missing from a lineage), which is what OPAL expects for its tree based
metrics.

Author: taxbencher pipeline
"""

import argparse
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd

__version__ = "2.0.0"

DEFAULT_RANKS = "superkingdom|phylum|class|order|family|genus|species|strain"

# Non-standard rank names that map onto CAMI ranks.
# NCBI (2025+) uses "domain" for Bacteria/Archaea/Eukaryota; older dumps use
# "superkingdom".  "kingdom" (e.g. Pseudomonadati) is deliberately NOT mapped:
# it is a level between superkingdom and phylum and would double count.
RANK_ALIASES = {
    "domain": "superkingdom",
    "subspecies": "strain",
}

# Ranks that may hold strain-level entries below species in NCBI
BELOW_SPECIES_RANKS = {"strain", "subspecies", "no rank", "isolate", "serotype",
                       "serogroup", "biotype", "genotype", "pathogroup",
                       "forma specialis", "varietas", "forma", "clade"}

UNCLASSIFIED_TAXID = 0


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


class Lineage:
    """Ordered lineage from root to the taxon itself: lists of taxids, ranks, names."""

    __slots__ = ("taxids", "ranks", "names")

    def __init__(self, taxids: Sequence[int], ranks: Sequence[str], names: Sequence[str]):
        self.taxids = list(taxids)
        self.ranks = list(ranks)
        self.names = list(names)


class LineageColumnResolver:
    """Resolve lineages from taxpasta ``id_lineage``/``rank_lineage``/``lineage`` columns."""

    SEP = ";"

    def __init__(self, df: pd.DataFrame):
        self._cache: Dict[int, Optional[Lineage]] = {}
        has_names = "lineage" in df.columns
        for _, row in df.iterrows():
            try:
                taxid = int(row["taxonomy_id"])
            except (TypeError, ValueError):
                continue
            ids = str(row["id_lineage"]) if pd.notna(row["id_lineage"]) else ""
            ranks = str(row["rank_lineage"]) if pd.notna(row["rank_lineage"]) else ""
            if not ids or not ranks:
                self._cache[taxid] = None
                continue
            id_list = [int(x) for x in ids.split(self.SEP) if x != ""]
            rank_list = ranks.split(self.SEP)
            if has_names and pd.notna(row["lineage"]):
                name_list = str(row["lineage"]).split(self.SEP)
            else:
                name_list = [f"taxid_{t}" for t in id_list]
            if not (len(id_list) == len(rank_list) == len(name_list)):
                logging.warning(f"Inconsistent lineage columns for taxid {taxid}; ignoring entry")
                self._cache[taxid] = None
                continue
            self._cache[taxid] = Lineage(id_list, rank_list, name_list)

    def resolve(self, taxid: int) -> Optional[Lineage]:
        return self._cache.get(taxid)

    @staticmethod
    def available(df: pd.DataFrame) -> bool:
        return {"id_lineage", "rank_lineage"}.issubset(df.columns)


class Ete3Resolver:
    """Resolve lineages with ete3's NCBITaxa."""

    def __init__(self, taxdump: Optional[Path] = None, dbfile: Optional[Path] = None):
        try:
            from ete3 import NCBITaxa  # noqa: WPS433
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise RuntimeError("ete3 is required for taxonomy lookups but is not installed") from exc

        kwargs = {}
        if dbfile is not None:
            kwargs["dbfile"] = str(dbfile)
        if taxdump is not None:
            if not Path(taxdump).exists():
                raise RuntimeError(f"taxdump file not found: {taxdump}")
            kwargs["taxdump_file"] = str(taxdump)
            if dbfile is None:
                # Build the database next to the output instead of in $HOME,
                # which may be read-only inside containers.
                kwargs["dbfile"] = str(Path.cwd() / "taxa.sqlite")
        logging.info(
            "Initialising NCBI taxonomy via ete3"
            + (f" from {taxdump}" if taxdump else " (default database; downloads from NCBI if absent)")
        )
        self._ncbi = NCBITaxa(**kwargs)
        self._cache: Dict[int, Optional[Lineage]] = {}

    def resolve(self, taxid: int) -> Optional[Lineage]:
        if taxid in self._cache:
            return self._cache[taxid]
        try:
            lineage_ids = self._ncbi.get_lineage(taxid)
        except Exception as exc:  # ete3 raises ValueError for unknown taxids
            logging.debug(f"taxid {taxid} not found in taxonomy: {exc}")
            self._cache[taxid] = None
            return None
        if not lineage_ids:
            self._cache[taxid] = None
            return None
        ranks = self._ncbi.get_rank(lineage_ids)
        names = self._ncbi.get_taxid_translator(lineage_ids)
        lineage = Lineage(
            lineage_ids,
            [ranks.get(t, "no rank") for t in lineage_ids],
            [names.get(t, f"taxid_{t}") for t in lineage_ids],
        )
        self._cache[taxid] = lineage
        return lineage


def normalise_rank(rank: str) -> str:
    rank = (rank or "").strip().lower()
    return RANK_ALIASES.get(rank, rank)


def select_rank_nodes(lineage: Lineage, ranks: List[str]) -> Dict[str, Tuple[int, str]]:
    """
    Pick, for every requested rank, the single lineage node representing it.

    Returns mapping rank -> (taxid, name).  For ``strain`` the deepest node
    below the species node is used when no node carries an explicit
    strain/subspecies rank (CAMI convention for NCBI "no rank" strains).
    """
    selected: Dict[str, Tuple[int, str]] = {}
    species_index = None
    for idx, (tid, rank, name) in enumerate(zip(lineage.taxids, lineage.ranks, lineage.names)):
        nrank = normalise_rank(rank)
        if nrank in ranks and nrank not in selected:
            selected[nrank] = (tid, name)
        if nrank == "species":
            species_index = idx

    if "strain" in ranks and "strain" not in selected and species_index is not None:
        # deepest node below species whose rank is a strain-like rank
        for idx in range(len(lineage.taxids) - 1, species_index, -1):
            if normalise_rank(lineage.ranks[idx]) in BELOW_SPECIES_RANKS:
                selected["strain"] = (lineage.taxids[idx], lineage.names[idx])
                break
    return selected


def read_profile(input_file: Path) -> pd.DataFrame:
    try:
        df = pd.read_csv(input_file, sep="\t", dtype={"taxonomy_id": str}, comment=None)
    except pd.errors.EmptyDataError:
        logging.error(f"Input file is empty: {input_file}")
        sys.exit(1)
    except Exception as exc:
        logging.error(f"Error reading input file: {exc}")
        sys.exit(1)

    missing = {"taxonomy_id", "count"} - set(df.columns)
    if missing:
        logging.error(
            f"Input file must contain 'taxonomy_id' and 'count' columns "
            f"(missing: {', '.join(sorted(missing))}; found: {', '.join(df.columns)})"
        )
        sys.exit(1)

    df = df.dropna(subset=["taxonomy_id", "count"]).copy()
    df["count"] = pd.to_numeric(df["count"], errors="coerce")
    df = df.dropna(subset=["count"])
    df["taxonomy_id"] = pd.to_numeric(df["taxonomy_id"], errors="coerce")
    bad = df["taxonomy_id"].isna().sum()
    if bad:
        logging.warning(f"Skipping {bad} rows with non-integer taxonomy_id")
    df = df.dropna(subset=["taxonomy_id"])
    df["taxonomy_id"] = df["taxonomy_id"].astype(int)
    negative = (df["count"] < 0).sum()
    if negative:
        logging.warning(f"Skipping {negative} rows with negative counts")
    df = df[df["count"] >= 0]
    return df


def convert_taxpasta_to_bioboxes(
    input_file: Path,
    output_file: Path,
    sample_id: str,
    ranks: List[str],
    taxonomy_db: str = "NCBI",
    version: str = "0.9.1",
    abundance_mode: str = "direct",
    include_unclassified: bool = False,
    use_ete3: bool = True,
    taxdump: Optional[Path] = None,
    ete3_db: Optional[Path] = None,
    allow_empty: bool = False,
    min_percentage: float = 0.0,
) -> int:
    """Convert and write the Bioboxes file. Returns the number of rows written."""
    logging.info(f"Reading taxpasta file: {input_file}")
    df = read_profile(input_file)

    # Collapse duplicated taxonomy IDs (should not happen in taxpasta output)
    if df["taxonomy_id"].duplicated().any():
        dups = int(df["taxonomy_id"].duplicated().sum())
        logging.warning(f"Summing counts of {dups} duplicated taxonomy_id rows")
        agg = df.groupby("taxonomy_id", as_index=False)["count"].sum()
        df = df.drop(columns=["count"]).drop_duplicates("taxonomy_id").merge(agg, on="taxonomy_id")

    # Choose taxonomy source
    if LineageColumnResolver.available(df):
        logging.info("Using lineage columns from taxpasta output for taxonomy")
        resolver = LineageColumnResolver(df)
    else:
        if taxonomy_db.upper() != "NCBI":
            raise RuntimeError(
                f"taxonomy_db={taxonomy_db!r} requires taxpasta lineage columns "
                "(id_lineage/rank_lineage); only NCBI can be resolved via ete3"
            )
        if not use_ete3:
            raise RuntimeError(
                "No lineage columns in input and ete3 lookups disabled (--no-ete3); "
                "cannot build a CAMI profile without taxonomy information"
            )
        resolver = Ete3Resolver(taxdump=taxdump, dbfile=ete3_db)

    unclassified = float(df.loc[df["taxonomy_id"] == UNCLASSIFIED_TAXID, "count"].sum())
    classified_df = df[(df["taxonomy_id"] != UNCLASSIFIED_TAXID) & (df["count"] > 0)]
    total_classified = float(classified_df["count"].sum())

    # rank -> taxid -> (abundance, name, taxpath, taxpathsn)
    abundance: Dict[str, Dict[int, float]] = defaultdict(lambda: defaultdict(float))
    node_info: Dict[Tuple[str, int], Tuple[str, str, str]] = {}
    unresolved_count = 0.0
    unresolved_taxa: List[int] = []
    above_rank_count = 0.0
    top_level_total = 0.0  # clade mode denominator
    ignored_ranks: Dict[str, int] = defaultdict(int)

    for taxid, count in zip(classified_df["taxonomy_id"], classified_df["count"]):
        count = float(count)
        lineage = resolver.resolve(int(taxid))
        if lineage is None:
            unresolved_count += count
            unresolved_taxa.append(int(taxid))
            continue

        selected = select_rank_nodes(lineage, ranks)

        def path_for(rank: str) -> Tuple[str, str]:
            idx = ranks.index(rank)
            ids, names = [], []
            for r in ranks[: idx + 1]:
                if r in selected:
                    ids.append(str(selected[r][0]))
                    names.append(selected[r][1])
                else:
                    ids.append("")
                    names.append("")
            return "|".join(ids), "|".join(names)

        if abundance_mode == "direct":
            if not selected:
                above_rank_count += count  # e.g. root / cellular organisms
            for rank, (node_taxid, node_name) in selected.items():
                abundance[rank][node_taxid] += count
                if (rank, node_taxid) not in node_info:
                    node_info[(rank, node_taxid)] = (node_name, *path_for(rank))
        else:  # clade mode: use the taxon's own value only
            own_rank = normalise_rank(lineage.ranks[-1])
            own_taxid = lineage.taxids[-1]
            if own_rank not in ranks:
                # NCBI "no rank" strain-like node below species -> strain
                if "strain" in selected and selected["strain"][0] == own_taxid:
                    own_rank = "strain"
                else:
                    ignored_ranks[own_rank or "none"] += 1
                    continue
            # top level nodes (no selected ancestor above own rank) define the denominator
            rank_idx = ranks.index(own_rank)
            if not any(r in selected for r in ranks[:rank_idx]):
                top_level_total += count
            abundance[own_rank][own_taxid] += count
            node_info[(own_rank, own_taxid)] = (selected[own_rank][1], *path_for(own_rank))

    if abundance_mode == "direct":
        denominator = total_classified + (unclassified if include_unclassified else 0.0)
    else:
        denominator = top_level_total + (unclassified if include_unclassified else 0.0)
        if top_level_total <= 0 and classified_df.shape[0] > 0:
            logging.warning("clade mode: no top-level taxa found; falling back to sum of all values")
            denominator = total_classified

    if unresolved_taxa:
        shown = ", ".join(str(t) for t in unresolved_taxa[:10])
        more = f" (+{len(unresolved_taxa) - 10} more)" if len(unresolved_taxa) > 10 else ""
        pct = (unresolved_count / denominator * 100) if denominator > 0 else 0
        logging.warning(
            f"{len(unresolved_taxa)} taxonomy IDs not found in taxonomy and skipped "
            f"({pct:.2f}% of classified abundance): {shown}{more}"
        )
    if above_rank_count:
        logging.info(
            f"{above_rank_count:g} counts assigned above the highest requested rank "
            f"(e.g. root) contribute to the denominator only"
        )
    if ignored_ranks:
        logging.info(f"clade mode: ignored entries with ranks outside @Ranks: {dict(ignored_ranks)}")
    if unclassified:
        logging.info(
            f"Unclassified (taxid 0) counts: {unclassified:g} "
            f"({'included in' if include_unclassified else 'excluded from'} denominator)"
        )

    # Assemble rows in @Ranks order, most abundant first within a rank
    rows = []
    for rank in ranks:
        for node_taxid, value in sorted(abundance[rank].items(), key=lambda kv: (-kv[1], kv[0])):
            pct = (value / denominator * 100.0) if denominator > 0 else 0.0
            if pct <= 0 or pct < min_percentage:
                continue
            name, taxpath, taxpathsn = node_info[(rank, node_taxid)]
            rows.append((node_taxid, rank, taxpath, taxpathsn, pct))

    if not rows and not allow_empty:
        raise RuntimeError(
            "No taxa could be placed on the requested ranks; the output would be an empty profile. "
            "Check that the taxonomy database matches the profile (unresolved taxids above) "
            "or pass --allow-empty to write a header-only file."
        )

    rank_sums = defaultdict(float)
    for _, rank, _, _, pct in rows:
        rank_sums[rank] += pct
    logging.info("Per-rank abundance sums: " + ", ".join(f"{r}={rank_sums[r]:.2f}%" for r in ranks if r in rank_sums))
    too_high = {r: round(s, 3) for r, s in rank_sums.items() if s > 100.0 + 1e-3}
    if too_high:
        raise RuntimeError(
            f"Per-rank abundances exceed 100%: {too_high}. In '{abundance_mode}' mode this means the "
            f"input counts do not have the assumed semantics (clade mode expects cumulative clade values "
            f"as reported by MetaPhlAn; direct mode expects reads assigned directly to each taxon). "
            f"Re-run with the other --abundance-mode."
        )

    logging.info(f"Writing Bioboxes file: {output_file}")
    with open(output_file, "w") as handle:
        handle.write(f"@SampleID:{sample_id}\n")
        handle.write(f"@Version:{version}\n")
        handle.write(f"@Ranks:{'|'.join(ranks)}\n")
        handle.write(f"@TaxonomyID:{taxonomy_db}\n")
        handle.write("@@TAXID\tRANK\tTAXPATH\tTAXPATHSN\tPERCENTAGE\n")
        for node_taxid, rank, taxpath, taxpathsn, pct in rows:
            handle.write(f"{node_taxid}\t{rank}\t{taxpath}\t{taxpathsn}\t{pct:.6f}\n")

    logging.info(f"Successfully wrote {len(rows)} entries across {len(rank_sums)} ranks")
    return len(rows)


def parse_ranks(value: str) -> List[str]:
    sep = "|" if "|" in value else ","
    ranks = [normalise_rank(r) for r in value.split(sep) if r.strip()]
    if not ranks:
        raise argparse.ArgumentTypeError("At least one rank is required")
    if len(set(ranks)) != len(ranks):
        raise argparse.ArgumentTypeError(f"Duplicate ranks in {value!r}")
    return ranks


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a taxpasta standardised profile to CAMI Bioboxes profiling format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Kraken2 profile (direct read counts), taxonomy from a pinned taxdump
  taxpasta_to_bioboxes.py -i kraken2.tsv -o kraken2.bioboxes -s sample_1 --taxdump taxdump.tar.gz

  # MetaPhlAn profile (clade-cumulative relative abundances)
  taxpasta_to_bioboxes.py -i metaphlan.tsv -o metaphlan.bioboxes -s sample_1 --abundance-mode clade

  # Profile with taxpasta lineage columns (no ete3 needed)
  taxpasta standardise -p kraken2 --taxonomy taxdump_dir --add-id-lineage --add-rank-lineage --add-lineage ...
  taxpasta_to_bioboxes.py -i kraken2_lineage.tsv -o kraken2.bioboxes -s sample_1 --no-ete3
        """,
    )
    parser.add_argument("-i", "--input", type=Path, required=True, help="Input taxpasta TSV file")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output Bioboxes file")
    parser.add_argument("-s", "--sample-id", type=str, required=True,
                        help="Sample identifier (must match the gold standard @SampleID)")
    parser.add_argument("-r", "--ranks", type=parse_ranks, default=parse_ranks(DEFAULT_RANKS),
                        help=f"Taxonomic ranks, pipe- or comma-separated (default: {DEFAULT_RANKS})")
    parser.add_argument("-d", "--taxonomy-db", type=str, default="NCBI",
                        help="Taxonomy database name written to @TaxonomyID (default: NCBI)")
    parser.add_argument("--version-bioboxes", type=str, default="0.9.1",
                        help="Bioboxes format version (default: 0.9.1)")
    parser.add_argument("--abundance-mode", choices=["direct", "clade"], default="direct",
                        help="'direct': counts are reads assigned directly to the taxon and are summed "
                             "over descendants (Kraken2, Centrifuge, ...); 'clade': values are already "
                             "cumulative clade abundances (MetaPhlAn). Default: direct")
    parser.add_argument("--include-unclassified", action="store_true",
                        help="Include unclassified counts (taxid 0) in the denominator so percentages "
                             "are relative to all reads instead of classified reads")
    parser.add_argument("--min-percentage", type=float, default=0.0,
                        help="Drop entries below this percentage (default: 0, keep all non-zero)")
    parser.add_argument("--taxdump", type=Path, default=None,
                        help="NCBI taxdump.tar.gz to build the ete3 database from (recommended)")
    parser.add_argument("--ete3-db", type=Path, default=None,
                        help="Path of the ete3 sqlite database to use/create")
    parser.add_argument("--no-ete3", action="store_true",
                        help="Disable ete3 lookups; requires taxpasta lineage columns in the input")
    parser.add_argument("--allow-empty", action="store_true",
                        help="Write a header-only file instead of failing when no taxa can be placed")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    args = parser.parse_args()
    setup_logging(args.verbose)

    if not args.input.exists():
        logging.error(f"Input file does not exist: {args.input}")
        sys.exit(1)

    try:
        convert_taxpasta_to_bioboxes(
            input_file=args.input,
            output_file=args.output,
            sample_id=args.sample_id,
            ranks=args.ranks,
            taxonomy_db=args.taxonomy_db,
            version=args.version_bioboxes,
            abundance_mode=args.abundance_mode,
            include_unclassified=args.include_unclassified,
            use_ete3=not args.no_ete3,
            taxdump=args.taxdump,
            ete3_db=args.ete3_db,
            allow_empty=args.allow_empty,
            min_percentage=args.min_percentage,
        )
        logging.info("Conversion completed successfully")
    except Exception as exc:
        logging.error(f"Conversion failed: {exc}")
        if args.verbose:
            raise
        sys.exit(1)


if __name__ == "__main__":
    main()
