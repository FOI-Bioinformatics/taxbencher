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
- Retrieves taxonomic lineages from taxpasta lineage columns or, otherwise, from an NCBI taxdump via taxopy
  (merged taxonomy IDs are translated to their current ID)
- Supports custom taxonomic ranks and database identifiers
- Reports unknown taxonomy IDs and fails instead of writing an empty profile
- Includes both full taxonomy paths (IDs) and scientific names

## Usage

### Basic Usage

```groovy
ch_taxpasta = Channel.of([
    [ id: 'sample1' ],
    file('sample1_taxpasta.tsv')
])

// taxdump directory (nodes.dmp, names.dmp, merged.dmp) from PREPARE_TAXDUMP, or [] for profiles
// that carry taxpasta lineage columns
PREPARE_TAXDUMP(file('taxdump.tar.gz'))
TAXPASTA_TO_BIOBOXES(ch_taxpasta, PREPARE_TAXDUMP.out.taxdump)
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

TAXPASTA_TO_BIOBOXES(ch_taxpasta, PREPARE_TAXDUMP.out.taxdump)
```

## Parameters

### Meta Map Parameters

- `id` (required): Sample identifier
- `sample_id` (optional): Alternative sample identifier for output (defaults to `id`)
- `ranks` (optional): Pipe-separated taxonomic ranks (default: `superkingdom|phylum|class|order|family|genus|species|strain`)
- `taxonomy_db` (optional): Taxonomy database name (default: `NCBI`)

## Dependencies

- Python 3.12, pandas 2.2 and taxopy 0.12 (all in `quay.io/biocontainers/taxpasta:0.7.0--pyhdfd78af_0`)

## Notes

- Without a taxdump (and without lineage columns) the script downloads the current NCBI taxdump (~80 MB) in every
  task; pass `--taxdump` to the pipeline for reproducible, offline runs.
- Loading the full NCBI taxonomy takes about 15 s and 3 GB of memory per task (the `process_single` label
  provides 6 GB).

## References

- [CAMI Bioboxes Format Specification](https://github.com/bioboxes/rfc/tree/master/data-format)
- [taxpasta Documentation](https://taxpasta.readthedocs.io/)
- [OPAL Evaluation Tool](https://github.com/CAMI-challenge/OPAL)
