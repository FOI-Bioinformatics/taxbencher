# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Subagent
**Active Subagent**: `bioinformatics-pipeline-dev`

## Overview

**taxbencher** is an nf-core compliant Nextflow pipeline for benchmarking taxonomic classifiers. It evaluates classifier predictions against ground truth using CAMI OPAL metrics.

**Key characteristics:**
- Nextflow DSL2 workflow (≥24.10.5)
- nf-core template v3.3.2 compliance
- **Accepts both raw profiler outputs AND pre-standardized taxpasta TSV files**
- Automatic format detection and standardization
- Supports 10+ taxonomic profilers (Kraken2, MetaPhlAn, Centrifuge, Kaiju, Bracken, and more)
- Uses CAMI OPAL for evaluation metrics
- Biocontainer-based reproducibility
- nf-test suite for validation

**NOT in scope:**
- Synthetic data generation (use external tools or CAMI datasets)
- Running classifiers (use nf-core/taxprofiler)
- Database building (use nf-core/createtaxdb)

## Quick Start

```bash
# Test the pipeline
nextflow run . -profile test,docker

# Test with raw profiler outputs
nextflow run . -profile test_raw,docker

# Run with real data (taxpasta TSV files)
nextflow run . \
  --input samplesheet.csv \
  --gold_standard gold_standard.bioboxes \
  --outdir results \
  -profile docker

# Run with raw profiler outputs (automatically standardized)
nextflow run . \
  --input samplesheet_raw.csv \
  --gold_standard gold_standard.bioboxes \
  --outdir results \
  --save_standardised_profiles \
  -profile docker
```

## Technical Stack
- **Workflow Language**: Nextflow DSL2
- **Framework**: nf-core template
- **Testing**: nf-test
- **Containers**: Docker/Singularity
- **Languages**: Python for utility scripts

## Key Requirements
1. Follow nf-core pipeline structure and guidelines
2. Implement comprehensive nf-test suites for all processes
3. Ensure reproducibility with proper containerization
4. Include proper documentation and parameter validation
5. Support resume functionality and error handling

## Architecture

### Pipeline Flow

```
Input: Raw profiler outputs OR taxpasta TSV files + gold standard bioboxes
    ↓
[TAXPASTA_STANDARDISE] - Standardize raw profiler outputs (optional, automatic)
    ↓
[TAXPASTA_TO_BIOBOXES] - Convert to CAMI format
    ↓
[OPAL] - Evaluate predictions
    ↓
[MULTIQC] - Aggregate reports
    ↓
Output: HTML reports + metrics
```

### Directory Structure

```
.
├── workflows/
│   └── taxbencher.nf          # Main workflow logic
├── modules/
│   ├── local/
│   │   ├── taxpasta_standardise/   # Standardization module (optional)
│   │   ├── taxpasta_to_bioboxes/   # Format conversion module
│   │   └── opal/                    # OPAL evaluation module
│   └── nf-core/
│       └── multiqc/                # Report aggregation
├── subworkflows/
│   ├── local/                      # Local subworkflows
│   └── nf-core/                    # nf-core utils
├── bin/
│   └── taxpasta_to_bioboxes.py    # Python conversion script
├── conf/
│   ├── base.config                 # Resource configs
│   ├── test.config                 # Test profile
│   └── modules.config              # Module-specific configs
├── assets/
│   ├── test_data/                  # Test datasets
│   ├── schema_input.json           # Samplesheet schema
│   └── samplesheet.csv             # Example samplesheet
└── tests/                          # nf-test suites
```

### Key Modules

#### TAXPASTA_STANDARDISE

**Location**: `modules/local/taxpasta_standardise/`

**Purpose**: Converts raw profiler outputs to taxpasta TSV format (runs automatically when needed)

**Inputs**:
- `tuple val(meta), path(profiler_output)` - Raw profiler output file
- Meta fields: `id`, `classifier`, `taxonomy_db`

**Outputs**:
- `tuple val(meta), path("*.tsv")` - Standardized taxpasta TSV
- `path("versions.yml")` - Version tracking

**Implementation**:
- Uses `taxpasta standardise` command
- Automatically triggered for non-.tsv/.txt file extensions
- Supports: Bracken, Centrifuge, DIAMOND, ganon, Kaiju, Kraken2, KrakenUniq, MEGAN6/MALT, MetaPhlAn, mOTUs

**Container**: `biocontainers/taxpasta:0.7.0--pyhdfd78af_0`

