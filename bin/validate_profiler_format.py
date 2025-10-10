#!/usr/bin/env python3
"""
Validate profiler output file format before running taxbencher pipeline.

This script checks if a profiler output file is likely to be compatible with
taxpasta standardisation based on basic format checks.

Usage:
    python3 validate_profiler_format.py <profiler> <file>

Examples:
    python3 validate_profiler_format.py kraken2 sample1.kreport
    python3 validate_profiler_format.py metaphlan sample1.profile
    python3 validate_profiler_format.py centrifuge sample1.report
"""

import sys
import argparse
from pathlib import Path


# Format specifications for each profiler
PROFILER_SPECS = {
    "kraken2": {
        "extensions": [".kreport", ".kreport2"],
        "delimiter": "\t",
        "min_columns": 6,
        "max_columns": 6,
        "description": "Kraken2 report format (6 tab-separated columns)",
        "example_columns": ["percentage", "clade_reads", "taxon_reads", "rank", "taxID", "name"],
    },
    "bracken": {
        "extensions": [".kreport", ".bracken"],
        "delimiter": "\t",
        "min_columns": 6,
        "max_columns": 7,
        "description": "Bracken report format (6-7 tab-separated columns)",
        "example_columns": ["percentage", "clade_reads", "taxon_reads", "rank", "taxID", "name"],
    },
    "centrifuge": {
        "extensions": [".report"],
        "delimiter": "\t",
        "min_columns": 6,
        "max_columns": 6,
        "description": "Centrifuge report format (6 tab-separated columns)",
        "example_columns": ["percentage", "numReads", "numUniqueReads", "rank", "taxID", "name"],
    },
    "metaphlan": {
        "extensions": [".profile", ".mpa", ".mpa3"],
        "delimiter": "\t",
        "min_columns": 3,
        "max_columns": 4,
        "description": "MetaPhlAn profile format (3-4 tab-separated columns)",
        "example_columns": ["clade_name", "NCBI_tax_id", "relative_abundance", "additional_species"],
        "header_marker": "#",
    },
    "kaiju": {
        "extensions": [".kaiju", ".out"],
        "delimiter": "\t",
        "min_columns": 3,
        "max_columns": None,
        "description": "Kaiju summary table format (tab-separated)",
        "example_columns": ["taxon_id", "taxon_name", "count"],
    },
    "diamond": {
        "extensions": [".diamond", ".tsv"],
        "delimiter": "\t",
        "min_columns": 2,
        "max_columns": None,
        "description": "DIAMOND taxonomic assignment format",
        "example_columns": ["taxon_id", "count"],
    },
    "ganon": {
        "extensions": [".ganon", ".out"],
        "delimiter": "\t",
        "min_columns": 3,
        "max_columns": None,
        "description": "ganon profiling output (tab-separated)",
        "example_columns": ["taxonomy_id", "lineage", "count"],
    },
    "kmcp": {
        "extensions": [".kmcp", ".out"],
        "delimiter": "\t",
        "min_columns": 2,
        "max_columns": None,
        "description": "KMCP profiling results (tab-separated)",
        "example_columns": ["taxid", "percentage"],
    },
    "motus": {
        "extensions": [".motus", ".out"],
        "delimiter": "\t",
        "min_columns": 2,
        "max_columns": None,
        "description": "mOTUs profiling output (tab-separated)",
        "example_columns": ["taxonomy", "count"],
    },
    "krakenuniq": {
        "extensions": [".krakenuniq", ".kreport"],
        "delimiter": "\t",
        "min_columns": 6,
        "max_columns": 8,
        "description": "KrakenUniq report format (6-8 tab-separated columns)",
        "example_columns": ["percentage", "reads", "taxReads", "kmers", "rank", "taxID", "name"],
    },
    "megan6": {
        "extensions": [".megan", ".rma6"],
        "delimiter": "\t",
        "min_columns": 2,
        "max_columns": None,
        "description": "MEGAN6 taxonomic summary format",
        "example_columns": ["taxon_id", "count"],
    },
}


