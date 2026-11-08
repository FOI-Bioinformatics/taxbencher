#!/usr/bin/env python3
"""
Repair a gold standard (CAMI profiling / Bioboxes) file.

What it does
------------
* Reconstructs TAXPATH and TAXPATHSN from the NCBI taxonomy (taxopy) restricted
  to the CAMI ranks (one element per rank, empty for missing ranks).
* Drops or remaps ranks OPAL does not support (root, no rank, kingdom, ...).
* Optionally derives missing higher-rank entries from lower-rank ones
  (``--fill-higher-ranks``), e.g. when only species-level truth is available.
* Renormalises abundances *per rank* to 100 % (``--renormalise``), never
  across ranks: in the CAMI format every rank sums to 100 %.
* Accepts files with 3 (TAXID, RANK, PERCENTAGE), 4 or 5 columns and uses the
  @@ header when present.
* Multi-sample files (several @SampleID blocks) are repaired block by block and
  written back as separate blocks.
* Merged (outdated) taxonomy IDs are replaced by their current ID.

Usage:
    fix_gold_standard.py -i gold.bioboxes -o fixed.bioboxes -s sample_id \
        [--taxdump taxdump.tar.gz|taxdump_dir] [--fill-higher-ranks] [--renormalise]
"""

import argparse
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# shared taxonomy helpers live next to this script in bin/
sys.path.insert(0, str(Path(__file__).resolve().parent))
from taxbencher_taxonomy import TaxonomyResolver  # noqa: E402

DEFAULT_RANKS = ["superkingdom", "phylum", "class", "order", "family", "genus", "species", "strain"]
RANK_ALIASES = {"domain": "superkingdom", "subspecies": "strain"}
BELOW_SPECIES_RANKS = {"strain", "subspecies", "no rank", "isolate", "serotype", "serogroup", "biotype",
                       "genotype", "pathogroup", "forma specialis", "varietas", "forma", "clade"}


def normalise_rank(rank: str) -> str:
    rank = (rank or "").strip().lower()
    return RANK_ALIASES.get(rank, rank)


def load_taxonomy(taxdump: Optional[Path]) -> TaxonomyResolver:
    if taxdump and not Path(taxdump).exists():
        sys.exit(f"ERROR: taxdump not found: {taxdump}")
    print("Loading NCBI taxonomy..." + (f" from {taxdump}" if taxdump else " (downloading the current taxdump)"))
    try:
        return TaxonomyResolver(taxdump)
    except (OSError, ValueError, RuntimeError) as exc:
        sys.exit(f"ERROR: {exc}")


Row = Tuple[int, str, float]


def parse_input(path: Path) -> List[Tuple[Dict[str, str], List[Row]]]:
    """Return one (headers, rows) block per @SampleID, rows being (taxid, rank, percentage).

    Files without @SampleID lines give a single block. Rows with a non-finite or negative
    percentage are reported and skipped.
    """
    blocks: List[Tuple[Dict[str, str], List[Row]]] = []
    headers: Dict[str, str] = {}
    columns: List[str] = []
    rows: List[Row] = []
    skipped = 0
    with open(path) as handle:
        for lineno, raw in enumerate(handle, 1):
            line = raw.rstrip("\n").rstrip("\r")
            if not line.strip() or line.startswith("#"):
                continue
            if line.startswith("@@"):
                columns = [c.strip().upper() for c in line[2:].split("\t")]
                continue
            if line.startswith("@"):
                key, _, value = line[1:].partition(":")
                key = key.strip()
                if key.upper() == "SAMPLEID" and (rows or any(k.upper() == "SAMPLEID" for k in headers)):
                    blocks.append((headers, rows))  # a new sample block starts
                    headers, rows, columns = {}, [], []
                headers["SampleID" if key.upper() == "SAMPLEID" else key] = value.strip()
                continue
            parts = line.split("\t")
            try:
                if columns and {"TAXID", "RANK", "PERCENTAGE"}.issubset(columns):
                    taxid = parts[columns.index("TAXID")]
                    rank = parts[columns.index("RANK")]
                    pct = parts[columns.index("PERCENTAGE")]
                elif len(parts) >= 3:
                    taxid, rank, pct = parts[0], parts[1], parts[-1]
                else:
                    raise ValueError("too few columns")
                value = float(pct)
                if not math.isfinite(value) or value < 0:
                    raise ValueError(f"percentage {pct!r} is not a finite non-negative number")
                rows.append((int(taxid), rank.strip(), value))
            except (ValueError, IndexError) as exc:
                print(f"Warning: skipping malformed line {lineno}: {line!r} ({exc})")
                skipped += 1
    if rows or headers or not blocks:
        blocks.append((headers, rows))
    if skipped:
        print(f"Skipped {skipped} malformed lines")
    return blocks