**When it runs**: Automatically when input files have extensions like `.kreport`, `.out`, `.profile`, `.mpa`, etc.

#### TAXPASTA_TO_BIOBOXES

**Location**: `modules/local/taxpasta_to_bioboxes/`

**Purpose**: Converts taxpasta TSV format to CAMI profiling Bioboxes format

**Inputs**:
- `tuple val(meta), path(taxpasta_tsv)` - Taxpasta profile
- Meta fields: `id`, `sample_id`, `taxonomy_db` (default: NCBI)

**Outputs**:
- `tuple val(meta), path("*.bioboxes")` - CAMI Bioboxes format
- `path("versions.yml")` - Version tracking

**Implementation**:
- Python script: `bin/taxpasta_to_bioboxes.py`
- Uses ete3 for NCBI taxonomy lookups
- Handles lineage path construction
- Calculates percentage from counts

**Container**: `biocontainers/python:3.11` (with conda env for ete3)

#### OPAL

**Location**: `modules/local/opal/`

**Purpose**: Runs CAMI OPAL evaluation framework

**Inputs**:
- `tuple val(meta), path(gold_standard)` - Ground truth bioboxes
- `path(predictions)` - Collected prediction bioboxes files
- Meta optional: `labels`, `filter`, `normalize`, `rank`

**Outputs**:
- `tuple val(meta), path(output_dir)` - OPAL results directory
- `path("versions.yml")` - Version tracking

**Container**: `quay.io/biocontainers/cami-opal:1.0.13--pyhdfd78af_0`

**Metrics produced**: Precision, Recall, F1, UniFrac, L1 norm, Jaccard, Shannon diversity, Bray-Curtis

### Workflow Logic

**File**: `workflows/taxbencher.nf`

**Key Architecture Pattern: Automatic Format Detection & Branching**

The pipeline automatically detects whether inputs need standardization based on file extensions:

```groovy
// Branch input channel based on file extension
ch_samplesheet
    .branch { meta, file ->
        raw: !(file.toString().endsWith('.tsv') || file.toString().endsWith('.txt'))
        standardised: file.toString().endsWith('.tsv') || file.toString().endsWith('.txt')
    }
    .set { ch_branched }

// Standardize raw profiler outputs
TAXPASTA_STANDARDISE(ch_branched.raw)

// Mix standardized outputs with already-standardized files
ch_taxpasta = TAXPASTA_STANDARDISE.out.tsv.mix(ch_branched.standardised)
```

**Why this pattern matters**:
- **User convenience**: Users can provide either format without changing parameters
- **Efficiency**: Only runs standardization when needed
- **Flexibility**: Supports mixed samplesheets (some raw, some standardized)
- **Transparency**: File extension determines behavior (explicit, predictable)

**Supported extensions triggering standardization**:
- `.kreport` - Kraken2/Bracken reports
- `.report` - Centrifuge reports
- `.out` - Generic profiler outputs
- `.profile`, `.mpa` - MetaPhlAn profiles
- `.kaiju` - Kaiju outputs
- Others: See `schema_input.json` for complete list

**Key operations**:

1. **Branch and standardize if needed**:
   ```groovy
   // Automatic format detection
   ch_samplesheet.branch { ... }
   TAXPASTA_STANDARDISE(ch_branched.raw)
   ch_taxpasta = TAXPASTA_STANDARDISE.out.tsv.mix(ch_branched.standardised)
   ```

2. **Convert taxpasta profiles to CAMI Bioboxes**:
   ```groovy
   TAXPASTA_TO_BIOBOXES(ch_taxpasta)
   ```

3. **Collect bioboxes files for OPAL**:
   ```groovy
   ch_bioboxes_collected = TAXPASTA_TO_BIOBOXES.out.bioboxes
       .map { meta, bioboxes -> bioboxes }
       .collect()
   ```

4. **Collect labels for OPAL**:
   ```groovy
   ch_bioboxes_labels = TAXPASTA_TO_BIOBOXES.out.bioboxes
       .map { meta, bioboxes -> meta.id }
       .collect()
       .map { labels -> labels.join(',') }
   ```

5. **Run OPAL evaluation**:
   ```groovy
   OPAL(ch_gold_with_meta, ch_bioboxes_collected)
   ```

**Channel operations explained**:
- `.branch { }` - Split channel into multiple paths based on condition
- `.map { }` - Transform channel items
- `.collect()` - Gather all items into a single list
- `.mix()` - Combine multiple channels into one
- `.first()` - Take only the first emission

