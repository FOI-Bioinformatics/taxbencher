# Local Testing Guide

This document provides guidance for testing taxbencher components locally.

## Critical Requirements

### Container vs Conda Profile

⚠️ **IMPORTANT**: Some modules require conda/wave profile due to missing pre-built containers.

**Modules requiring conda/wave**:
- `TAXPASTA_TO_BIOBOXES` - needs pandas + ete3
- `COMPARATIVE_ANALYSIS` - needs pandas + scikit-learn + plotly + scipy + statsmodels

**Recommended profiles**:
```bash
# Development/testing (slower first run, cached after)
nextflow run . -profile test,conda

# Production (automatic container building)
nextflow run . -profile test,wave

# CI/CD (only works for some modules)
nextflow run . -profile test,docker
```

## Known Issues

### 1. Container Dependency Gaps

**Issue**: No pre-built biocontainers exist with full Python scientific stack

**Affected modules**:
- `TAXPASTA_TO_BIOBOXES` (modules/local/taxpasta_to_bioboxes/main.nf:5-10)
- `COMPARATIVE_ANALYSIS` (modules/local/comparative_analysis/main.nf:5-10)

**Error with docker profile**:
```
ModuleNotFoundError: No module named 'pandas'
```

**Solution**: Use conda or wave profile
```bash
# Conda (recommended for local testing)
nf-test test modules/local/taxpasta_to_bioboxes/tests/ --profile conda

# Wave (recommended for production)
nextflow run . -profile test,wave
```

**First-time conda build**: ~5-10 minutes (subsequent runs use cached environment)

### 2. OPAL 1.0.13 Spider Plot Bug

**Issue**: OPAL fails to generate spider plots with minimal test datasets

**Error**:
```
ValueError: x and y must have same first dimension, but have shapes (3,) and (0,)
at cami_opal/plots.py:382 in spider_plot
```

**Root cause**: OPAL's plotting code assumes more data points than minimal test sets provide

**Impact**:
- ❌ HTML report generation fails
- ✅ Core metrics are computed correctly
- ❌ Full pipeline tests fail at OPAL_PER_SAMPLE
- ✅ This is NOT a bug in taxbencher

**Workarounds**:
1. Use stub tests for CI/CD
2. Test with larger, realistic datasets
3. Accept that minimal test data triggers OPAL bugs

**Container**: `quay.io/biocontainers/cami-opal:1.0.13--pyhdfd78af_0`

### 3. ete3 NCBI Taxonomy Download

**Issue**: First run of `taxpasta_to_bioboxes.py` downloads ~500MB NCBI taxonomy database

**Timing**:
- First run: ~2-3 minutes (downloading + indexing)
- Subsequent runs: instant (cached at `~/.etetoolkit/taxa.sqlite`)

**Solution**: This is expected behavior, not a bug

## Testing Components

### 1. Test taxpasta_to_bioboxes.py

The conversion script can be tested independently:

```bash
# Test with sample data
python3 bin/taxpasta_to_bioboxes.py \
  --input assets/test_data/taxpasta/sample1_kraken2.tsv \
  --output test_output.bioboxes \
  --sample_id test_sample \
  --no-ete3  # Skip taxonomy lookups for quick test

# Test with taxonomy lookups (requires ete3)
python3 bin/taxpasta_to_bioboxes.py \
  --input assets/test_data/taxpasta/sample1_kraken2.tsv \
  --output test_output.bioboxes \
  --sample_id test_sample
```

**Requirements**:
```bash
pip install pandas ete3
```

**Expected output**: Valid CAMI Bioboxes format file

### 2. Test OPAL (if fixed)

```bash
# Test OPAL with sample data
opal.py \
  --gold_standard_file assets/test_data/gold_standard.bioboxes \
  --output_dir test_opal_output \
  modules/local/opal/tests/testdata/prediction1.bioboxes
```

**Requirements**: See "OPAL Bokeh Compatibility" above

### 3. Test taxpasta

```bash
# Validate taxpasta works
taxpasta --version

# Test standardization (if you have classifier outputs)
taxpasta standardise \
  --profiler kraken2 \
  --output test.tsv \
  input_kraken2.txt
```

## Validation Scripts

The pipeline includes pre-flight validation scripts to check data quality before running. These tools help catch format issues early and provide detailed error messages.

> [!TIP]
> Always run validation scripts on your input files before starting the pipeline to avoid runtime errors.

### validate_taxpasta.py

Validates taxpasta TSV format:

```bash
python3 bin/validate_taxpasta.py assets/test_data/taxpasta/sample1_kraken2.tsv
```

Checks:
- Required columns (taxonomy_id, count)
- Valid data types
- Positive counts
- No duplicates

### validate_bioboxes.py

Validates CAMI Bioboxes format:

```bash
python3 bin/validate_bioboxes.py assets/test_data/gold_standard.bioboxes
```

Checks:
- Required headers
- Required columns
- TAXPATH format
- Percentage values

## Running nf-test

### Test individual modules

