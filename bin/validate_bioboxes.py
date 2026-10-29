#!/usr/bin/env python3
"""
Validate CAMI profiling (Bioboxes) format files as consumed by OPAL.

Checks performed per sample block:
  * required headers (@SampleID, @Version, @Ranks, @TaxonomyID)
  * column header (@@) with TAXID, RANK, TAXPATH, PERCENTAGE (TAXPATHSN optional)
  * ranks restricted to the OPAL-supported CAMI ranks
  * TAXID / PERCENTAGE value types and ranges
  * TAXPATH structure (pipe separated integers, empty fields allowed for
    missing ranks, last element equals TAXID) and TAXPATHSN length
  * duplicated TAXIDs within a sample
  * abundance sums *per rank* (CAMI semantics: each rank sums to <= 100 %)

Multi-sample files (several @SampleID blocks) are supported.

Exit status: 0 when valid or when only warnings were found, 1 when errors were
found with --strict, or always 1 on errors when --strict is given.

Usage:
    validate_bioboxes.py <input_file> [--strict] [--sample-id ID ...]
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

OPAL_RANKS = ["superkingdom", "phylum", "class", "order", "family", "genus", "species", "strain"]
REQUIRED_HEADERS = ["SampleID", "Version", "Ranks", "TaxonomyID"]
REQUIRED_COLUMNS = ["TAXID", "RANK", "TAXPATH", "PERCENTAGE"]
RANK_SUM_TOLERANCE = 1.0  # percent


def split_samples(lines: List[str]) -> List[Tuple[Dict[str, str], List[str], List[Tuple[int, str]], List[str]]]:
    """
    Split the file into sample blocks.

    Returns a list of (headers, columns, data_lines[(lineno, line)], block_errors).
    A new block starts when an '@' header line follows data lines.
    """
    blocks = []
    headers: Dict[str, str] = {}
    columns: List[str] = []
    data: List[Tuple[int, str]] = []
    block_errors: List[str] = []
    reading_data = False

    def flush():
        if headers or columns or data:
            blocks.append((headers, columns, data, block_errors))

    for lineno, raw in enumerate(lines, 1):
        line = raw.rstrip("\n").rstrip("\r")
        if not line.strip() or line.startswith("#"):
            continue
        if line.startswith("@@"):
            columns = [c.strip() for c in line[2:].split("\t")]
            reading_data = False
            continue
        if line.startswith("@"):
            if reading_data:
                flush()
                headers, columns, data, block_errors = {}, [], [], []
                reading_data = False
            match = re.match(r"@([^:]+):(.*)$", line)
            if match:
                headers[match.group(1).strip()] = match.group(2).strip()
            else:
                block_errors.append(f"Line {lineno}: Invalid header format: {line}")
            continue
        reading_data = True
        data.append((lineno, line))
    flush()
    return blocks


def validate_block(headers, columns, data, errors: List[str], warnings: List[str], stats: Dict) -> None:
    sample = headers.get("SampleID", "<unknown>")
    prefix = f"[{sample}] "

    for header in REQUIRED_HEADERS:
        if header not in headers:
            errors.append(f"{prefix}Missing required header: @{header}")

    version = headers.get("Version")
    if version and not re.match(r"^\d+\.\d+(\.\d+)?$", version):
        errors.append(f"{prefix}Version format invalid: {version} (expected X.Y[.Z])")

    header_ranks: List[str] = []
    if "Ranks" in headers:
        header_ranks = [r.strip() for r in headers["Ranks"].split("|") if r.strip()]
        unsupported = [r for r in header_ranks if r not in OPAL_RANKS]
        if unsupported:
            errors.append(
                f"{prefix}@Ranks contains ranks unsupported by OPAL: {unsupported}. "
                f"Supported: {', '.join(OPAL_RANKS)}"
            )

    tax_db = headers.get("TaxonomyID")
    if tax_db and tax_db not in ("NCBI", "GTDB"):
        warnings.append(f"{prefix}Unusual @TaxonomyID: {tax_db} (expected NCBI or GTDB)")

    if not columns:
        errors.append(f"{prefix}Missing column header line starting with @@")
        return
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in columns]
    if missing_cols:
        errors.append(f"{prefix}Missing required columns: {', '.join(missing_cols)} (found: {', '.join(columns)})")
        return
    if "TAXPATHSN" not in columns:
        warnings.append(f"{prefix}No TAXPATHSN column (optional, but recommended)")

    idx = {name: columns.index(name) for name in columns}
    ncol = len(columns)

    if not data:
        errors.append(f"{prefix}No data rows found")
        return

    rank_sums: Dict[str, float] = defaultdict(float)
    rank_counts: Dict[str, int] = defaultdict(int)
    seen_taxids: Dict[str, int] = defaultdict(int)
    unsupported_ranks = set()
    not_in_header_ranks = set()

    for lineno, line in data:
        fields = line.split("\t")
        if len(fields) != ncol:
            errors.append(f"{prefix}Line {lineno}: expected {ncol} columns, got {len(fields)}")
            if len(fields) < ncol:
                continue
        taxid = fields[idx["TAXID"]].strip()
        rank = fields[idx["RANK"]].strip()
        taxpath = fields[idx["TAXPATH"]].strip()
        taxpathsn = fields[idx["TAXPATHSN"]].strip() if "TAXPATHSN" in idx else None
        percentage = fields[idx["PERCENTAGE"]].strip()

        # TAXID
        taxid_ok = False
        try:
            taxid_int = int(taxid)
            taxid_ok = True
            if taxid_int <= 0:
                errors.append(f"{prefix}Line {lineno}: TAXID must be positive: {taxid}")
        except ValueError:
            # GTDB and other databases may use string identifiers
            if headers.get("TaxonomyID", "NCBI") == "NCBI":
                errors.append(f"{prefix}Line {lineno}: TAXID is not an integer: {taxid}")
        seen_taxids[taxid] += 1

        # RANK
        if rank not in OPAL_RANKS:
            unsupported_ranks.add(rank)
        elif header_ranks and rank not in header_ranks:
            not_in_header_ranks.add(rank)

        # TAXPATH
        if not taxpath:
            errors.append(f"{prefix}Line {lineno}: empty TAXPATH")
        else:
            parts = taxpath.split("|")
            if headers.get("TaxonomyID", "NCBI") == "NCBI":
                bad = [p for p in parts if p and not p.isdigit()]
                if bad:
                    errors.append(f"{prefix}Line {lineno}: TAXPATH contains non-integer element(s): {bad[:3]}")
            if parts[-1] != taxid:
                errors.append(
                    f"{prefix}Line {lineno}: last TAXPATH element ({parts[-1] or '<empty>'}) does not match TAXID ({taxid})"
                )
            if header_ranks and rank in header_ranks and len(parts) != header_ranks.index(rank) + 1:
                # Full NCBI lineages are tolerated by OPAL but are not CAMI conformant
                warnings.append(
                    f"{prefix}Line {lineno}: TAXPATH has {len(parts)} elements but rank '{rank}' is position "
                    f"{header_ranks.index(rank) + 1} in @Ranks (CAMI expects one element per rank)"
                )
            if taxpathsn is not None and taxpathsn:
                name_parts = taxpathsn.split("|")
                if len(name_parts) != len(parts):
                    errors.append(
                        f"{prefix}Line {lineno}: TAXPATHSN has {len(name_parts)} elements but TAXPATH has {len(parts)}"
                    )

        # PERCENTAGE
        try:
            pct = float(percentage)
            if pct < 0 or pct > 100:
                errors.append(f"{prefix}Line {lineno}: PERCENTAGE out of range [0, 100]: {pct}")
            else:
                rank_sums[rank] += pct
                rank_counts[rank] += 1
                if pct == 0:
                    warnings.append(f"{prefix}Line {lineno}: zero abundance entry (ignored by OPAL)")
        except ValueError:
            errors.append(f"{prefix}Line {lineno}: PERCENTAGE is not a number: {percentage}")

    if unsupported_ranks:
        errors.append(
            f"{prefix}Data contains ranks unsupported by OPAL: {sorted(unsupported_ranks)}. "
            f"Use fix_gold_standard.py to drop or remap them."
        )
    if not_in_header_ranks:
        errors.append(f"{prefix}Data contains ranks missing from @Ranks: {sorted(not_in_header_ranks)}")

    duplicates = {t: n for t, n in seen_taxids.items() if n > 1}
    if duplicates:
        errors.append(
            f"{prefix}{len(duplicates)} TAXID(s) appear more than once (OPAL sums or rejects them): "
            f"{sorted(duplicates)[:10]}"
        )

    for rank in header_ranks or sorted(rank_sums):
        if rank not in rank_sums:
            warnings.append(f"{prefix}No entries for rank '{rank}'")
            continue
        total = rank_sums[rank]
        if total > 100 + RANK_SUM_TOLERANCE:
            errors.append(
                f"{prefix}Rank '{rank}' abundances sum to {total:.2f}% (> 100%). "
                f"Each rank must sum to at most 100%."
            )
        elif total < 100 - RANK_SUM_TOLERANCE:
            warnings.append(
                f"{prefix}Rank '{rank}' abundances sum to {total:.2f}% (< 100%; acceptable if part of the "
                f"sample is unassigned at this rank, otherwise consider renormalising)"
            )

    stats.setdefault("samples", []).append(sample)
    stats.setdefault("per_sample", {})[sample] = {
        "data_rows": len(data),
        "ranks": {r: {"n": rank_counts[r], "sum": round(rank_sums[r], 4)} for r in rank_sums},
    }


def validate_bioboxes(input_file: Path, expected_samples: List[str] = None) -> Tuple[bool, List[str], List[str], Dict]:
    errors: List[str] = []
    warnings: List[str] = []
    stats: Dict = {}

    if not input_file.exists():
        return False, [f"File not found: {input_file}"], [], {}
    try:
        with open(input_file, "r") as handle:
            lines = handle.readlines()
    except Exception as exc:
        return False, [f"Cannot read file: {exc}"], [], {}
    if not any(l.strip() for l in lines):
        return False, ["File is empty"], [], {}

    stats["total_lines"] = len(lines)
    blocks = split_samples(lines)
    if not blocks:
        return False, ["No sample blocks found"], [], stats

    for headers, columns, data, block_errors in blocks:
        errors.extend(block_errors)
        validate_block(headers, columns, data, errors, warnings, stats)

    samples = stats.get("samples", [])
    dup_samples = {s for s in samples if samples.count(s) > 1}
    if dup_samples:
        errors.append(f"Duplicate @SampleID blocks: {sorted(dup_samples)}")
    if expected_samples:
        missing = [s for s in expected_samples if s not in samples]
        if missing:
            errors.append(
                f"Expected sample ID(s) not present in file: {missing}. "
                f"OPAL silently skips profiles whose @SampleID has no gold standard match."
            )

    return len(errors) == 0, errors, warnings, stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate CAMI profiling Bioboxes format (as used by OPAL)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  validate_bioboxes.py gold_standard.bioboxes
  validate_bioboxes.py gold_standard.bioboxes --strict --sample-id sample1 --sample-id sample2

Format specification:
  @SampleID:sample_name
  @Version:0.9.1
  @Ranks:superkingdom|phylum|class|order|family|genus|species|strain
  @TaxonomyID:NCBI
  @@TAXID	RANK	TAXPATH	TAXPATHSN	PERCENTAGE
  2	superkingdom	2	Bacteria	100.0
  562	species	2|1224|1236|91347|543|561|562	Bacteria|...|Escherichia coli	45.5

Reference: https://github.com/bioboxes/rfc/tree/master/data-format
        """,
    )
    parser.add_argument("input_file", type=Path, help="Input bioboxes file")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when errors are found")
    parser.add_argument("--sample-id", action="append", default=[],
                        help="Sample ID that must be present (repeatable)")
    parser.add_argument("--quiet", action="store_true", help="Only print the verdict and problems")
    parser.add_argument("--version", action="version", version="%(prog)s 2.0.0")
    args = parser.parse_args()

    print(f"Validating: {args.input_file}")
    print("-" * 60)
    is_valid, errors, warnings, stats = validate_bioboxes(args.input_file, args.sample_id)

    if stats and not args.quiet:
        print("\nStatistics:")
        print(f"  total_lines: {stats.get('total_lines')}")
        for sample, info in stats.get("per_sample", {}).items():
            print(f"  sample {sample}: {info['data_rows']} rows")
            for rank, r in info["ranks"].items():
                print(f"    {rank:13s} n={r['n']:5d} sum={r['sum']:.2f}%")

    if warnings:
        print("\nWarnings:")
        for w in warnings[:50]:
            print(f"  ! {w}")
        if len(warnings) > 50:
            print(f"  ... {len(warnings) - 50} more warnings")
    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  ✗ {e}")

    print("\n" + "-" * 60)
    if is_valid:
        print("✓ VALID: File conforms to CAMI Bioboxes format" + (" (with warnings)" if warnings else ""))
        return 0
    print("✗ INVALID: File has format issues")
    print("\nPlease fix the issues above before using this file (see docs/troubleshooting-gold-standard.md).")
    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
