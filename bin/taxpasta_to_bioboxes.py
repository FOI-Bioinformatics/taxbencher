#!/usr/bin/env python3
"""
Convert taxpasta standardized format to CAMI Bioboxes profiling format.

This script converts taxonomic profiling results from taxpasta's standardized
TSV format to the CAMI Bioboxes format required for OPAL evaluation.

Author: taxbencher pipeline
"""

import argparse
import sys
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import pandas as pd

# Try to import ete3 for taxonomy lookups
try:
    from ete3 import NCBITaxa
    HAS_ETE3 = True
except ImportError:
    HAS_ETE3 = False
    logging.warning("ete3 not available, using simplified conversion mode")


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def get_taxonomy_info(taxid: int, ncbi: Optional['NCBITaxa'] = None) -> Tuple[str, str, str]:
    """
    Get taxonomy information for a given taxid.

    Args:
        taxid: NCBI taxonomy ID
        ncbi: NCBITaxa object (optional)

    Returns:
        Tuple of (rank, taxpath, taxpathsn)
    """
    if not HAS_ETE3 or ncbi is None:
        # Simplified mode: return taxid as-is with unknown rank
        return "unknown", str(taxid), f"taxid_{taxid}"

    try:
        # Get rank
        rank = ncbi.get_rank([taxid]).get(taxid, "unknown")

        # Get lineage
        lineage = ncbi.get_lineage(taxid)
        if lineage is None:
            lineage = [taxid]

        # Create taxpath (pipe-separated taxids)
        taxpath = "|".join(str(tid) for tid in lineage)

        # Get names for taxpathsn
        name_dict = ncbi.get_taxid_translator(lineage)
        taxpathsn = "|".join(name_dict.get(tid, f"taxid_{tid}") for tid in lineage)

        return rank, taxpath, taxpathsn

    except Exception as e:
        logging.warning(f"Error getting taxonomy info for taxid {taxid}: {e}")
        return "unknown", str(taxid), f"taxid_{taxid}"


