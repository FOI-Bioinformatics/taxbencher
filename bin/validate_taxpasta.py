#!/usr/bin/env python3
"""
Validate taxpasta TSV format.

This script validates that a file conforms to the taxpasta standardized
format requirements before being used in the taxbencher pipeline.

Usage:
    validate_taxpasta.py <input_file>

Author: taxbencher pipeline
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import pandas as pd


def validate_taxpasta(input_file: Path) -> Tuple[bool, List[str], Dict[str, any]]:
    """
    Validate taxpasta TSV format.

    Args:
        input_file: Path to taxpasta TSV file

    Returns:
        Tuple of (is_valid, errors, statistics)
    """
    errors = []
    stats = {}

    # Check file exists
    if not input_file.exists():
        return False, [f"File not found: {input_file}"], {}

    # Check file is readable
    try:
        with open(input_file, 'r') as f:
            first_line = f.readline()
    except Exception as e:
        return False, [f"Cannot read file: {e}"], {}

    # Read file
    try:
        df = pd.read_csv(input_file, sep='\t')
        stats['total_rows'] = len(df)
    except pd.errors.EmptyDataError:
        return False, ["File is empty"], {}
    except Exception as e:
        return False, [f"Cannot parse file as TSV: {e}"], {}

    # Validate required columns
    required_columns = ['taxonomy_id', 'count']
    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        errors.append(f"Missing required columns: {', '.join(missing_columns)}")
        errors.append(f"Found columns: {', '.join(df.columns)}")
        return False, errors, stats

    # Check taxonomy_id column
    stats['total_entries'] = len(df)

    # Check for missing taxonomy_id
    missing_taxid = df['taxonomy_id'].isna().sum()
    if missing_taxid > 0:
        errors.append(f"Found {missing_taxid} rows with missing taxonomy_id")
        stats['missing_taxonomy_id'] = missing_taxid

    # Check taxonomy_id are valid (convertible to int)
    try:
        df['taxonomy_id_int'] = pd.to_numeric(df['taxonomy_id'], errors='coerce')
        invalid_taxid = df['taxonomy_id_int'].isna().sum()
        if invalid_taxid > 0:
            errors.append(f"Found {invalid_taxid} rows with invalid taxonomy_id (not convertible to integer)")
            stats['invalid_taxonomy_id'] = invalid_taxid
            # Show examples
            invalid_examples = df[df['taxonomy_id_int'].isna()]['taxonomy_id'].head(5).tolist()
            errors.append(f"  Examples: {invalid_examples}")
    except Exception as e:
        errors.append(f"Error validating taxonomy_id: {e}")

    # Check for negative or zero taxonomy_id
    if 'taxonomy_id_int' in df.columns:
        valid_taxids = df['taxonomy_id_int'].dropna()
        if len(valid_taxids) > 0:
            negative_taxid = (valid_taxids <= 0).sum()
            if negative_taxid > 0:
                errors.append(f"Found {negative_taxid} rows with non-positive taxonomy_id")
                stats['negative_taxonomy_id'] = negative_taxid

    # Check count column
    # Check for missing counts
    missing_count = df['count'].isna().sum()
    if missing_count > 0:
        errors.append(f"Found {missing_count} rows with missing count")
        stats['missing_count'] = missing_count

    # Check counts are numeric
    try:
        df['count_numeric'] = pd.to_numeric(df['count'], errors='coerce')
        invalid_count = df['count_numeric'].isna().sum()
        if invalid_count > 0:
            errors.append(f"Found {invalid_count} rows with invalid count (not numeric)")
            stats['invalid_count'] = invalid_count
            # Show examples
            invalid_examples = df[df['count_numeric'].isna()]['count'].head(5).tolist()
            errors.append(f"  Examples: {invalid_examples}")
    except Exception as e:
        errors.append(f"Error validating count: {e}")

    # Check for negative or zero counts
    if 'count_numeric' in df.columns:
        valid_counts = df['count_numeric'].dropna()
        if len(valid_counts) > 0:
            negative_count = (valid_counts <= 0).sum()
            if negative_count > 0:
                errors.append(f"Found {negative_count} rows with non-positive count")
                stats['negative_count'] = negative_count

            # Statistics on counts
            stats['total_reads'] = int(valid_counts.sum())
            stats['min_count'] = int(valid_counts.min())
            stats['max_count'] = int(valid_counts.max())
            stats['mean_count'] = float(valid_counts.mean())

    # Check for duplicates
    if 'taxonomy_id_int' in df.columns:
        valid_df = df.dropna(subset=['taxonomy_id_int'])
        duplicates = valid_df['taxonomy_id_int'].duplicated().sum()
        if duplicates > 0:
            errors.append(f"Found {duplicates} duplicate taxonomy_id entries")
            stats['duplicate_taxonomy_id'] = duplicates
            # Show examples
            dup_taxids = valid_df[valid_df['taxonomy_id_int'].duplicated(keep=False)]['taxonomy_id'].head(10).tolist()
            errors.append(f"  Examples: {dup_taxids}")

    # Count valid rows
    if 'taxonomy_id_int' in df.columns and 'count_numeric' in df.columns:
        valid_rows = df.dropna(subset=['taxonomy_id_int', 'count_numeric'])
        valid_rows = valid_rows[
            (valid_rows['taxonomy_id_int'] > 0) &
            (valid_rows['count_numeric'] > 0)
        ]
        stats['valid_rows'] = len(valid_rows)
        stats['unique_taxa'] = valid_rows['taxonomy_id_int'].nunique()

    is_valid = len(errors) == 0
    return is_valid, errors, stats


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Validate taxpasta TSV format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Validate a taxpasta file
  validate_taxpasta.py sample1_kraken2.tsv

  # Validate multiple files
  for f in *.tsv; do validate_taxpasta.py "$f"; done

Format requirements:
  - Tab-separated values (TSV)
  - Header row with column names
  - Required columns: taxonomy_id, count
  - taxonomy_id: positive integer (NCBI taxonomy ID)
  - count: positive number (read count)
  - No duplicate taxonomy_id values
        '''
    )
    parser.add_argument('input_file', type=Path, help='Input taxpasta TSV file')
    parser.add_argument('--strict', action='store_true',
                       help='Exit with error on any validation warning')

    args = parser.parse_args()

    print(f"Validating: {args.input_file}")
    print("-" * 60)

    is_valid, errors, stats = validate_taxpasta(args.input_file)

    # Print statistics
    if stats:
        print("\nStatistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")

    # Print errors
    if errors:
        print("\nValidation Issues:")
        for error in errors:
            print(f"  ✗ {error}")

    # Print result
    print("\n" + "-" * 60)
    if is_valid:
        print("✓ VALID: File conforms to taxpasta format")
        return 0
    else:
        print("✗ INVALID: File has format issues")
        print("\nPlease fix the issues above before using this file.")
        return 1 if args.strict else 0


if __name__ == '__main__':
    sys.exit(main())