```bash
# Test taxpasta_standardise (works with docker)
nf-test test modules/local/taxpasta_standardise/tests/main.nf.test --profile docker

# Test taxpasta_to_bioboxes (REQUIRES CONDA)
nf-test test modules/local/taxpasta_to_bioboxes/tests/main.nf.test --profile conda

# Test OPAL (partial - OPAL bugs with minimal data)
nf-test test modules/local/opal/tests/main.nf.test --profile docker

# Test OPAL_PER_SAMPLE (stub tests only - OPAL bugs)
nf-test test modules/local/opal_per_sample/tests/main.nf.test --profile docker

# Test COMPARATIVE_ANALYSIS (stub tests only - requires conda for functional)
nf-test test modules/local/comparative_analysis/tests/main.nf.test --profile docker
```

### Test full pipeline

⚠️ **Expected to fail** at OPAL_PER_SAMPLE due to OPAL 1.0.13 bugs with minimal test data

```bash
# Test with conda (best coverage)
nf-test test tests/default.nf.test --profile test,conda
# Expected: Fails at OPAL_PER_SAMPLE spider plot

# Test with docker (partial coverage)
nf-test test tests/default.nf.test --profile test,docker
# Expected: Fails at TAXPASTA_TO_BIOBOXES (missing deps)

# Test with wave (automatic container building)
nf-test test tests/default.nf.test --profile test,wave
# Expected: Should work but untested
```

### Realistic testing approach

For comprehensive testing, use realistic data instead of minimal test data:

```bash
# With larger dataset (avoids OPAL bugs)
nextflow run . \
  --input samplesheet_realistic.csv \
  --gold_standard gold_standard_realistic.bioboxes \
  --outdir results \
  -profile conda
```

### Generate snapshots

```bash
# Update all snapshots after changes
nf-test test --update-snapshot modules/local/taxpasta_standardise/tests/
nf-test test --update-snapshot modules/local/taxpasta_to_bioboxes/tests/
nf-test test --update-snapshot modules/local/opal/tests/
nf-test test --update-snapshot modules/local/opal_per_sample/tests/
nf-test test --update-snapshot modules/local/comparative_analysis/tests/
nf-test test --update-snapshot tests/
```

## Common Issues

### 1. ModuleNotFoundError: No module named 'pandas'

**Symptom**: TAXPASTA_TO_BIOBOXES or COMPARATIVE_ANALYSIS fails with missing module

**Cause**: Using docker/singularity profile without suitable container

**Solution**: Switch to conda or wave profile
```bash
nextflow run . -profile test,conda
# or
nextflow run . -profile test,wave
```

### 2. OPAL spider plot ValueError

**Symptom**: `ValueError: x and y must have same first dimension, but have shapes (3,) and (0,)`

**Cause**: OPAL 1.0.13 bug with minimal test datasets

**Impact**: This is expected with test data, NOT a pipeline bug

**Solution**:
- Accept that minimal test data triggers this
- Use stub tests for CI/CD
- Test with realistic data for validation

### 3. ete3 downloads NCBI taxonomy on first run

**Symptom**: First run of taxpasta_to_bioboxes.py is slow (~2-3 minutes)

**Cause**: ete3 downloads ~500MB taxonomy database on first use

**Solution**: This is normal behavior. Subsequent runs use cached data at `~/.etetoolkit/taxa.sqlite`

### 4. Conda environment build takes 10 minutes

**Symptom**: First nf-test with conda profile is very slow

**Cause**: Building conda environments from scratch

**Solution**:
- This is normal on first run
- Environments are cached in `work/conda/` or `.nextflow/conda/`
- Subsequent runs reuse cached environments (~30 seconds)
- Use `-resume` to avoid rebuilds

### 5. Container not found

**Symptom**: `biocontainers/cami-opal:1.0.13--pyhdfd78af_0` not found

**Solution**: Pull container manually:
```bash
docker pull quay.io/biocontainers/cami-opal:1.0.13--pyhdfd78af_0
```

### 6. Taxpasta validation fails

**Symptom**: Script exits with column errors

**Solution**: Ensure TSV has tab-separated columns with header:
```
taxonomy_id	count
562	1000
```

### 7. Bioboxes validation fails

**Symptom**: OPAL can't parse file

**Solution**: Check format exactly matches specification:
- Headers start with `@`
- Column headers start with `@@`
- Tab-separated values
- No extra whitespace

## Debugging Tips

### Enable verbose logging

```bash
# Python scripts
python3 bin/taxpasta_to_bioboxes.py --verbose ...

# Nextflow
nextflow run . -profile test,docker -with-trace -with-report -with-timeline
```

### Check intermediate files

```bash
# Look at work directory
ls -la work/*/*/

# Check specific task
cat work/XX/XXXXXXXX/.command.log
cat work/XX/XXXXXXXX/.command.err
```

### Validate outputs manually

```bash
# Check bioboxes format
head assets/test_data/gold_standard.bioboxes

# Check taxpasta format
head assets/test_data/taxpasta/sample1_kraken2.tsv

# Validate with scripts
python3 bin/validate_taxpasta.py file.tsv
python3 bin/validate_bioboxes.py file.bioboxes
```

## CI/CD Testing

The GitHub Actions workflows test with:
- Docker profile (primary)
- Multiple Nextflow versions
- Linting and formatting checks

See `.github/workflows/` for details.
