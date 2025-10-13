#!/usr/bin/env python3
"""
Fix gold standard bioboxes file by reconstructing proper TAXPATH and TAXPATHSN.
"""

import sys
import argparse
from ete3 import NCBITaxa

def fix_gold_standard(input_file, output_file, sample_id='gold_standard'):
    """Fix gold standard file by reconstructing TAXPATH and TAXPATHSN from taxids."""

    print(f"Initializing NCBI taxonomy database...")
    ncbi = NCBITaxa()

    print(f"Reading input file: {input_file}")

    # Read the input file
    data_lines = []
    with open(input_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('@') or line.startswith('#'):
                continue
            data_lines.append(line)

    print(f"Processing {len(data_lines)} entries...")

    # Valid ranks for OPAL (standard CAMI ranks)
    valid_ranks = {'superkingdom', 'phylum', 'class', 'order', 'family', 'genus', 'species', 'strain'}

    # Map subspecies to strain
    rank_mapping = {'subspecies': 'strain'}

    # Process each row
    results = []
    skipped = 0
    for line in data_lines:
        parts = line.split('\t')

        # Assume format: TAXID, RANK, TAXPATHSN (or TAXPATH), PERCENTAGE
        # Or: TAXID, RANK, TAXPATH, TAXPATHSN, PERCENTAGE
        if len(parts) == 4:
            taxid, rank, taxpathsn_or_taxpath, percentage = parts
        elif len(parts) == 5:
            taxid, rank, _, taxpathsn_or_taxpath, percentage = parts
        else:
            print(f"Warning: Skipping malformed line: {line}")
            continue

        taxid = int(taxid)

        # Skip unsupported ranks
        if rank not in valid_ranks and rank not in rank_mapping:
            skipped += 1
            continue

        # Map subspecies to strain
        if rank in rank_mapping:
            rank = rank_mapping[rank]

        # Get full lineage from NCBI
        try:
            lineage = ncbi.get_lineage(taxid)
            if not lineage:
                print(f"Warning: No lineage found for taxid {taxid}, skipping")
                continue

            # Get names for all taxids in lineage
            names = ncbi.get_taxid_translator(lineage)

            # Build TAXPATH and TAXPATHSN
            taxpath = '|'.join(map(str, lineage))
            taxpathsn = '|'.join([names.get(tid, f'unknown_{tid}') for tid in lineage])

            results.append({
                'TAXID': taxid,
                'RANK': rank,
                'TAXPATH': taxpath,
                'TAXPATHSN': taxpathsn,
                'PERCENTAGE': percentage
            })
        except Exception as e:
            print(f"Error processing taxid {taxid}: {e}")
            continue

    if skipped > 0:
        print(f"Skipped {skipped} entries with unsupported ranks (root, no rank, etc.)")

    # Recalculate percentages to sum to 100%
    total_percentage = sum(float(r['PERCENTAGE']) for r in results)
    if total_percentage > 0 and abs(total_percentage - 100.0) > 0.01:
        print(f"Renormalizing percentages (current sum: {total_percentage:.2f}%)")
        for result in results:
            result['PERCENTAGE'] = f"{float(result['PERCENTAGE']) / total_percentage * 100:.6f}"

    # Write output file
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
        description='Fix gold standard bioboxes file by reconstructing TAXPATH and TAXPATHSN'
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
