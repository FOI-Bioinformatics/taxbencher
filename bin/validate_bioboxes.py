#!/usr/bin/env python3
"""
Validate CAMI Bioboxes profiling format.

This script validates that a file conforms to the CAMI profiling Bioboxes
format specification required by OPAL.

Usage:
    validate_bioboxes.py <input_file>

Author: taxbencher pipeline
"""

import argparse
import sys
import re
from pathlib import Path
from typing import Dict, List, Tuple


def validate_bioboxes(input_file: Path) -> Tuple[bool, List[str], Dict[str, any]]:
    """
    Validate CAMI Bioboxes profiling format.

    Args:
        input_file: Path to bioboxes file

    Returns:
        Tuple of (is_valid, errors, statistics)
    """
    errors = []
    stats = {}

    # Check file exists
    if not input_file.exists():
        return False, [f"File not found: {input_file}"], {}

    # Read file
    try:
        with open(input_file, 'r') as f:
            lines = f.readlines()
    except Exception as e:
        return False, [f"Cannot read file: {e}"], {}

    if not lines:
        return False, ["File is empty"], {}

    stats['total_lines'] = len(lines)

    # Track headers and data
    headers = {}
    data_lines = []
    in_data = False

    for i, line in enumerate(lines, 1):
        line = line.strip()

        # Skip empty lines
        if not line:
            continue

        # Parse header lines (@ prefix)
        if line.startswith('@') and not line.startswith('@@'):
            match = re.match(r'@(\w+):(.+)', line)
            if match:
                key, value = match.groups()
                headers[key] = value.strip()
            else:
                errors.append(f"Line {i}: Invalid header format: {line}")

        # Parse column header (@@)
        elif line.startswith('@@'):
            in_data = True
            # Remove @@ prefix and split
            col_line = line[2:].strip()
            stats['column_header'] = col_line

        # Parse data lines
        elif in_data:
            data_lines.append((i, line))

    # Validate required headers
    required_headers = ['SampleID', 'Version', 'Ranks']
    for header in required_headers:
        if header not in headers:
            errors.append(f"Missing required header: @{header}")

    # Store header stats
    stats['headers_found'] = list(headers.keys())

    # Validate Version
    if 'Version' in headers:
        version = headers['Version']
        if not re.match(r'\d+\.\d+\.\d+', version):
            errors.append(f"Version format invalid: {version} (expected format: X.Y.Z)")
        stats['version'] = version

    # Validate Ranks
    if 'Ranks' in headers:
        ranks = headers['Ranks']
        rank_list = ranks.split('|')
        stats['ranks'] = rank_list
        stats['num_ranks'] = len(rank_list)

        # Common rank names
        expected_ranks = [
            'superkingdom', 'kingdom', 'phylum', 'class', 'order',
            'family', 'genus', 'species', 'strain'
        ]
        unexpected_ranks = [r for r in rank_list if r not in expected_ranks and not r.startswith('no_rank')]
        if unexpected_ranks:
            errors.append(f"Unexpected rank names: {unexpected_ranks}")

    # Validate TaxonomyID if present
    if 'TaxonomyID' in headers:
        tax_db = headers['TaxonomyID']
        stats['taxonomy_db'] = tax_db
        if tax_db not in ['NCBI', 'GTDB']:
            errors.append(f"Unusual TaxonomyID: {tax_db} (expected NCBI or GTDB)")

    # Check for column header
    if 'column_header' not in stats:
        errors.append("Missing column header (line starting with @@)")
        return False, errors, stats

    # Validate column header
    expected_columns = ['TAXID', 'RANK', 'TAXPATH', 'TAXPATHSN', 'PERCENTAGE']
    found_columns = stats['column_header'].split('\t')
    found_columns = [col.strip() for col in found_columns]
    stats['columns_found'] = found_columns

    missing_columns = [col for col in expected_columns if col not in found_columns]
    if missing_columns:
        errors.append(f"Missing required columns: {', '.join(missing_columns)}")
        errors.append(f"Found columns: {', '.join(found_columns)}")

    # Validate data lines
    if not data_lines:
        errors.append("No data rows found")
        stats['data_rows'] = 0
    else:
        stats['data_rows'] = len(data_lines)
        percentages = []
        taxids = []

        for line_num, line in data_lines:
            fields = line.split('\t')

            if len(fields) < 5:
                errors.append(f"Line {line_num}: Insufficient columns (expected 5, got {len(fields)})")
                continue

            taxid, rank, taxpath, taxpathsn, percentage = fields[:5]

            # Validate TAXID
            try:
                taxid_int = int(taxid)
                if taxid_int <= 0:
                    errors.append(f"Line {line_num}: Invalid TAXID (must be positive): {taxid}")
                taxids.append(taxid_int)
            except ValueError:
                errors.append(f"Line {line_num}: TAXID not an integer: {taxid}")

            # Validate RANK
            if 'Ranks' in headers:
                rank_list = headers['Ranks'].split('|')
                if rank not in rank_list and rank != 'no_rank' and rank != 'unknown':
                    errors.append(f"Line {line_num}: RANK '{rank}' not in header Ranks")

            # Validate TAXPATH (pipe-separated taxids)
            if taxpath:
                taxpath_parts = taxpath.split('|')
                for part in taxpath_parts:
                    try:
                        int(part)
                    except ValueError:
                        errors.append(f"Line {line_num}: TAXPATH contains non-integer: {part}")
                        break

                # Check if last taxid in path matches TAXID
                if taxpath_parts and taxid:
                    try:
                        if int(taxpath_parts[-1]) != int(taxid):
                            errors.append(
                                f"Line {line_num}: Last TAXPATH element ({taxpath_parts[-1]}) "
                                f"doesn't match TAXID ({taxid})"
                            )
                    except (ValueError, IndexError):
                        pass

            # Validate TAXPATHSN (pipe-separated names)
            if taxpathsn and taxpath:
                name_parts = taxpathsn.split('|')
                path_parts = taxpath.split('|')
                if len(name_parts) != len(path_parts):
                    errors.append(
                        f"Line {line_num}: TAXPATHSN ({len(name_parts)} elements) "
                        f"doesn't match TAXPATH ({len(path_parts)} elements)"
                    )

            # Validate PERCENTAGE
            try:
                pct = float(percentage)
                if pct < 0 or pct > 100:
                    errors.append(f"Line {line_num}: PERCENTAGE out of range [0, 100]: {pct}")
                percentages.append(pct)
            except ValueError:
                errors.append(f"Line {line_num}: PERCENTAGE not a number: {percentage}")

        # Statistics on data
        if percentages:
            stats['total_percentage'] = sum(percentages)
            stats['min_percentage'] = min(percentages)
            stats['max_percentage'] = max(percentages)

            # Check if percentages sum to ~100 (allow some tolerance)
            pct_sum = sum(percentages)
            if abs(pct_sum - 100) > 1.0:  # 1% tolerance
                errors.append(
                    f"Percentages sum to {pct_sum:.2f}% (expected ~100%). "
                    f"This may be acceptable for some use cases."
                )

        if taxids:
            stats['unique_taxids'] = len(set(taxids))
            # Check for duplicates
            duplicates = len(taxids) - len(set(taxids))
            if duplicates > 0:
                errors.append(f"Found {duplicates} duplicate TAXID entries")

    is_valid = len(errors) == 0
    return is_valid, errors, stats


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Validate CAMI Bioboxes profiling format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Validate a bioboxes file
  validate_bioboxes.py gold_standard.bioboxes

  # Validate multiple files
  for f in *.bioboxes; do validate_bioboxes.py "$f"; done

