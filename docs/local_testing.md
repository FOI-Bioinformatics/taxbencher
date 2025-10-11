# Local Testing Guide

This document provides guidance for testing taxbencher components locally without Docker/Singularity.

## Known Issues

### OPAL Bokeh Compatibility

**Issue**: OPAL 1.0.5 is incompatible with bokeh >= 3.0

```
ImportError: cannot import name 'Panel' from 'bokeh.models.widgets'
```

**Root cause**: Bokeh 3.x removed the `Panel` class, but OPAL 1.0.5 still imports it.

**Solutions**:

1. **Use containers** (RECOMMENDED - what the pipeline does):
   ```bash
   # Pipeline uses: quay.io/biocontainers/cami-opal:1.0.13--pyhdfd78af_0
   # This works correctly
   ```

2. **Downgrade bokeh** (for local testing):
   ```bash
   pip install 'bokeh<3.0' 'cami-opal==1.0.5'
   ```

3. **Upgrade OPAL** (may have other issues):
   ```bash
   pip install 'cami-opal>=1.0.13'
   ```

4. **Use isolated environment**:
   ```bash
   conda create -n opal_local python=3.10 -y
   conda activate opal_local
   conda install -c bioconda cami-opal=1.0.13
   ```

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
# Test taxpasta_standardise
nf-test test modules/local/taxpasta_standardise/tests/main.nf.test

# Test taxpasta_to_bioboxes
nf-test test modules/local/taxpasta_to_bioboxes/tests/main.nf.test

# Test OPAL (uses container, should work)
nf-test test modules/local/opal/tests/main.nf.test

# Test OPAL_PER_SAMPLE (stub tests due to known OPAL HTML bug)
nf-test test modules/local/opal_per_sample/tests/main.nf.test

# Test COMPARATIVE_ANALYSIS (stub tests)
nf-test test modules/local/comparative_analysis/tests/main.nf.test
```

### Test full pipeline

```bash
# Test with Docker (RECOMMENDED)
nf-test test tests/default.nf.test -profile test,docker

# Test with Singularity
nf-test test tests/default.nf.test -profile test,singularity

# Test with conda (may have OPAL issues)
nf-test test tests/default.nf.test -profile test,conda
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

### 1. ete3 downloads NCBI taxonomy on first run

**Symptom**: First run of taxpasta_to_bioboxes.py is slow

**Solution**: This is normal. ete3 downloads ~500MB taxonomy database on first use. Subsequent runs use cached data.

**Location**: `~/.etetoolkit/taxa.sqlite`

### 2. Container not found

**Symptom**: `biocontainers/cami-opal:1.0.13--pyhdfd78af_0` not found

**Solution**: Pull container manually:
```bash
docker pull quay.io/biocontainers/cami-opal:1.0.13--pyhdfd78af_0
```

### 3. Taxpasta validation fails

**Symptom**: Script exits with column errors

**Solution**: Ensure TSV has tab-separated columns with header:
```
taxonomy_id	count
562	1000
```

### 4. Bioboxes validation fails

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