## Development Workflow

###  Development Guidelines
- All processes should be modular and reusable
- Use nf-core modules where available
- Implement proper logging and error messages
- Follow semantic versioning
- Ensure FAIR compliance


### Adding a New Module

1. **Create module structure**:
   ```bash
   mkdir -p modules/local/mymodule
   cd modules/local/mymodule
   ```

2. **Create files**:
   - `main.nf` - Process definition
   - `meta.yml` - Module metadata
   - `tests/main.nf.test` - nf-test suite
   - `environment.yml` - Conda environment (if needed)

3. **Follow nf-core patterns**:
   ```groovy
   process MYMODULE {
       tag "$meta.id"
       label 'process_low'  // or medium/high

       conda "${moduleDir}/environment.yml"
       container "biocontainers/tool:version"

       input:
       tuple val(meta), path(input_file)

       output:
       tuple val(meta), path("*.out"), emit: results
       path "versions.yml"           , emit: versions

       script:
       """
       tool --input $input_file --output ${meta.id}.out

       cat <<-END_VERSIONS > versions.yml
       "${task.process}":
           tool: \$(tool --version | sed 's/^.*version //')
       END_VERSIONS
       """
   }
   ```

4. **Write nf-test**:
   ```groovy
   nextflow_process {
       name "Test MYMODULE"
       script "modules/local/mymodule/main.nf"
       process "MYMODULE"

       test("Should run successfully") {
           when {
               process {
                   """
                   input[0] = [ [id:'test'], file('test.input') ]
                   """
               }
           }
           then {
               assert process.success
               assert snapshot(process.out).match()
           }
       }
   }
   ```

5. **Test the module**:
   ```bash
   nf-test test modules/local/mymodule/tests/main.nf.test
   ```

### Modifying Workflows

**File**: `workflows/taxbencher.nf`

**Best practices**:
- Keep `ch_versions` tracking for all modules
- Mix module outputs into `ch_multiqc_files` for reporting
- Use descriptive channel names (prefix with `ch_`)
- Document channel operations with comments
- Preserve emit block structure

**Example addition**:
```groovy
// Add new process
MYPROCESS(ch_input)
ch_versions = ch_versions.mix(MYPROCESS.out.versions)
ch_multiqc_files = ch_multiqc_files.mix(MYPROCESS.out.results)
```

### Configuration

**Add module config** in `conf/modules.config`:
```groovy
process {
    withName: 'TAXPASTA_TO_BIOBOXES' {
        ext.args = ''
        publishDir = [
            path: { "${params.outdir}/taxpasta_to_bioboxes" },
            mode: params.publish_dir_mode,
            saveAs: { filename -> filename.equals('versions.yml') ? null : filename }
        ]
    }
}
```

**Update schema** in `nextflow_schema.json`:
- Add new parameters to appropriate section
- Include validation rules (type, format, exists)
- Provide help text

### Testing

**Run full test suite**:
```bash
nf-test test --profile test,docker
```

**Run specific test**:
```bash
nf-test test modules/local/opal/tests/main.nf.test
```

**Update snapshots**:
```bash
nf-test test --update-snapshot
```

**Test profiles**:
- `test` - Minimal dataset with pre-standardized taxpasta TSV files
- `test_raw` - Minimal dataset with raw profiler outputs (kraken2)
- `docker` - Docker containers
- `singularity` - Singularity containers
- `conda` - Conda environments

## Input/Output

### Samplesheet Format

**File**: CSV with header

**Columns**:
- `sample` - Sample identifier (required)
- `classifier` - Tool name (required, e.g., kraken2, metaphlan, centrifuge)
- `taxpasta_file` - Path to taxpasta TSV OR raw profiler output (required)
- `taxonomy_db` - Taxonomy DB, default NCBI (optional)

**Input Options**:
The pipeline accepts two input types:

1. **Pre-standardized taxpasta TSV** (.tsv or .txt extension):
```csv
sample,classifier,taxpasta_file,taxonomy_db
sample1,kraken2,results/sample1_kraken2.tsv,NCBI
sample1,metaphlan,results/sample1_metaphlan.tsv,NCBI
```

2. **Raw profiler outputs** (automatically standardized):
```csv
sample,classifier,taxpasta_file,taxonomy_db
sample1,kraken2,results/sample1_kraken2.kreport,NCBI
sample1,metaphlan,results/sample1_metaphlan.profile,NCBI
sample1,centrifuge,results/sample1_centrifuge.out,NCBI
```