def convert_taxpasta_to_bioboxes(
    input_file: Path,
    output_file: Path,
    sample_id: str,
    ranks: List[str],
    taxonomy_db: str = "NCBI",
    version: str = "0.9.1",
    use_ete3: bool = True
) -> None:
    """
    Convert taxpasta format to CAMI Bioboxes format.

    Args:
        input_file: Path to taxpasta TSV file
        output_file: Path to output Bioboxes file
        sample_id: Sample identifier
        ranks: List of taxonomic ranks to include in header
        taxonomy_db: Taxonomy database name (default: NCBI)
        version: Bioboxes format version (default: 0.9.1)
        use_ete3: Whether to use ete3 for taxonomy lookups
    """
    logging.info(f"Reading taxpasta file: {input_file}")

    # Read taxpasta file
    try:
        df = pd.read_csv(input_file, sep='\t', dtype={'taxonomy_id': str})
    except Exception as e:
        logging.error(f"Error reading input file: {e}")
        sys.exit(1)

    # Validate required columns
    if 'taxonomy_id' not in df.columns or 'count' not in df.columns:
        logging.error("Input file must contain 'taxonomy_id' and 'count' columns")
        sys.exit(1)

    # Remove rows with missing or invalid data
    df = df.dropna(subset=['taxonomy_id', 'count'])
    df['count'] = pd.to_numeric(df['count'], errors='coerce')
    df = df.dropna(subset=['count'])
    df = df[df['count'] > 0]

    if len(df) == 0:
        logging.warning("No valid data found in input file")

    # Calculate total counts for percentage calculation
    total_counts = df['count'].sum()

    # Initialize ete3 if requested and available
    ncbi = None
    if use_ete3 and HAS_ETE3:
        logging.info("Initializing NCBI taxonomy database")
        try:
            ncbi = NCBITaxa()
            # Update database if needed
            # ncbi.update_taxonomy_database()  # Uncomment to force update
        except Exception as e:
            logging.warning(f"Could not initialize NCBITaxa: {e}. Using simplified mode.")
            ncbi = None

    # Valid ranks for OPAL (standard CAMI ranks)
    valid_ranks = {'superkingdom', 'phylum', 'class', 'order', 'family', 'genus', 'species', 'strain'}

    # Map non-standard ranks to standard ones
    rank_mapping = {
        'subspecies': 'strain',
        'domain': 'superkingdom',
        'kingdom': 'superkingdom'
    }

    # Process each taxonomy entry
    results = []
    skipped_ranks = set()
    for idx, row in df.iterrows():
        try:
            taxid = int(row['taxonomy_id'])
        except (ValueError, TypeError):
            logging.warning(f"Invalid taxonomy_id: {row['taxonomy_id']}, skipping")
            continue

        count = row['count']
        percentage = (count / total_counts * 100) if total_counts > 0 else 0

        # Get taxonomy information
        rank, taxpath, taxpathsn = get_taxonomy_info(taxid, ncbi)

        # Skip unsupported ranks (root, no rank, unknown, cellular root, etc.)
        if rank not in valid_ranks and rank not in rank_mapping:
            skipped_ranks.add(rank)
            continue

        # Map non-standard ranks to standard ones
        if rank in rank_mapping:
            rank = rank_mapping[rank]

        results.append({
            'TAXID': taxid,
            'RANK': rank,
            'TAXPATH': taxpath,
            'TAXPATHSN': taxpathsn,
            'PERCENTAGE': f"{percentage:.6f}"
        })

    if skipped_ranks:
        logging.info(f"Skipped {len(skipped_ranks)} unsupported ranks: {', '.join(sorted(skipped_ranks))}")

    # Renormalize percentages to sum to 100%
    total_percentage = sum(float(r['PERCENTAGE']) for r in results)
    if total_percentage > 0 and abs(total_percentage - 100.0) > 0.01:
        logging.info(f"Renormalizing percentages (current sum: {total_percentage:.2f}%)")
        for result in results:
            result['PERCENTAGE'] = f"{float(result['PERCENTAGE']) / total_percentage * 100:.6f}"

    # Create output file with proper Bioboxes format
    logging.info(f"Writing Bioboxes file: {output_file}")

    with open(output_file, 'w') as f:
        # Write header
        f.write(f"@SampleID:{sample_id}\n")
        f.write(f"@Version:{version}\n")
        f.write(f"@Ranks:{ranks if isinstance(ranks, str) else '|'.join(ranks)}\n")
        f.write(f"@TaxonomyID:{taxonomy_db}\n")

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

    logging.info(f"Successfully converted {len(results)} entries")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Convert taxpasta format to CAMI Bioboxes format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic conversion
  taxpasta_to_bioboxes.py -i input.tsv -o output.bioboxes -s sample_1

  # With custom ranks
  taxpasta_to_bioboxes.py -i input.tsv -o output.bioboxes -s sample_1 \\
      -r superkingdom,phylum,class,order,family,genus,species,strain

  # Without ete3 (simplified mode)
  taxpasta_to_bioboxes.py -i input.tsv -o output.bioboxes -s sample_1 --no-ete3
        """
    )

    parser.add_argument(
        '-i', '--input',
        type=Path,
        required=True,
        help='Input taxpasta TSV file'
    )
    parser.add_argument(
        '-o', '--output',
        type=Path,
        required=True,
        help='Output Bioboxes file'
    )
    parser.add_argument(
        '-s', '--sample-id',
        type=str,
        required=True,
        help='Sample identifier'
    )
    parser.add_argument(
        '-r', '--ranks',
        type=str,
        default='superkingdom|phylum|class|order|family|genus|species|strain',
        help='Taxonomic ranks (pipe-separated, default: superkingdom|phylum|class|order|family|genus|species|strain)'
    )
    parser.add_argument(
        '-d', '--taxonomy-db',
        type=str,
        default='NCBI',
        help='Taxonomy database name (default: NCBI)'
    )
    parser.add_argument(
        '--version-bioboxes',
        type=str,
        default='0.9.1',
        help='Bioboxes format version (default: 0.9.1)'
    )
    parser.add_argument(
        '--no-ete3',
        action='store_true',
        help='Disable ete3 taxonomy lookups (simplified mode)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 1.0.0'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    # Validate input file
    if not args.input.exists():
        logging.error(f"Input file does not exist: {args.input}")
        sys.exit(1)

    # Convert ranks string to list if needed
    ranks = args.ranks if '|' in args.ranks else args.ranks.split(',')

    # Perform conversion
    try:
        convert_taxpasta_to_bioboxes(
            input_file=args.input,
            output_file=args.output,
            sample_id=args.sample_id,
            ranks=ranks,
            taxonomy_db=args.taxonomy_db,
            version=args.version_bioboxes,
            use_ete3=not args.no_ete3
        )
        logging.info("Conversion completed successfully")
    except Exception as e:
        logging.error(f"Conversion failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