Format specification:
  @SampleID:sample_name
  @Version:0.9.1
  @Ranks:superkingdom|phylum|class|order|family|genus|species
  @TaxonomyID:NCBI

  @@TAXID	RANK	TAXPATH	TAXPATHSN	PERCENTAGE
  562	species	2|1224|1236|91347|543|561|562	Bacteria|...	45.5

Reference:
  https://github.com/bioboxes/rfc/tree/master/data-format
        '''
    )
    parser.add_argument('input_file', type=Path, help='Input bioboxes file')
    parser.add_argument('--strict', action='store_true',
                       help='Exit with error on any validation warning')

    args = parser.parse_args()

    print(f"Validating: {args.input_file}")
    print("-" * 60)

    is_valid, errors, stats = validate_bioboxes(args.input_file)

    # Print statistics
    if stats:
        print("\nStatistics:")
        for key, value in stats.items():
            if isinstance(value, list) and len(value) > 10:
                print(f"  {key}: {len(value)} items")
            else:
                print(f"  {key}: {value}")

    # Print errors
    if errors:
        print("\nValidation Issues:")
        for error in errors:
            print(f"  ✗ {error}")

    # Print result
    print("\n" + "-" * 60)
    if is_valid:
        print("✓ VALID: File conforms to CAMI Bioboxes format")
        return 0
    else:
        print("✗ INVALID: File has format issues")
        print("\nPlease fix the issues above before using this file.")
        print("\nSee: https://github.com/bioboxes/rfc/tree/master/data-format")
        return 1 if args.strict else 0


if __name__ == '__main__':
    sys.exit(main())