def select_rank_nodes(taxonomy: TaxonomyResolver, taxid: int, ranks: List[str]) -> Optional[Dict[str, Tuple[int, str]]]:
    resolved = taxonomy.resolve(taxid)
    if resolved is None or not resolved.taxids:
        return None
    lineage = resolved.taxids
    rank_of = dict(zip(resolved.taxids, resolved.ranks))
    name_of = dict(zip(resolved.taxids, resolved.names))
    selected: Dict[str, Tuple[int, str]] = {}
    species_index = None
    for idx, tid in enumerate(lineage):
        nrank = normalise_rank(rank_of.get(tid, "no rank"))
        if nrank in ranks and nrank not in selected:
            selected[nrank] = (tid, name_of.get(tid, f"taxid_{tid}"))
        if nrank == "species":
            species_index = idx
    if "strain" in ranks and "strain" not in selected and species_index is not None:
        for idx in range(len(lineage) - 1, species_index, -1):
            if normalise_rank(rank_of.get(lineage[idx], "no rank")) in BELOW_SPECIES_RANKS:
                selected["strain"] = (lineage[idx], name_of.get(lineage[idx], f"taxid_{lineage[idx]}"))
                break
    return selected


def build_paths(selected: Dict[str, Tuple[int, str]], rank: str, ranks: List[str]) -> Tuple[str, str]:
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


def fix_gold_standard(input_file: Path, output_file: Path, sample_id: Optional[str], ranks: List[str],
                      taxdump: Optional[Path], fill_higher: bool,
                      renormalise: bool, taxonomy_db: str, version: str) -> None:
    blocks = [(headers, rows) for headers, rows in parse_input(input_file) if rows]
    if not blocks:
        sys.exit("ERROR: no data rows found in input")
    if sample_id and len(blocks) > 1:
        sys.exit(f"ERROR: --sample-id can only be used with single-sample input; {input_file} has "
                 f"{len(blocks)} @SampleID blocks")
    sample_ids = [sample_id or headers.get("SampleID") or "gold_standard" for headers, _ in blocks]
    duplicates = sorted({sid for sid in sample_ids if sample_ids.count(sid) > 1})
    if duplicates:
        sys.exit(f"ERROR: duplicate @SampleID blocks in {input_file}: {duplicates}")
    taxonomy = load_taxonomy(taxdump)

    written = 0
    with open(output_file, "w") as handle:
        for sid, (_, rows) in zip(sample_ids, blocks):
            out_rows = fix_sample(taxonomy, sid, rows, ranks, fill_higher, renormalise)
            handle.write(f"@SampleID:{sid}\n")
            handle.write(f"@Version:{version}\n")
            handle.write(f"@Ranks:{'|'.join(ranks)}\n")
            handle.write(f"@TaxonomyID:{taxonomy_db}\n")
            handle.write("@@TAXID\tRANK\tTAXPATH\tTAXPATHSN\tPERCENTAGE\n")
            for taxid, rank, taxpath, taxpathsn, pct in out_rows:
                handle.write(f"{taxid}\t{rank}\t{taxpath}\t{taxpathsn}\t{format_percentage(pct)}\n")
            if len(blocks) > 1:
                handle.write("\n")
            written += len(out_rows)
    print(f"Wrote {written} entries for {len(blocks)} sample(s) to {output_file}")


def format_percentage(pct: float) -> str:
    """Six decimals, but never round a non-zero abundance to 0 (OPAL drops 0.0 rows)."""
    text = f"{pct:.6f}"
    if pct > 0 and float(text) == 0.0:
        text = f"{pct:.6e}"
    return text


