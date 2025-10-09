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
- Filters out unsupported ranks (root, no rank, unknown, cellular root, etc.)
- Maps `subspecies` → `strain` and `domain`/`kingdom` → `superkingdom`
- Renormalizes percentages to sum to 100%

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