**Supported file extensions**:
- Taxpasta: `.tsv`, `.txt`
- Kraken2/KrakenUniq: `.kreport`
- MetaPhlAn: `.profile`, `.mpa`
- Centrifuge: `.out`
- Other profilers: `.kaiju`, `.bracken`, `.ganon`, `.motus`, `.megan`, `.rma6`

**Validation**: `assets/schema_input.json`

**Note**: The pipeline automatically detects file type by extension and applies standardization when needed.

### Gold Standard Format

**File**: CAMI profiling Bioboxes format

**Structure**:
```
@SampleID:benchmark
@Version:0.9.1
@Ranks:superkingdom|phylum|class|order|family|genus|species
@TaxonomyID:NCBI
@@TAXID	RANK	TAXPATH	TAXPATHSN	PERCENTAGE
562	species	131567|2|...	Biota|Bacteria|...	0.50
```

### Output Structure

```
results/
├── taxpasta_to_bioboxes/
│   ├── sample1_kraken2.bioboxes
│   └── sample1_metaphlan.bioboxes
├── opal/
│   └── benchmark/
│       ├── results.html
│       └── metrics.txt
├── multiqc/
│   └── multiqc_report.html
└── pipeline_info/
    ├── execution_report.html
    └── taxbencher_software_mqc_versions.yml
```

## Integration Points

### Upstream: nf-core/taxprofiler

taxbencher accepts taxpasta files from taxprofiler:

```bash
# Run taxprofiler
nextflow run nf-core/taxprofiler \
  --input samples.csv \
  --databases databases.csv \
  --outdir taxprofiler_results \
  --run_taxpasta

# Use taxprofiler output in taxbencher
nextflow run taxbencher \
  --input samplesheet_from_taxprofiler.csv \
  --gold_standard gold_standard.bioboxes \
  --outdir benchmark_results
```

### Test Data Sources

**CAMI datasets**:
- Portal: https://data.cami-challenge.org/participate
- Toy datasets: Publicly available, no restrictions
- Full datasets: Require registration

**Test data included**:
- Located in `assets/test_data/`
- Taxpasta TSV samples from multiple classifiers
- Bioboxes gold standard file
- Minimal but complete for pipeline testing

## Validation Infrastructure

The pipeline includes comprehensive validation tools for data quality assurance.

### Validation Scripts

**Location**: `bin/` directory

#### validate_taxpasta.py

Validates taxpasta TSV format before pipeline execution:

```bash
python3 bin/validate_taxpasta.py input.tsv
```

**Checks**:
- Required columns: `taxonomy_id`, `count`
- Valid data types (integers for taxid, numbers for count)
- Positive values only
- No duplicate taxonomy IDs
- Statistics: read counts, unique taxa

**Exit codes**:
- 0: Valid file
- 1: Validation errors found

#### validate_bioboxes.py

Validates CAMI Bioboxes profiling format with **CRITICAL OPAL compatibility checks**:

```bash
python3 bin/validate_bioboxes.py gold_standard.bioboxes
```

**CRITICAL Checks (will cause OPAL to fail)**:
- ✓ Required headers: `@SampleID`, `@Version`, `@Ranks`, `@TaxonomyID`
- ✓ Required columns: `TAXID`, `RANK`, `TAXPATH`, `TAXPATHSN`, `PERCENTAGE`
- ✓ **Column count mismatch** between header and data rows
- ✓ **Unsupported OPAL ranks** in data (root, no rank, unknown, cellular root, domain, kingdom, subspecies)
- ✓ Unsupported ranks in header (must be: superkingdom, phylum, class, order, family, genus, species, strain)

**Data Quality Checks**:
- TAXPATH format (pipe-separated taxonomy IDs)
- TAXPATHSN matches TAXPATH length
- Percentages in valid range (0-100)
- Percentages sum to ~100%
- No duplicate TAXIDs
- Valid TAXIDs (positive integers)

**Exit codes**:
- 0: Valid file
- 1: Validation errors found

**Common Issues**:
If validation fails, use `fix_gold_standard.py` to automatically fix common issues. See [Gold Standard Troubleshooting](docs/troubleshooting-gold-standard.md).

#### fix_gold_standard.py

Automatically fixes common gold standard file issues:

```bash
python3 bin/fix_gold_standard.py \
  -i gold_standard.bioboxes \
  -o gold_standard_fixed.bioboxes \
  -s sample_id
```