def fix_sample(taxonomy: TaxonomyResolver, sample_id: str, rows: List[Row], ranks: List[str], fill_higher: bool,
               renormalise: bool) -> List[Tuple[int, str, str, str, float]]:
    print(f"Processing {len(rows)} entries for sample '{sample_id}'...")

    # rank -> taxid -> percentage ; node info for TAXPATH
    abundance: Dict[str, Dict[int, float]] = defaultdict(lambda: defaultdict(float))
    node_info: Dict[Tuple[str, int], Tuple[str, str]] = {}
    dropped_ranks: Dict[str, int] = defaultdict(int)
    remapped: Dict[str, int] = defaultdict(int)
    unresolved: List[int] = []

    for taxid, rank, pct in rows:
        selected = select_rank_nodes(taxonomy, taxid, ranks)
        if selected is None:
            unresolved.append(taxid)
            continue
        nrank = normalise_rank(rank)
        if nrank not in ranks:
            # Try to interpret the taxon by its own NCBI rank instead of the stated one
            own = [r for r, (tid, _) in selected.items() if tid == taxid]
            if own:
                nrank = own[0]
            else:
                dropped_ranks[rank] += 1
                continue
        node_taxid = taxid
        if nrank not in selected or selected[nrank][0] != taxid:
            # Stated rank disagrees with the taxonomy. Prefer the taxon's own rank; otherwise
            # (e.g. a sub-strain node listed as 'strain') aggregate it into its ancestor at
            # the stated rank, which is how CAMI profiles represent taxa below the rank list.
            own = [r for r, (tid, _) in selected.items() if tid == taxid]
            if own:
                nrank = own[0]
            elif nrank in selected:
                remapped[f"{taxid} -> {selected[nrank][0]} ({nrank})"] += 1
                node_taxid = selected[nrank][0]
            else:
                dropped_ranks[f"{rank} (taxid {taxid} has no ancestor at that rank)"] += 1
                continue
        abundance[nrank][node_taxid] += pct
        node_info[(nrank, node_taxid)] = build_paths(selected, nrank, ranks)

    if fill_higher:
        # Treat the listed entries as observations that also count towards every higher
        # rank, unless an ancestor at the target rank or at an intermediate rank is itself
        # listed explicitly (its value then stands, which avoids double counting).
        listed = {rank: dict(entries) for rank, entries in abundance.items() if entries}
        filled: Dict[str, Dict[int, float]] = defaultdict(lambda: defaultdict(float))
        contributions = defaultdict(int)
        for source, entries in listed.items():
            for taxid, pct in entries.items():
                selected = select_rank_nodes(taxonomy, taxid, ranks)
                if not selected:
                    continue
                for target in ranks[: ranks.index(source)]:
                    if target not in selected:
                        continue
                    covering = ranks[ranks.index(target): ranks.index(source)]
                    if any(r in selected and selected[r][0] in listed.get(r, {}) for r in covering):
                        continue
                    htid, _ = selected[target]
                    filled[target][htid] += pct
                    node_info[(target, htid)] = build_paths(selected, target, ranks)
                    contributions[target] += 1
        for target, entries in filled.items():
            for htid, pct in entries.items():
                abundance[target][htid] += pct
            print(f"Filled rank '{target}': {len(entries)} taxa from {contributions[target]} lower-rank entries")

    if unresolved:
        print(f"Warning: {len(unresolved)} taxid(s) not found in taxonomy and dropped: {unresolved[:10]}")
    if remapped:
        print(f"Aggregated {sum(remapped.values())} entries into their ancestor at the stated rank: {dict(remapped)}")
    if dropped_ranks:
        print(f"Dropped entries with unsupported ranks: {dict(dropped_ranks)}")

    out_rows = []
    for rank in ranks:
        entries = abundance[rank]
        if not entries:
            continue
        total = sum(entries.values())
        if renormalise and total > 0 and abs(total - 100.0) > 0.01:
            print(f"Renormalising rank '{rank}' (sum {total:.4f}%) to 100%")
            factor = 100.0 / total
        else:
            factor = 1.0
            if total > 100.01:
                print(f"Warning: rank '{rank}' sums to {total:.4f}% (> 100%); use --renormalise")
        for taxid, pct in sorted(entries.items(), key=lambda kv: (-kv[1], kv[0])):
            if pct <= 0:
                continue
            taxpath, taxpathsn = node_info[(rank, taxid)]
            out_rows.append((taxid, rank, taxpath, taxpathsn, pct * factor))

    if not out_rows:
        sys.exit(f"ERROR: no entries left for sample '{sample_id}' after fixing; nothing written")
    return out_rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fix a gold standard bioboxes file (TAXPATH reconstruction, rank clean-up, per-rank renormalisation)"
    )
    parser.add_argument("-i", "--input", required=True, type=Path, help="Input gold standard file")
    parser.add_argument("-o", "--output", required=True, type=Path, help="Output fixed file")
    parser.add_argument("-s", "--sample-id", default=None,
                        help="@SampleID for the output of a single-sample input (default: value from the "
                             "input, else 'gold_standard'); multi-sample inputs keep their own IDs")
    parser.add_argument("-r", "--ranks", default="|".join(DEFAULT_RANKS),
                        help="Pipe- or comma-separated ranks to keep (default: %(default)s)")
    parser.add_argument("--taxdump", type=Path, default=None,
                        help="NCBI taxdump: taxdump.tar.gz / taxdmp_*.zip archive or extracted directory "
                             "(recommended; without it the current taxonomy is downloaded)")
    parser.add_argument("--fill-higher-ranks", action="store_true",
                        help="Derive entries for higher ranks that are absent from the input by summing the "
                             "lowest present rank (e.g. species-only truth)")
    parser.add_argument("--renormalise", "--renormalize", action="store_true",
                        help="Rescale each rank to sum to exactly 100%%")
    parser.add_argument("--taxonomy-db", default="NCBI", help="@TaxonomyID value (default: NCBI)")
    parser.add_argument("--version-bioboxes", default="0.9.1", help="@Version value (default: 0.9.1)")
    args = parser.parse_args()

    sep = "|" if "|" in args.ranks else ","
    ranks = [normalise_rank(r) for r in args.ranks.split(sep) if r.strip()]
    fix_gold_standard(args.input, args.output, args.sample_id, ranks, args.taxdump,
                      args.fill_higher_ranks, args.renormalise, args.taxonomy_db, args.version_bioboxes)


if __name__ == "__main__":
    main()