def validate_file_format(profiler: str, file_path: Path) -> tuple[bool, list[str]]:
    """
    Validate if a file matches the expected format for a profiler.

    Args:
        profiler: Profiler name (e.g., 'kraken2', 'metaphlan')
        file_path: Path to the profiler output file

    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []

    if profiler not in PROFILER_SPECS:
        issues.append(f"Unknown profiler '{profiler}'")
        issues.append(f"Supported profilers: {', '.join(sorted(PROFILER_SPECS.keys()))}")
        return False, issues

    spec = PROFILER_SPECS[profiler]

    # Check file exists
    if not file_path.exists():
        issues.append(f"File does not exist: {file_path}")
        return False, issues

    # Check file extension
    file_ext = file_path.suffix
    if file_ext not in spec["extensions"]:
        issues.append(
            f"File extension '{file_ext}' does not match expected extensions for {profiler}"
        )
        issues.append(f"Expected extensions: {', '.join(spec['extensions'])}")

    # Read and validate file content
    try:
        with open(file_path, "r") as f:
            lines = [line.rstrip("\n") for line in f if line.strip()]

        if not lines:
            issues.append("File is empty")
            return False, issues

        # Check for header marker (e.g., MetaPhlAn uses #)
        header_marker = spec.get("header_marker")
        data_lines = []
        header_lines = []

        for line in lines:
            if header_marker and line.startswith(header_marker):
                header_lines.append(line)
            else:
                data_lines.append(line)

        if not data_lines:
            issues.append("File contains no data lines (only headers or empty)")
            return False, issues

        # Validate column counts in data lines
        delimiter = spec["delimiter"]
        min_cols = spec["min_columns"]
        max_cols = spec["max_columns"]

        column_counts = {}
        for i, line in enumerate(data_lines[:10], 1):  # Check first 10 data lines
            cols = line.split(delimiter)
            col_count = len(cols)
            column_counts[col_count] = column_counts.get(col_count, 0) + 1

            if min_cols is not None and col_count < min_cols:
                issues.append(
                    f"Line {i}: Has {col_count} columns but {profiler} expects at least {min_cols}"
                )
                issues.append(f"  Expected columns: {', '.join(spec['example_columns'])}")

            if max_cols is not None and col_count > max_cols:
                issues.append(
                    f"Line {i}: Has {col_count} columns but {profiler} expects at most {max_cols}"
                )
                issues.append(f"  Expected columns: {', '.join(spec['example_columns'])}")

        # Report column count summary
        if len(column_counts) > 1:
            issues.append(
                f"WARNING: Inconsistent column counts in file: {dict(column_counts)}"
            )

    except Exception as e:
        issues.append(f"Error reading file: {e}")
        return False, issues

    # Determine if validation passed
    is_valid = len(issues) == 0 or all("WARNING" in issue for issue in issues)

    return is_valid, issues


def main():
    parser = argparse.ArgumentParser(
        description="Validate profiler output file format for taxbencher pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s kraken2 sample1.kreport
    %(prog)s metaphlan sample1.profile
    %(prog)s centrifuge sample1.report

Supported profilers:
    """ + ", ".join(sorted(PROFILER_SPECS.keys())),
    )

    parser.add_argument(
        "profiler",
        help="Profiler name (e.g., kraken2, metaphlan, centrifuge)",
    )

    parser.add_argument(
        "file",
        type=Path,
        help="Path to profiler output file",
    )

    parser.add_argument(
        "--show-spec",
        action="store_true",
        help="Show format specification for the profiler",
    )

    args = parser.parse_args()

    profiler = args.profiler.lower()

    # Show spec if requested
    if args.show_spec:
        if profiler not in PROFILER_SPECS:
            print(f"ERROR: Unknown profiler '{profiler}'", file=sys.stderr)
            print(f"Supported profilers: {', '.join(sorted(PROFILER_SPECS.keys()))}", file=sys.stderr)
            sys.exit(1)

        spec = PROFILER_SPECS[profiler]
        print(f"\nFormat specification for {profiler}:")
        print(f"  Description: {spec['description']}")
        print(f"  Extensions: {', '.join(spec['extensions'])}")
        print(f"  Delimiter: {repr(spec['delimiter'])}")
        print(f"  Min columns: {spec['min_columns']}")
        print(f"  Max columns: {spec['max_columns']}")
        print(f"  Example columns: {', '.join(spec['example_columns'])}")
        if "header_marker" in spec:
            print(f"  Header marker: {spec['header_marker']}")
        print()
        sys.exit(0)

    # Validate file
    print(f"Validating {args.file} as {profiler} format...")

    is_valid, issues = validate_file_format(profiler, args.file)

    if is_valid:
        print(f"✓ File appears to be valid {profiler} format")
        if issues:
            print("\nWarnings:")
            for issue in issues:
                print(f"  {issue}")
        sys.exit(0)
    else:
        print(f"\n✗ File does not appear to be valid {profiler} format\n", file=sys.stderr)
        print("Issues found:", file=sys.stderr)
        for issue in issues:
            print(f"  • {issue}", file=sys.stderr)

        print(f"\nFor format details, run:", file=sys.stderr)
        print(f"  {sys.argv[0]} {profiler} --show-spec", file=sys.stderr)
        print(f"\nSee docs/raw-inputs.md for comprehensive format documentation", file=sys.stderr)

        sys.exit(1)


if __name__ == "__main__":
    main()