**Automatic Fixes**:
- ✓ Adds missing TAXPATH column (uses taxid as placeholder or ete3 for full lineage)
- ✓ Adds missing required headers (@SampleID, @Version, @Ranks, @TaxonomyID)
- ✓ Filters out unsupported OPAL ranks (root, no rank, unknown, cellular root, etc.)
- ✓ Maps non-standard ranks (subspecies → strain, domain/kingdom → superkingdom)
- ✓ Renormalizes percentages to sum to 100% after filtering
- ✓ Fixes column count mismatches

**Options**:
- `-i, --input`: Input bioboxes file
- `-o, --output`: Output fixed file
- `-s, --sample-id`: Sample ID for @SampleID header (default: gold_standard)

**Note**: The script works without ete3 (uses placeholder TAXPATHs) but produces better results with ete3 installed for full taxonomy lineage lookup.

### Validation Workflow

**Recommended pre-flight checks**:

```bash
# 1. Validate samplesheet format
head samplesheet.csv

# 2. Validate all taxpasta files
for f in /path/to/taxpasta/*.tsv; do
    python3 bin/validate_taxpasta.py "$f" || echo "FAILED: $f"
done

# 3. Validate gold standard (CRITICAL - must pass before running pipeline)
python3 bin/validate_bioboxes.py gold_standard.bioboxes

# 4. If validation fails, fix the gold standard automatically
if [ $? -ne 0 ]; then
    echo "Validation failed. Fixing gold standard..."
    python3 bin/fix_gold_standard.py \
        -i gold_standard.bioboxes \
        -o gold_standard_fixed.bioboxes \
        -s my_sample

    # Re-validate the fixed file
    python3 bin/validate_bioboxes.py gold_standard_fixed.bioboxes
    GOLD_STANDARD="gold_standard_fixed.bioboxes"
else
    GOLD_STANDARD="gold_standard.bioboxes"
fi

# 5. Run pipeline with validated gold standard
nextflow run . \
    --input samplesheet.csv \
    --gold_standard "$GOLD_STANDARD" \
    --outdir results \
    -profile docker
```

**Critical validation checks added in v1.0.1**:
- Column count mismatch detection (header vs data rows)
- Unsupported OPAL rank detection (root, no rank, unknown, etc.)
- These checks prevent cryptic OPAL failures during pipeline execution

### Test Coverage

For detailed validation and testing information, see [VALIDATION_REPORT.md](VALIDATION_REPORT.md).

**nf-test coverage**:
- `TAXPASTA_TO_BIOBOXES`: 3/3 tests pass (basic, custom params, stub)
- `OPAL`: Core functionality verified (metrics, plots generated)
- Full test suite: `nf-test test --profile test,docker`

**Known limitations**:
- OPAL HTML generation fails with single-sample datasets (OPAL 1.0.13 bug)
- This only affects minimal test data, not production use
- All core metrics and evaluation functions work correctly

## Common Patterns

### Channel Operations

**Create from samplesheet**:
```groovy
ch_input = samplesheet.map { meta ->
    [meta, file(meta.file_path)]
}
```

**Collect multiple files**:
```groovy
ch_collected = ch_files.collect()
```

**Group by key**:
```groovy
ch_grouped = ch_input.groupTuple()
```

**Combine with value channel**:
```groovy
ch_combined = ch_input.combine(ch_value)
```

### Version Tracking

Always emit versions.yml:
```groovy
cat <<-END_VERSIONS > versions.yml
"${task.process}":
    tool: \$(tool --version)
END_VERSIONS
```

### Error Handling

Use `when:` for conditional execution:
```groovy
when:
task.ext.when == null || task.ext.when
```

## Common Issues

**Module not found**: Check `include` statement and module path

**Channel empty**: Use `.view()` to debug channel contents

**Container not found**: Verify container exists on biocontainers/quay.io

**Test fails**: Check if snapshots need updating with `--update-snapshot`

**Samplesheet validation fails**: Verify `assets/schema_input.json` matches format

## References

- **nf-core**: https://nf-co.re/
- **Nextflow docs**: https://nextflow.io/docs/latest/
- **nf-test**: https://www.nf-test.com/
- **CAMI OPAL**: https://github.com/CAMI-challenge/OPAL
- **taxpasta**: https://taxpasta.readthedocs.io/
- **nf-core/taxprofiler**: https://nf-co.re/taxprofiler
- **Bioboxes format**: https://github.com/bioboxes/rfc/tree/master/data-format

