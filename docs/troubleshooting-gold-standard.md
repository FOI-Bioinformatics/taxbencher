# Troubleshooting Gold Standard Files

This guide helps you validate and fix gold standard files for taxbencher/OPAL evaluation.

## Quick Validation

Always validate your gold standard file before running the pipeline:

```bash
python3 bin/validate_bioboxes.py gold_standard.bioboxes
```

## Common Issues and Fixes

### Issue 1: Column Count Mismatch

**Error:**

```
CRITICAL: Column count mismatch! Header has 5 columns but first data row has 4 columns.
```

**Cause:** The column header lists TAXPATH but the data rows are missing that column.

**Fix:**

```bash
python3 bin/fix_gold_standard.py \
  -i gold_standard.bioboxes \
  -o gold_standard_fixed.bioboxes \
  -s your_sample_id
```

### Issue 2: Unsupported Ranks

**Error:**

```
CRITICAL: Data contains unsupported ranks for OPAL: ['cellular root', 'domain', 'no rank', 'root', 'unknown']
```

**Cause:** OPAL only supports standard CAMI ranks: `superkingdom`, `phylum`, `class`, `order`, `family`, `genus`, `species`, `strain`

**Fix:** The `fix_gold_standard.py` script automatically:

- Reconstructs TAXPATH/TAXPATHSN from the NCBI taxonomy (ete3), one element per rank of `@Ranks`
- Filters out unsupported ranks (root, no rank, kingdom, cellular root, etc.)
- Maps `domain` → `superkingdom` and `subspecies`/`no rank` below species → `strain`; taxa below the strain
  level are aggregated into their strain ancestor
- Optionally derives higher ranks from species/strain level truth (`--fill-higher-ranks`)
- Optionally rescales every rank to exactly 100 % (`--renormalise`)

Pass `--taxdump taxdump.tar.gz` to use the same pinned NCBI taxonomy as the pipeline (`--taxdump`); without
it ete3 downloads the current taxonomy into `~/.etetoolkit`.

### Issue 2b: Abundances do not sum to 100 % per rank

CAMI profiles are _per rank_: the entries of each rank (all species, all genera, ...) sum to 100 %, so a file
with eight ranks sums to 800 % in total. A gold standard whose ranks sum to much less than 100 % (for example
one that was normalised across all ranks) makes every OPAL abundance metric (L1 norm, Bray-Curtis, UniFrac)
meaningless. `validate_bioboxes.py` reports the per-rank sums; fix with
`fix_gold_standard.py --renormalise` when every organism of the sample is represented at each rank.

### Issue 2c: Only species (or strain) level truth is available

Simulated datasets often provide the truth at the species or strain level only. OPAL evaluates every rank in
`@Ranks`, so missing higher ranks count as "nothing is true at this rank" and every prediction becomes a false
positive. Derive the higher ranks from the leaves:

```bash
python3 bin/fix_gold_standard.py -i truth_species.tsv -o gold_standard.bioboxes \
  -s my_sample --taxdump taxdump.tar.gz --fill-higher-ranks
```

The input may be a plain `TAXID<TAB>RANK<TAB>PERCENTAGE` table with the four `@` header lines.

### Issue 2d: Sample ID does not match the samplesheet

OPAL matches predictions to the gold standard by `@SampleID` and silently skips profiles without a match.
The pipeline therefore refuses to start when a `sample_id` from the samplesheet has no `@SampleID` block in the
gold standard. Multi-sample gold standards (several `@SampleID` blocks in one file, separated by their own
header lines) are supported; validate them with `validate_bioboxes.py --sample-id <id> ...`.

### Issue 3: Missing Required Headers

**Error:**

```
Missing required header: @TaxonomyID
```

**Fix:** Add required metadata headers to your file:

```
@SampleID:your_sample_name
@Version:0.9.1
@Ranks:superkingdom|phylum|class|order|family|genus|species|strain
@TaxonomyID:NCBI
```

## Validation Workflow

```bash
# 1. Validate your gold standard
python3 bin/validate_bioboxes.py gold_standard.bioboxes

# 2. If validation fails, fix the file
python3 bin/fix_gold_standard.py \
  -i gold_standard.bioboxes \
  -o gold_standard_fixed.bioboxes \
  -s my_sample

# 3. Validate the fixed file
python3 bin/validate_bioboxes.py gold_standard_fixed.bioboxes

# 4. Run the pipeline with the fixed file
nextflow run . \
  --input samplesheet.csv \
  --gold_standard gold_standard_fixed.bioboxes \
  --outdir results \
  -profile docker
```

## Validator Features

The enhanced `validate_bioboxes.py` script checks:

✓ **Critical Issues (will cause OPAL to fail):**

- Missing required headers (@SampleID, @Version, @Ranks, @TaxonomyID)
- Missing required columns (TAXID, RANK, TAXPATH, TAXPATHSN, PERCENTAGE)
- Column count mismatch between header and data rows
- Unsupported ranks in data (root, no rank, unknown, cellular root, domain, kingdom, subspecies)

✓ **Data Quality Issues:**

- Invalid TAXIDs (non-integer or non-positive)
- Invalid percentages (out of range 0-100)
- Percentages not summing to ~100%
- Duplicate TAXID entries
- TAXPATH format validation
- TAXPATHSN/TAXPATH element count matching

✓ **Statistics:**

- Total data rows
- Unique TAXIDs
- Percentage range and sum
- Ranks found

## Examples

### Valid File (passes all checks):

```
@SampleID:test1
@Version:0.9.1
@Ranks:superkingdom|phylum|class|order|family|genus|species|strain
@TaxonomyID:NCBI
@@TAXID	RANK	TAXPATH	TAXPATHSN	PERCENTAGE
2	superkingdom	1|131567|2	root|cellular organisms|Bacteria	50.0
1224	phylum	1|131567|2|1224	root|cellular organisms|Bacteria|Pseudomonadota	30.0
1236	class	1|131567|2|1224|1236	root|cellular organisms|Bacteria|Pseudomonadota|Gammaproteobacteria	20.0
```

Output:

```
✓ VALID: File conforms to CAMI Bioboxes format
```

### Invalid File (will fail):

```
@SampleID:test1
@Version:0.9.1
@Ranks:superkingdom|phylum|class
@TaxonomyID:NCBI
@@TAXID	RANK	TAXPATH	TAXPATHSN	PERCENTAGE
1	root	root	100.0
2	superkingdom	Bacteria	50.0
```

Output:

```
✗ CRITICAL: Column count mismatch! Header has 5 columns but first data row has 4 columns.
✗ CRITICAL: Data contains unsupported ranks: ['root']
✗ INVALID: File has format issues
```

## Integration with Pipeline

The validator can be run as a pre-flight check before launching the pipeline:

```bash
#!/bin/bash
# validate_and_run.sh

GOLD_STANDARD="gold_standard.bioboxes"

# Validate first
if python3 bin/validate_bioboxes.py "$GOLD_STANDARD"; then
    echo "✓ Validation passed, running pipeline..."
    nextflow run . --gold_standard "$GOLD_STANDARD" --input samplesheet.csv -profile docker
else
    echo "✗ Validation failed. Please fix the gold standard file first."
    echo "Hint: Use bin/fix_gold_standard.py to automatically fix common issues"
    exit 1
fi
```

## Reference

- CAMI Bioboxes format: https://github.com/bioboxes/rfc/tree/master/data-format
- OPAL documentation: https://github.com/CAMI-challenge/OPAL
- taxbencher pipeline: https://github.com/FOI-Bioinformatics/taxbencher
