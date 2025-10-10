# Raw Profiler Input Guide

This guide describes how to use raw taxonomic profiler outputs directly with taxbencher, without requiring pre-standardization through taxpasta.

## Overview

taxbencher automatically detects and standardizes raw profiler outputs using the integrated TAXPASTA_STANDARDISE module. You can provide either:

1. **Pre-standardized** taxpasta TSV files (`.tsv`, `.txt`)
2. **Raw profiler outputs** (automatically standardized during pipeline execution)

The pipeline determines which inputs need standardization based on file extension.

## Supported Profilers

taxbencher supports all profilers compatible with [taxpasta](https://taxpasta.readthedocs.io/):

| Profiler | Supported Versions | Common Extensions | Format Description |
|----------|-------------------|-------------------|-------------------|
| **Bracken** | Latest | `.kreport`, `.bracken` | Kraken-style report with re-estimated abundances |
| **Centrifuge** | Latest | `.report` | 6-column TSV: percentage, numReads, numUniqueReads, rank, taxID, name |
| **DIAMOND** | Latest | `.diamond`, `.tsv` | Taxonomic assignment output from DIAMOND+MEGAN workflow |
| **ganon** | Latest | `.ganon`, `.out` | ganon taxonomic profiling output |
| **Kaiju** | Latest | `.kaiju`, `.out` | Kaiju taxonomic classification summary |
| **KMCP** | Latest | `.kmcp`, `.out` | KMCP profiling results |
| **Kraken2** | Latest | `.kreport`, `.kreport2` | 6-column report: percentage, clade_reads, taxon_reads, rank, taxID, name |
| **KrakenUniq** | Latest | `.krakenuniq`, `.kreport` | KrakenUniq-specific report format |
| **MEGAN6/MALT** | MEGAN6 | `.megan`, `.rma6` | MEGAN6 taxonomic summary files |
| **MetaPhlAn** | 3.x, 4.x | `.profile`, `.mpa`, `.mpa3` | 4-column TSV: clade_name, NCBI_tax_id, relative_abundance, additional_species |
| **mOTUs** | Latest | `.motus`, `.out` | mOTUs taxonomic profiling output |

## File Extension Detection

The pipeline uses file extensions to determine processing:

### Standardized Format (Pass-Through)
- `.tsv` - taxpasta standardized TSV
- `.txt` - taxpasta standardized text file

**These files bypass standardization** and go directly to bioboxes conversion.

### Raw Formats (Auto-Standardized)
All other extensions trigger the TAXPASTA_STANDARDISE module:
- `.kreport`, `.kreport2` - Kraken2/Bracken
- `.report` - Centrifuge
- `.out` - Kaiju/ganon/KMCP/mOTUs
- `.profile`, `.mpa`, `.mpa3` - MetaPhlAn
- `.diamond` - DIAMOND
- `.motus` - mOTUs
- `.megan`, `.rma6` - MEGAN6
- `.krakenuniq` - KrakenUniq
- `.kaiju` - Kaiju
- `.bracken` - Bracken
- `.ganon` - ganon
- `.kmcp` - KMCP

## Samplesheet Format

### Example with Raw Profiler Outputs

```csv
sample,classifier,taxpasta_file,taxonomy_db
sample1,kraken2,/path/to/sample1.kreport,NCBI
sample1,metaphlan,/path/to/sample1.profile,NCBI
sample1,centrifuge,/path/to/sample1.report,NCBI
sample2,kaiju,/path/to/sample2.kaiju.out,NCBI
sample2,bracken,/path/to/sample2.bracken,NCBI
```

### Example with Pre-Standardized Files

```csv
sample,classifier,taxpasta_file,taxonomy_db
sample1,kraken2,/path/to/sample1_kraken2.tsv,NCBI
sample1,metaphlan,/path/to/sample1_metaphlan.tsv,NCBI
```

### Mixed Format (Both Raw and Standardized)

```csv
sample,classifier,taxpasta_file,taxonomy_db
sample1,kraken2,/path/to/sample1.kreport,NCBI
sample1,metaphlan,/path/to/sample1_metaphlan.tsv,NCBI
sample2,centrifuge,/path/to/sample2_centrifuge.tsv,NCBI
```

The pipeline handles mixed inputs automatically based on file extension.

## Column Specifications

### Required Columns

1. **sample** (string, no spaces)
   - Sample identifier for grouping results
   - Example: `sample1`, `patient_42`, `site_A`

2. **classifier** (string, no spaces)
   - Taxonomic profiler name
   - Must match one of the supported profilers
   - Example: `kraken2`, `metaphlan`, `centrifuge`

3. **taxpasta_file** (file path)
   - Path to profiler output file
   - Must exist and be readable
   - Extension determines processing (standardized vs. raw)

### Optional Columns

4. **taxonomy_db** (string, default: `NCBI`)
   - Taxonomy database used by the profiler
   - Options: `NCBI`, `GTDB`
   - Used for taxonomy lookups during bioboxes conversion

## Format Requirements by Profiler

### Bracken
**Format**: Kraken-style report (6 columns, tab-separated)
```
percentage  clade_reads  taxon_reads  rank  taxID  scientific_name
```
**Extensions**: `.kreport`, `.bracken`

### Centrifuge
**Format**: Report format (6 columns, tab-separated)
```
percentage  numReads  numUniqueReads  rank  taxID  name
```
**Extensions**: `.report`

**Example**:
```
50.00	5	5	S	562	Escherichia coli
30.00	3	3	S	1280	Staphylococcus aureus
20.00	2	2	S	272631	Burkholderia pseudomallei
```

### DIAMOND
**Format**: DIAMOND taxonomic assignment output
**Extensions**: `.diamond`, `.tsv`

### ganon
**Format**: ganon profiling output
**Extensions**: `.ganon`, `.out`

### Kaiju
**Format**: Kaiju summary table
**Extensions**: `.kaiju`, `.out`

### KMCP
**Format**: KMCP profiling results
**Extensions**: `.kmcp`, `.out`

### Kraken2
**Format**: Report format (6 columns, tab-separated)
```
percentage  clade_reads  taxon_reads  rank  taxID  scientific_name
```
**Extensions**: `.kreport`, `.kreport2`

**Example**:
```
 99.95	9995	9995	U	0	unclassified
  0.05	5	0	R	1	root
  0.03	3	0	D	2	  Bacteria
  0.02	2	0	P	1224	    Pseudomonadota
  0.01	1	1	G	561	            Escherichia
```

### KrakenUniq
**Format**: KrakenUniq-specific report
**Extensions**: `.krakenuniq`, `.kreport`

### MEGAN6/MALT
**Format**: MEGAN6 taxonomic summary
**Extensions**: `.megan`, `.rma6`

### MetaPhlAn
**Format**: Profile format (4 columns, tab-separated)
```
clade_name  NCBI_tax_id  relative_abundance  additional_species
```
**Extensions**: `.profile`, `.mpa`, `.mpa3`

**Example**:
```
#clade_name	NCBI_tax_id	relative_abundance	additional_species
k__Bacteria	2	98.5
p__Proteobacteria	1224	85.3
c__Gammaproteobacteria	1236	75.2
o__Enterobacterales	91347	60.1
f__Enterobacteriaceae	543	55.0
g__Escherichia	561	50.0
s__Escherichia_coli	562	50.0
```

**Note**: MetaPhlAn files must have 4 columns. The `additional_species` column may be empty but must be present.

### mOTUs
**Format**: mOTUs profiling output
**Extensions**: `.motus`, `.out`

## Workflow Architecture

### Automatic Format Detection

The pipeline uses Nextflow channel branching to detect formats:

```groovy
ch_samplesheet
    .branch { meta, file ->
        raw: !(file.toString().endsWith('.tsv') || file.toString().endsWith('.txt'))
        standardised: file.toString().endsWith('.tsv') || file.toString().endsWith('.txt')
    }
    .set { ch_branched }
```

### Processing Flow

```
Raw Profiler Outputs (.kreport, .report, .profile, etc.)
    ↓
[TAXPASTA_STANDARDISE] - Convert to taxpasta TSV format
    ↓
    ├──→ Mix with pre-standardized files (.tsv, .txt)
    ↓
[TAXPASTA_TO_BIOBOXES] - Convert to CAMI Bioboxes format
    ↓
[OPAL] - Evaluate against gold standard
    ↓
Results
```

### Channel Operations

1. **Branch**: Split inputs by format
   - `raw`: Files needing standardization
   - `standardised`: Files ready for bioboxes conversion

2. **Standardize**: Run taxpasta on raw files
   ```groovy
   TAXPASTA_STANDARDISE(ch_branched.raw)
   ```

3. **Mix**: Combine standardized outputs
   ```groovy
   ch_taxpasta = TAXPASTA_STANDARDISE.out.tsv.mix(ch_branched.standardised)
   ```

4. **Convert**: Transform to bioboxes format
   ```groovy
   TAXPASTA_TO_BIOBOXES(ch_taxpasta)
   ```

## Integration with nf-core/taxprofiler

taxbencher is designed to work seamlessly with outputs from [nf-core/taxprofiler](https://nf-co.re/taxprofiler).

### Using taxprofiler Outputs

If you ran taxprofiler with `--run_taxpasta`, use the standardized TSV files:

```bash
# taxprofiler output
taxprofiler_results/taxpasta/*.tsv
```

**Samplesheet**:
```csv
sample,classifier,taxpasta_file,taxonomy_db
sample1,kraken2,taxprofiler_results/taxpasta/sample1_kraken2.tsv,NCBI
sample1,metaphlan,taxprofiler_results/taxpasta/sample1_metaphlan.tsv,NCBI
```

If you have raw profiler outputs from taxprofiler:

```bash
# taxprofiler raw outputs
taxprofiler_results/kraken2/*.kreport
taxprofiler_results/metaphlan/*.profile
taxprofiler_results/centrifuge/*.report
```

**Samplesheet**:
```csv
sample,classifier,taxpasta_file,taxonomy_db
sample1,kraken2,taxprofiler_results/kraken2/sample1.kreport,NCBI
sample1,metaphlan,taxprofiler_results/metaphlan/sample1.profile,NCBI
sample1,centrifuge,taxprofiler_results/centrifuge/sample1.report,NCBI
```

## Validation

### Pre-Flight Checks

Before running the pipeline, validate your files:

**For standardized files**:
```bash
python3 bin/validate_taxpasta.py /path/to/sample.tsv
```

**For gold standard**:
```bash
python3 bin/validate_bioboxes.py gold_standard.bioboxes
```

### Common Issues

#### Issue: "Unexpected report format. It has X columns but only Y are expected"

**Cause**: Profiler output format doesn't match taxpasta expectations

**Solutions**:
- Verify profiler version compatibility
- Check that output file is in the correct format (e.g., Centrifuge report, not classification output)
- Consult profiler documentation for output format options

#### Issue: "Column not found in header"

**Cause**: Missing required columns in profiler output

**Solutions**:
- MetaPhlAn files must have 4 columns (including `additional_species`)
- Centrifuge must use report format (6 columns), not classification format (8 columns)
- Check profiler run parameters to ensure correct output format

#### Issue: "File extension not recognized"

**Cause**: File extension not in schema validation pattern

**Solutions**:
- Use one of the supported extensions listed above
- Rename file to use standard extension (e.g., `.kreport` for Kraken2)
- For standardized files, use `.tsv` or `.txt`

## Testing

The pipeline includes comprehensive tests for raw profiler inputs:

**Test raw profiler standardization**:
```bash
nf-test test modules/local/taxpasta_standardise/tests/main.nf.test
```

**Test full pipeline with raw inputs**:
```bash
nextflow run . -profile test_raw,conda
```

**Test with your own data**:
```bash
nextflow run . \
  --input samplesheet_raw.csv \
  --gold_standard gold_standard.bioboxes \
  --outdir results \
  -profile docker
```

## Performance Considerations

### When to Pre-Standardize

**Use raw inputs** when:
- Working with fresh profiler outputs
- Processing outputs from nf-core/taxprofiler without taxpasta
- Simplifying workflow (one less manual step)

**Pre-standardize with taxpasta** when:
- Processing large batches (can parallelize independently)
- Reusing standardized files across multiple analyses
- Troubleshooting format issues (easier to inspect TSV)

### Resource Requirements

The TAXPASTA_STANDARDISE module is lightweight:
- CPU: 2 cores (default)
- Memory: 6 GB (default)
- Time: < 1 minute per file (typically)

For large files or many samples, consider:
- Running on compute cluster with parallel execution
- Using `-profile conda` or `-profile singularity` for better reproducibility
- Adjusting `conf/base.config` resource allocations if needed

## References

- **taxpasta documentation**: https://taxpasta.readthedocs.io/
- **nf-core/taxprofiler**: https://nf-co.re/taxprofiler
- **CAMI Bioboxes format**: https://github.com/bioboxes/rfc/tree/master/data-format
- **Supported profilers**: https://taxpasta.readthedocs.io/en/latest/supported_profilers/

## Example Workflows

### Workflow 1: Kraken2 + MetaPhlAn Comparison

```bash
# Samplesheet: samplesheet.csv
# sample,classifier,taxpasta_file,taxonomy_db
# sample1,kraken2,data/sample1.kreport,NCBI
# sample1,metaphlan,data/sample1.profile,NCBI

nextflow run FOI-Bioinformatics/taxbencher \
  --input samplesheet.csv \
  --gold_standard gold_standard.bioboxes \
  --outdir results/kraken_vs_metaphlan \
  -profile docker
```

### Workflow 2: Multi-Tool Benchmarking

```bash
# Samplesheet with 5 profilers per sample
# sample,classifier,taxpasta_file,taxonomy_db
# sample1,kraken2,data/sample1.kreport,NCBI
# sample1,metaphlan,data/sample1.profile,NCBI
# sample1,centrifuge,data/sample1.report,NCBI
# sample1,kaiju,data/sample1.kaiju.out,NCBI
# sample1,bracken,data/sample1.bracken,NCBI

nextflow run FOI-Bioinformatics/taxbencher \
  --input samplesheet_multitool.csv \
  --gold_standard gold_standard.bioboxes \
  --outdir results/multitool_benchmark \
  -profile singularity \
  -resume
```

### Workflow 3: Mixed Standardized and Raw

```bash
# Samplesheet mixing formats
# sample,classifier,taxpasta_file,taxonomy_db
# sample1,kraken2,standardized/sample1_kraken2.tsv,NCBI
# sample1,metaphlan,raw/sample1.profile,NCBI
# sample2,centrifuge,raw/sample2.report,NCBI

nextflow run FOI-Bioinformatics/taxbencher \
  --input samplesheet_mixed.csv \
  --gold_standard gold_standard.bioboxes \
  --outdir results/mixed_formats \
  -profile conda
```

## Troubleshooting

### Enable Verbose Logging

```bash
nextflow run . -profile test_raw,docker -with-trace -with-report -with-timeline
```

### Check Standardization Output

Standardized files are published to:
```
results/taxpasta_standardise/
├── sample1_kraken2_standardised.tsv
├── sample1_metaphlan_standardised.tsv
└── sample1_centrifuge_standardised.tsv
```

Inspect these files to verify standardization:
```bash
head results/taxpasta_standardise/sample1_kraken2_standardised.tsv
```

Expected format:
```
taxonomy_id	count
562	50
1280	30
272631	20
```

### Check Bioboxes Conversion

Bioboxes files are published to:
```
results/taxpasta_to_bioboxes/
├── sample1_kraken2.bioboxes
├── sample1_metaphlan.bioboxes
└── sample1_centrifuge.bioboxes
```

Validate bioboxes format:
```bash
python3 bin/validate_bioboxes.py results/taxpasta_to_bioboxes/sample1_kraken2.bioboxes
```

### Debug Profile Detection

Add this to your samplesheet to test detection:
```csv
sample,classifier,taxpasta_file,taxonomy_db
test_raw,kraken2,test.kreport,NCBI
test_std,kraken2,test.tsv,NCBI
```

The `.kreport` file will trigger standardization, `.tsv` will not.
