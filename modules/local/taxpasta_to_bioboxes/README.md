# TAXPASTA_TO_BIOBOXES

## Description

This module converts taxonomic profiling results from taxpasta's standardized TSV format to the CAMI Bioboxes profiling format required for OPAL evaluation.

## Input Format (Taxpasta)

```tsv
taxonomy_id    count
562            1000
1280           500
```

## Output Format (CAMI Bioboxes)

```tsv
@SampleID:sample_1
@Version:0.9.1
@Ranks:superkingdom|phylum|class|order|family|genus|species|strain
@TaxonomyID:NCBI

@@TAXID    RANK       TAXPATH    TAXPATHSN              PERCENTAGE
562        species    131567|2|1224|1236|135622|543|561|562    Biota|Bacteria|...    0.55
```

## Features

- Converts read counts to percentages
- Retrieves taxonomic lineage information using ete3
- Supports custom taxonomic ranks and database identifiers
- Handles missing or invalid taxonomy IDs gracefully
- Includes both full taxonomy paths (IDs) and scientific names

## Usage

### Basic Usage

```groovy
ch_taxpasta = Channel.of([
    [ id: 'sample1' ],
    file('sample1_taxpasta.tsv')
])

TAXPASTA_TO_BIOBOXES(ch_taxpasta)
```

### With Custom Parameters

```groovy
ch_taxpasta = Channel.of([
    [
        id: 'sample1',
        sample_id: 'my_sample',
        ranks: 'domain|phylum|class|order|family|genus|species',
        taxonomy_db: 'NCBI'
    ],
    file('sample1_taxpasta.tsv')
])

TAXPASTA_TO_BIOBOXES(ch_taxpasta)
```

## Parameters

### Meta Map Parameters

- `id` (required): Sample identifier
- `sample_id` (optional): Alternative sample identifier for output (defaults to `id`)
- `ranks` (optional): Pipe-separated taxonomic ranks (default: `superkingdom|phylum|class|order|family|genus|species|strain`)
- `taxonomy_db` (optional): Taxonomy database name (default: `NCBI`)

## Dependencies

- Python 3.11
- pandas >= 2.0
- ete3 >= 3.1.3

## Notes

- The script requires the NCBI taxonomy database for ete3. On first run, ete3 will download the database (~500MB).
- If ete3 is not available, the script falls back to a simplified mode without lineage information.
- For large-scale conversions, consider pre-downloading the NCBI taxonomy database.

## References

- [CAMI Bioboxes Format Specification](https://github.com/bioboxes/rfc/tree/master/data-format)
- [taxpasta Documentation](https://taxpasta.readthedocs.io/)
- [OPAL Evaluation Tool](https://github.com/CAMI-challenge/OPAL)
