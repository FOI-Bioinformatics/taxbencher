#!/usr/bin/env python3
"""
Fix gold standard bioboxes file by adding TAXPATH column and proper headers.
"""

import sys
import argparse

# Try to import ete3, but make it optional
try:
    from ete3 import NCBITaxa
    HAS_ETE3 = True
except ImportError:
    HAS_ETE3 = False
    print("Warning: ete3 not available, will use placeholder TAXPATHs")

def get_lineage_path(taxid, ncbi=None):
    """Get the taxonomy ID lineage path for a given taxid."""
    if not HAS_ETE3 or ncbi is None:
        # Fallback: use taxid as placeholder
        return str(taxid)

    try:
        lineage = ncbi.get_lineage(taxid)
        if lineage:
            return '|'.join(map(str, lineage))
        return str(taxid)
    except:
        return str(taxid)

def fix_gold_standard(input_file, output_file, sample_id='gold_standard'):
    """Fix gold standard file by adding TAXPATH column and headers."""

    # Initialize NCBI if available
    ncbi = None
    if HAS_ETE3:
        print(f"Initializing NCBI taxonomy database...")
        try:
            ncbi = NCBITaxa()
        except Exception as e:
            print(f"Warning: Could not initialize NCBITaxa: {e}")
            ncbi = None

    print(f"Reading input file: {input_file}")

    # Read the input file
    header_line = None
    data_lines = []
    with open(input_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Skip metadata lines (single @) but keep column header (@@)
            if line.startswith('@@'):
                header_line = line.lstrip('@')
            elif line.startswith('#') or line.startswith('@'):
                continue
            else:
                data_lines.append(line)

    if header_line is None:
        print("Error: No column header found")
        return

    columns = header_line.split('\t')
    print(f"Found columns: {columns}")

    # Check if data rows match header column count
    first_data_row = data_lines[0].split('\t') if data_lines else []
    print(f"Header has {len(columns)} columns, first data row has {len(first_data_row)} columns")

    # Determine if we need to fix
    if 'TAXPATH' not in columns:
        print("TAXPATH column missing from header, will add it")
        needs_fix = True
        # Find column indices (no TAXPATH)
        taxid_idx = columns.index('TAXID')
        rank_idx = columns.index('RANK')
        taxpathsn_idx = columns.index('TAXPATHSN')
        percentage_idx = columns.index('PERCENTAGE')
        taxpath_idx = None
    elif len(columns) != len(first_data_row):
        print(f"Column count mismatch - header has TAXPATH but data rows don't, will fix")
        needs_fix = True
        # Data is missing TAXPATH column - assume order is: TAXID, RANK, TAXPATHSN, PERCENTAGE
        taxid_idx = 0
        rank_idx = 1
        taxpathsn_idx = 2
        percentage_idx = 3
        taxpath_idx = None
    else:
        print("TAXPATH column already exists and data matches, no fix needed.")
        return

    print(f"Processing {len(data_lines)} entries...")

    # Valid ranks for OPAL (standard CAMI ranks)
    valid_ranks = {'superkingdom', 'phylum', 'class', 'order', 'family', 'genus', 'species', 'strain'}

    # Map subspecies to strain (OPAL doesn't have subspecies)
    rank_mapping = {'subspecies': 'strain'}

    # Process each row and add TAXPATH
    results = []
    skipped = 0
    for line in data_lines:
        parts = line.split('\t')
        taxid = int(parts[taxid_idx])
        rank = parts[rank_idx]
        taxpathsn = parts[taxpathsn_idx]
        percentage = parts[percentage_idx]

        # Skip unsupported ranks (root, no rank, etc.)
        if rank not in valid_ranks and rank not in rank_mapping:
            skipped += 1
            continue

        # Map subspecies to strain
        if rank in rank_mapping:
            rank = rank_mapping[rank]

        # Get TAXPATH from NCBI
        taxpath = get_lineage_path(taxid, ncbi)

        results.append({
            'TAXID': taxid,
            'RANK': rank,
            'TAXPATH': taxpath,
            'TAXPATHSN': taxpathsn,
            'PERCENTAGE': percentage
        })

    if skipped > 0:
        print(f"Skipped {skipped} entries with unsupported ranks (root, no rank, etc.)")

    # Recalculate percentages to sum to 100%
    total_percentage = sum(float(r['PERCENTAGE']) for r in results)
    if total_percentage > 0 and abs(total_percentage - 100.0) > 0.01:
        print(f"Renormalizing percentages (current sum: {total_percentage:.2f}%)")
        for result in results:
            result['PERCENTAGE'] = f"{float(result['PERCENTAGE']) / total_percentage * 100:.6f}"

    # Write output file with proper format
    print(f"Writing output file: {output_file}")

    with open(output_file, 'w') as f:
        # Write headers
        f.write(f"@SampleID:{sample_id}\n")
        f.write("@Version:0.9.1\n")
        f.write("@Ranks:superkingdom|phylum|class|order|family|genus|species|strain\n")
        f.write("@TaxonomyID:NCBI\n")

        # Write column headers
        f.write("@@TAXID\tRANK\tTAXPATH\tTAXPATHSN\tPERCENTAGE\n")

        # Write data
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
        description='Fix gold standard bioboxes file by adding TAXPATH column'
    )
    parser.add_argument(
        '-i', '--input',
        required=True,
        help='Input gold standard file'
    )
    parser.add_argument(
        '-o', '--output',
        required=True,
        help='Output fixed file'
    )
    parser.add_argument(
        '-s', '--sample-id',
        default='gold_standard',
        help='Sample ID for @SampleID header (default: gold_standard)'
    )

    args = parser.parse_args()

    fix_gold_standard(args.input, args.output, args.sample_id)

if __name__ == '__main__':
    main()
