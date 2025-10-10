# Troubleshooting Guide

This guide covers common issues and their solutions when running taxbencher.

## Table of Contents

- [Apple Silicon (M1/M2/M3) Issues](#apple-silicon-m1m2m3-issues)
- [Container Issues](#container-issues)
- [Input Validation Errors](#input-validation-errors)
- [OPAL Failures](#opal-failures)

## Apple Silicon (M1/M2/M3) Issues

### MultiQC "Illegal Instruction" Error

**Symptom:**
```
ERROR ~ Error executing process > 'MULTIQC'
Caused by:
  Process `MULTIQC` terminated with an error exit status (132)
Command error:
  .command.sh: line 11:    44 Illegal instruction     multiqc --force --config multiqc_config.yml .
```

**Cause:** Docker containers on Apple Silicon Macs are AMD64/x86_64 images that require emulation. Some containers (especially those built by Wave on-the-fly) don't work well with Rosetta 2 emulation.

**Solution 1: Use Conda Profile (Recommended)**
```bash
nextflow run FOI-Bioinformatics/taxbencher \
  -profile conda \
  --input samplesheet.csv \
  --gold_standard gold_standard.bioboxes \
  --outdir results
```

Conda installs native ARM64 packages and avoids all emulation issues.

**Solution 2: Accept MultiQC Failure**

The core benchmarking processes (TAXPASTA_STANDARDISE, TAXPASTA_TO_BIOBOXES, OPAL) complete successfully even when MultiQC fails. You'll get:

✅ All OPAL metrics and evaluation results
✅ Individual HTML reports from OPAL
✅ TSV files with all metrics
❌ Only the aggregated MultiQC report fails

**What you lose:** The pretty MultiQC summary report that combines all modules.
**What you keep:** All the important benchmarking data and OPAL-generated reports.

**Solution 3: Enable Platform Emulation**

Update Docker Desktop settings:
1. Open Docker Desktop
2. Go to Settings → Features in development
3. Enable "Use Rosetta for x86_64/amd64 emulation on Apple Silicon"
4. Restart Docker

Then try adding the `arm` profile:
```bash
nextflow run FOI-Bioinformatics/taxbencher \
  -profile docker,wave,arm \
  --input samplesheet.csv \
  --gold_standard gold_standard.bioboxes \
  --outdir results
```

Note: This may still fail with Wave-built containers but is worth trying.

## Container Issues

### "No module named 'pandas'" Error

**Symptom:**
```
ERROR ~ Error executing process > 'TAXPASTA_TO_BIOBOXES'
Command error:
  ModuleNotFoundError: No module named 'pandas'
```

**Cause:** Running with `-profile docker` without `-profile wave`. The base `biocontainers/python:3.11` image lacks pandas and ete3.

**Solution:** Always use Wave with Docker:
```bash
# Correct
nextflow run FOI-Bioinformatics/taxbencher -profile docker,wave

# Alternative: Use conda
nextflow run FOI-Bioinformatics/taxbencher -profile conda
```

### "Manifest not found" Error

**Symptom:**
```
docker: Error response from daemon: manifest for community.wave.seqera.io/library/pandas_python_pip:xxxxx not found
```

**Cause:** Trying to use Docker without Wave enabled. The hardcoded container doesn't exist.

**Solution:** Enable Wave:
```bash
nextflow run FOI-Bioinformatics/taxbencher -profile docker,wave
```

## Input Validation Errors

### "Column not found: TAXPATH" Error

**Symptom:**
```
ERROR: Column count mismatch in data row
Expected 5 columns (TAXID, RANK, TAXPATH, TAXPATHSN, PERCENTAGE)
Found: 4 columns
```

**Cause:** Gold standard file has missing or malformed columns.

**Solution:** Use the validation and fixing tools:

```bash
# Validate to see the issue
python3 bin/validate_bioboxes.py gold_standard.bioboxes

# Automatically fix common issues
python3 bin/fix_gold_standard.py \
  -i gold_standard.bioboxes \
  -o gold_standard_fixed.bioboxes \
  -s your_sample_id
```

See [Gold Standard Troubleshooting](troubleshooting-gold-standard.md) for detailed guide.

### "Unsupported rank" Errors

**Symptom:**
```
ERROR: Found unsupported OPAL ranks in gold standard:
  - 'no rank' appears 45 times
  - 'subspecies' appears 12 times
  - 'domain' appears 8 times
```

**Cause:** Gold standard contains taxonomic ranks that OPAL doesn't support.

**Solution:** Use `fix_gold_standard.py` to filter and map ranks:

```bash
python3 bin/fix_gold_standard.py \
  -i gold_standard.bioboxes \
  -o gold_standard_fixed.bioboxes \
  -s sample_id
```

The script automatically:
- Filters unsupported ranks (no rank, root, domain, kingdom, subspecies, etc.)
- Maps compatible ranks (domain→superkingdom, subspecies→strain)
- Renormalizes percentages after filtering

### Raw Profiler Format Errors

**Symptom:**
```
ERROR: Unexpected report format. It has 8 columns but only 6 are expected
```

**Cause:** Wrong profiler output format. For example, Centrifuge has both "classification" (8 columns) and "report" (6 columns) formats. Taxpasta expects the report format.

**Solution:** Validate your profiler output format:

```bash
# Check if your file matches the expected format
python3 bin/validate_profiler_format.py centrifuge sample.report

# Show what format is expected
python3 bin/validate_profiler_format.py centrifuge --show-spec
```

See [docs/raw-inputs.md](raw-inputs.md) for detailed format specifications for all 11 supported profilers.

## OPAL Failures

### "KeyError: 'no rank'" in OPAL

**Symptom:**
```
File "cami_opal/plots.py", line 502, in plot_purity_completeness_per_tool_and_rank
  index = rank_to_index[rank]
KeyError: 'no rank'
```

**Cause:** Gold standard or prediction files contain "no rank" entries that OPAL can't handle.

**Solution:** Fix the gold standard:

```bash
python3 bin/fix_gold_standard.py \
  -i gold_standard.bioboxes \
  -o gold_standard_fixed.bioboxes \
  -s sample_id
```

For prediction files, this should be handled automatically by `taxpasta_to_bioboxes.py`, but if it persists, check that your profiler outputs are correctly formatted.

### OPAL HTML Generation Fails

**Symptom:**
```
OPAL completes but no HTML plots are generated, or partial plots only
```

**Known Issue:** OPAL 1.0.13 has bugs when generating HTML plots for single-sample datasets. This is an upstream OPAL issue, not a taxbencher issue.

**Workaround:**
- Use multiple samples/classifiers in your benchmark (recommended)
- OPAL will successfully generate:
  - All metrics in TSV format ✅
  - Some plots (rarefaction curves, beta diversity) ✅
  - May fail on others (purity/completeness per tool) ❌

**Impact:** Metrics calculation is unaffected. Only visualization is impacted.

## Performance Issues

### Slow Docker Performance on Apple Silicon

**Symptom:** Pipeline runs very slowly when using Docker on M1/M2/M3 Macs.

**Cause:** x86_64 emulation overhead.

**Solutions:**
1. **Use Conda** (native ARM64, no emulation):
   ```bash
   nextflow run FOI-Bioinformatics/taxbencher -profile conda
   ```

2. **Enable Rosetta in Docker Desktop:**
   - Settings → Features in development
   - Enable "Use Rosetta for x86_64/amd64 emulation"
   - Provides ~4-5x speedup vs QEMU emulation

3. **Increase Docker Resources:**
   - Settings → Resources
   - Increase CPUs and Memory allocation

### Out of Memory Errors

**Symptom:**
```
ERROR ~ Error executing process > 'OPAL'
Exit status: 137 (out of memory)
```

**Solutions:**

1. **Increase process memory** in `conf/base.config`:
   ```groovy
   withLabel: process_high {
       cpus   = 8
       memory = 32.GB  // Increase this
   }
   ```

2. **Limit samples:**
   - Benchmark fewer samples/classifiers at once
   - Split large benchmarks into batches

3. **Use HPC/Cloud:**
   - Run on systems with more resources
   - Use `-profile cluster` or cloud executor

## Getting Help

If you encounter issues not covered here:

1. **Check logs:**
   ```bash
   cat .nextflow.log
   cat work/<task_hash>/.command.log
   ```

2. **Run with debug:**
   ```bash
   nextflow run FOI-Bioinformatics/taxbencher -profile conda --input samplesheet.csv --gold_standard gold.bioboxes --outdir results -with-trace -with-report -with-timeline
   ```

3. **Report issues:**
   - GitHub: https://github.com/FOI-Bioinformatics/taxbencher/issues
   - Include: Platform, profile used, error message, relevant logs

## Quick Reference

### Recommended Profiles by Platform

| Platform | Use This | Avoid This |
|----------|----------|------------|
| Linux x86_64 | `docker,wave` or `singularity,wave` | - |
| Linux ARM64 | `conda` | `docker` (AMD64 only) |
| macOS Intel | `docker,wave` or `conda` | - |
| macOS Apple Silicon | `conda` | `docker,wave` (MultiQC issues) |
| HPC Cluster | `singularity` or `conda` | `docker` (often not available) |

### Common Command Patterns

**Basic run (conda):**
```bash
nextflow run FOI-Bioinformatics/taxbencher -profile conda --input samplesheet.csv --gold_standard gold.bioboxes --outdir results
```

**With raw profiler inputs:**
```bash
nextflow run FOI-Bioinformatics/taxbencher -profile conda --input samplesheet_raw.csv --gold_standard gold.bioboxes --save_standardised_profiles --outdir results
```

**Resume failed run:**
```bash
nextflow run FOI-Bioinformatics/taxbencher -profile conda --input samplesheet.csv --gold_standard gold.bioboxes --outdir results -resume
```

**With debugging:**
```bash
nextflow run FOI-Bioinformatics/taxbencher -profile conda --input samplesheet.csv --gold_standard gold.bioboxes --outdir results -with-trace -with-report -with-timeline
```
