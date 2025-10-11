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
[Group by sample_id] - Group classifiers by biological sample
    ↓
[OPAL_PER_SAMPLE] - Per-sample evaluation (one OPAL run per biological sample)
    ↓
[COMPARATIVE_ANALYSIS] - Per-sample classifier comparison (PCA, differential taxa)
    ↓
[MULTIQC] - Aggregate reports
    ↓
Output: Per-sample reports + comparative analysis + aggregated metrics
```

### Sample-Level Architecture

**Core Concept**: The pipeline now supports **per-sample comparative analysis**, where profiles from the same biological sample are evaluated together.

**Key Terminology**:
- **`sample_id`**: Biological sample identifier (grouping key)
  - Profiles with the same `sample_id` are evaluated together in one OPAL run
  - Example: `sample1` → evaluates kraken2, metaphlan, centrifuge together
- **`label`**: Unique identifier for each taxonomic profile
  - Each classifier-sample combination needs a unique label
  - Example: `sample1_kraken2`, `sample1_metaphlan`

**Example Samplesheet**:
```csv
sample_id,label,classifier,taxpasta_file,taxonomy_db
sample1,sample1_kraken2,kraken2,/path/to/sample1_kraken2.tsv,NCBI
sample1,sample1_metaphlan,metaphlan,/path/to/sample1_metaphlan.tsv,NCBI
sample1,sample1_centrifuge,centrifuge,/path/to/sample1_centrifuge.tsv,NCBI
sample2,sample2_kraken2,kraken2,/path/to/sample2_kraken2.tsv,NCBI
sample2,sample2_metaphlan,metaphlan,/path/to/sample2_metaphlan.tsv,NCBI
```

**Result**:
- `sample1`: 1 OPAL run comparing 3 classifiers + 1 comparative analysis report
- `sample2`: 1 OPAL run comparing 2 classifiers + 1 comparative analysis report

**Why This Design**:
- Enables fair classifier comparison (same biological sample, different tools)
- Produces per-sample metrics and visualizations
- Supports PCA and statistical analysis across classifiers
- Allows identification of classifier-specific biases per sample

### Directory Structure

```
.
├── workflows/
│   └── taxbencher.nf               # Main workflow logic
├── modules/
│   ├── local/
│   │   ├── taxpasta_standardise/      # Standardization module (optional)
│   │   ├── taxpasta_to_bioboxes/      # Format conversion module
│   │   ├── opal_per_sample/           # Per-sample OPAL evaluation
│   │   └── comparative_analysis/      # Per-sample classifier comparison
│   └── nf-core/
│       └── multiqc/                   # Report aggregation
├── subworkflows/
│   ├── local/                         # Local subworkflows
│   └── nf-core/                       # nf-core utils
├── bin/
│   ├── taxpasta_to_bioboxes.py       # CAMI format conversion
│   ├── comparative_analysis.py        # Classifier comparison script
│   ├── validate_taxpasta.py           # Taxpasta validation
│   ├── validate_bioboxes.py           # Bioboxes validation
│   └── fix_gold_standard.py           # Gold standard auto-fixer
├── conf/
│   ├── base.config                    # Resource configs
│   ├── test.config                    # Test profile
│   └── modules.config                 # Module-specific configs
├── assets/
│   ├── test_data/                     # Test datasets
│   ├── schema_input.json              # Samplesheet schema
│   └── samplesheet.csv                # Example samplesheet
└── tests/                             # nf-test suites
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

#### OPAL_PER_SAMPLE

**Location**: `modules/local/opal_per_sample/`

**Purpose**: Runs CAMI OPAL evaluation framework for a single biological sample with all its classifiers

**Inputs**:
- `tuple val(meta), path(gold_standard), path(predictions)` - All components bundled in tuple
  - `meta`: Sample metadata (id, sample_id, labels, num_classifiers)
  - `gold_standard`: Ground truth bioboxes
  - `predictions`: List of prediction bioboxes files for this sample_id

**Outputs**:
- `tuple val(meta), path(output_dir)` - OPAL results directory per sample_id
- `path("versions.yml")` - Version tracking

**Container**: `quay.io/biocontainers/cami-opal:1.0.13--pyhdfd78af_0`

**Metrics produced**: Precision, Recall, F1, UniFrac, L1 norm, Jaccard, Shannon diversity, Bray-Curtis

**Why tuple-embedded predictions?**
This module solves a Nextflow channel cardinality problem. The original OPAL module had separate inputs:
```groovy
// Original (problematic for per-sample invocation)
input:
tuple val(meta), path(gold_standard)
path(predictions)  // Separate channel
```

With separate inputs, Nextflow's cardinality matching would send ALL predictions to each OPAL invocation, not just files for that sample_id. The solution is tuple-embedded predictions:
```groovy
// New OPAL_PER_SAMPLE (enables per-sample invocation)
input:
tuple val(meta), path(gold_standard), path(predictions)
```

This allows groupTuple() to create one tuple per sample_id containing only that sample's files.

#### COMPARATIVE_ANALYSIS

**Location**: `modules/local/comparative_analysis/`

**Purpose**: Performs statistical and visual comparison of classifiers within a biological sample

**Inputs**:
- `tuple val(meta), path(opal_dir)` - OPAL results directory for this sample_id
- `path(gold_standard)` - Gold standard bioboxes for differential analysis

**Outputs**:
- `tuple val(meta), path("*_pca.html")` - PCA visualization of classifier performance
- `tuple val(meta), path("*_diff_taxa.tsv")` - Taxa significantly different from gold standard
- `tuple val(meta), path("*_comparison.html")` - Comprehensive comparison report
- `path("versions.yml")` - Version tracking

**Implementation**: Python script `bin/comparative_analysis.py`

**Current Status**: Placeholder infrastructure ready for enhancement
- Defined output formats and specifications
- Creates placeholder HTML/TSV files with correct structure
- Full implementation requires: pandas, scikit-learn, plotly, scipy, statsmodels

**Future Enhancement Roadmap**:
1. **PCA Analysis**: Plot classifiers in PC space based on performance metrics
2. **Statistical Testing**: Chi-square or similar tests for differential abundance
3. **Interactive Visualizations**: Plotly-based HTML reports
4. **Jaccard Similarity**: Heatmap of classifier agreement
5. **Top Misclassifications**: Identify commonly misclassified taxa

**Container**: Uses base Python container (future: add statistical libraries)

### Workflow Logic

**File**: `workflows/taxbencher.nf`

**Key Architecture Pattern 1: Automatic Format Detection & Branching**

The pipeline automatically detects whether inputs need standardization based on file extensions:

```groovy
// Branch input channel based on file extension
ch_input
    .branch { meta, file ->
        standardised: file.name.endsWith('.tsv') || file.name.endsWith('.txt')
            return [meta, file]
        needs_standardisation: true
            return [meta, file]
    }
    .set { ch_branched }

// Standardize raw profiler outputs
TAXPASTA_STANDARDISE(ch_branched.needs_standardisation)

// Mix standardized outputs with already-standardized files
ch_taxpasta = ch_branched.standardised
    .mix(TAXPASTA_STANDARDISE.out.standardised)
```

**Why this pattern matters**:
- **User convenience**: Users can provide either format without changing parameters
- **Efficiency**: Only runs standardization when needed
- **Flexibility**: Supports mixed samplesheets (some raw, some standardized)
- **Transparency**: File extension determines behavior (explicit, predictable)

**Supported extensions triggering standardization**:
- `.kreport` - Kraken2/Bracken reports
- `.report` - Centrifuge reports
- `.out` - Generic profiler outputs (ganon, kaiju, kmcp, mOTUs)
- `.profile`, `.mpa`, `.mpa3` - MetaPhlAn profiles
- `.kaiju` - Kaiju outputs
- `.bracken` - Bracken outputs
- Others: See `schema_input.json` for complete list

**Key Architecture Pattern 2: Per-Sample Grouping with groupTuple()**

The pipeline groups classifiers by biological sample for per-sample OPAL evaluation:

```groovy
// Group bioboxes by sample_id for per-sample OPAL evaluation
// Each biological sample gets its own OPAL run with all its classifiers
ch_bioboxes_per_sample = TAXPASTA_TO_BIOBOXES.out.bioboxes
    .map { meta, bioboxes ->
        [meta.sample_id, meta.label, bioboxes]
    }
    .groupTuple()  // Groups by sample_id: [sample_id, [labels...], [bioboxes...]]
    .combine(ch_gold_standard)
    .map { sample_id, labels, bioboxes_files, gold_std ->
        // Create meta for this sample_id group
        def meta_grouped = [
            id: sample_id,
            sample_id: sample_id,
            labels: labels.join(','),
            num_classifiers: labels.size()
        ]
        // Return: [meta, gold_standard, [bioboxes_files]]
        tuple(meta_grouped, gold_std, bioboxes_files)
    }

// Run OPAL once per sample_id with that sample's bioboxes files
OPAL_PER_SAMPLE(ch_bioboxes_per_sample)
```

**Why this pattern matters**:
- **Fair Comparison**: All classifiers evaluated together for the same biological sample
- **Proper Grouping**: groupTuple() automatically groups by the first element (sample_id)
- **Tuple Embedding**: Predictions embedded in tuple solves Nextflow cardinality matching
- **One OPAL per sample**: Each biological sample gets independent evaluation

**Example Input**:
```
[meta: [sample_id:'sample1', label:'sample1_kraken2'], bioboxes1]
[meta: [sample_id:'sample1', label:'sample1_metaphlan'], bioboxes2]
[meta: [sample_id:'sample2', label:'sample2_kraken2'], bioboxes3]
```

**After groupTuple()**:
```
['sample1', ['sample1_kraken2','sample1_metaphlan'], [bioboxes1, bioboxes2]]
['sample2', ['sample2_kraken2'], [bioboxes3]]
```

**Key operations**:

1. **Branch and standardize if needed**:
   ```groovy
   ch_input.branch { ... }
   TAXPASTA_STANDARDISE(ch_branched.needs_standardisation)
   ch_taxpasta = ch_branched.standardised.mix(TAXPASTA_STANDARDISE.out.standardised)
   ```

2. **Convert taxpasta profiles to CAMI Bioboxes**:
   ```groovy
   TAXPASTA_TO_BIOBOXES(ch_taxpasta)
   ```

3. **Group by sample_id**:
   ```groovy
   ch_bioboxes_per_sample = TAXPASTA_TO_BIOBOXES.out.bioboxes
       .map { meta, bioboxes -> [meta.sample_id, meta.label, bioboxes] }
       .groupTuple()
       .combine(ch_gold_standard)
       .map { /* create meta_grouped */ }
   ```

4. **Run per-sample OPAL evaluation**:
   ```groovy
   OPAL_PER_SAMPLE(ch_bioboxes_per_sample)
   ```

5. **Comparative analysis per sample**:
   ```groovy
   COMPARATIVE_ANALYSIS(
       OPAL_PER_SAMPLE.out.results,
       ch_gold_standard
   )
   ```

**Channel operations explained**:
- `.branch { }` - Split channel into multiple paths based on condition
- `.map { }` - Transform channel items
- `.groupTuple()` - Group by first element, collecting rest into lists
- `.combine()` - Cartesian product with another channel
- `.mix()` - Combine multiple channels into one
- `.first()` - Take only the first emission
- `.collect()` - Gather all items into a single list

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
- `sample_id` - **Biological sample identifier** (required, grouping key for per-sample OPAL)
- `label` - **Unique identifier for this taxonomic profile** (required, distinguishes individual classifier outputs)
- `classifier` - Tool name (required, e.g., kraken2, metaphlan, centrifuge)
- `taxpasta_file` - Path to taxpasta TSV OR raw profiler output (required)
- `taxonomy_db` - Taxonomy DB, default NCBI (optional)

**Key Distinction: sample_id vs label**:
- **sample_id**: Groups profiles from the same biological sample
  - All profiles with the same `sample_id` are evaluated together in one OPAL run
  - Example: `sample1` → combines `sample1_kraken2`, `sample1_metaphlan`, `sample1_centrifuge`
- **label**: Unique identifier for each individual profile
  - Must be unique across the entire samplesheet
  - Used for labeling in OPAL reports and output files
  - Example: `sample1_kraken2`, `sample1_metaphlan`, `sample2_kraken2`

**Input Options**:
The pipeline accepts two input types:

1. **Pre-standardized taxpasta TSV** (.tsv or .txt extension):
```csv
sample_id,label,classifier,taxpasta_file,taxonomy_db
sample1,sample1_kraken2,kraken2,results/sample1_kraken2.tsv,NCBI
sample1,sample1_metaphlan,metaphlan,results/sample1_metaphlan.tsv,NCBI
sample1,sample1_centrifuge,centrifuge,results/sample1_centrifuge.tsv,NCBI
sample2,sample2_kraken2,kraken2,results/sample2_kraken2.tsv,NCBI
```

**Result**: 2 OPAL runs (sample1 with 3 classifiers, sample2 with 1 classifier)

2. **Raw profiler outputs** (automatically standardized):
```csv
sample_id,label,classifier,taxpasta_file,taxonomy_db
sample1,sample1_kraken2,kraken2,results/sample1.kreport,NCBI
sample1,sample1_metaphlan,metaphlan,results/sample1.profile,NCBI
sample1,sample1_centrifuge,centrifuge,results/sample1.report,NCBI
sample2,sample2_kraken2,kraken2,results/sample2.kreport,NCBI
```

**Result**: Same - 2 OPAL runs, but files are auto-standardized first

**Supported file extensions**:
- Taxpasta: `.tsv`, `.txt` (already standardized)
- Kraken2: `.kreport`, `.kreport2`
- Bracken: `.kreport`, `.bracken`
- MetaPhlAn: `.profile`, `.mpa`, `.mpa3`
- Centrifuge: `.report`
- Kaiju: `.kaiju`, `.out`
- ganon: `.ganon`, `.out`
- kmcp: `.kmcp`, `.out`
- mOTUs: `.motus`, `.out`
- DIAMOND: `.diamond`
- MEGAN6/MALT: `.megan`, `.rma6`
- KrakenUniq: `.krakenuniq`

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
│   ├── sample1_metaphlan.bioboxes
│   ├── sample1_centrifuge.bioboxes
│   └── sample2_kraken2.bioboxes
├── opal/
│   ├── sample1/                      # Per-sample OPAL results
│   │   ├── results.html             # Interactive HTML report
│   │   ├── results.tsv              # Metrics table
│   │   ├── confusion.tsv            # Confusion matrix
│   │   └── by_rank/                 # Per-rank breakdowns
│   └── sample2/
│       ├── results.html
│       └── ...
├── comparative_analysis/
│   ├── sample1/
│   │   ├── sample1_pca.html         # PCA plot of classifiers
│   │   ├── sample1_diff_taxa.tsv    # Differential taxa analysis
│   │   └── sample1_comparison.html  # Comprehensive comparison
│   └── sample2/
│       └── ...
├── multiqc/
│   └── multiqc_report.html           # Aggregated report
└── pipeline_info/
    ├── execution_report.html
    ├── execution_timeline.html
    ├── execution_trace.txt
    ├── pipeline_dag.svg
    └── taxbencher_software_mqc_versions.yml
```

**Per-Sample Organization**:
- Each biological sample (`sample_id`) gets its own subdirectory in `opal/` and `comparative_analysis/`
- OPAL results contain metrics comparing all classifiers for that sample
- Comparative analysis provides statistical comparison and visualizations
- MultiQC aggregates metrics across all samples

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

For detailed validation and testing information, see:
- [VALIDATION_REPORT.md](VALIDATION_REPORT.md) - Quick overview
- [TEST_COVERAGE_REPORT.md](TEST_COVERAGE_REPORT.md) - Honest detailed assessment

**nf-test coverage**: 14/22 tests passing (64%)

**Profile requirements**:
- `TAXPASTA_STANDARDISE`: ✅ Works with docker/conda
- `TAXPASTA_TO_BIOBOXES`: ⚠️ Requires conda/wave (no pre-built container with pandas+ete3)
- `OPAL`: ⚠️ Works but OPAL 1.0.13 has bugs with minimal test data
- `OPAL_PER_SAMPLE`: ⚠️ Stub tests only (OPAL bugs)
- `COMPARATIVE_ANALYSIS`: ⚠️ Stub tests only, requires conda/wave for functional tests
- Full pipeline: ❌ Fails at OPAL_PER_SAMPLE with test data

**Recommended testing approaches**:
```bash
# Module tests with conda (best coverage)
nf-test test modules/local/taxpasta_to_bioboxes/tests/ --profile conda

# Full pipeline with realistic data
nextflow run . --input real_data.csv --gold_standard gold.bioboxes --outdir results -profile conda

# CI/CD with stub tests (structure validation only)
nf-test test --tag stub_only --profile docker
```

**Known limitations**:
- No pre-built containers for Python scientific stack → Use conda or wave profile
- OPAL 1.0.13 spider plot bug with minimal datasets → Use larger realistic data
- Full pipeline tests expected to fail with minimal test data → Not a pipeline bug
- Stub tests verify module structure but not functionality → Documented in TEST_COVERAGE_REPORT.md

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

**Per-sample grouping pattern** (NEW):
```groovy
// Group by sample_id for per-sample processing
ch_grouped = ch_input
    .map { meta, file -> [meta.sample_id, meta.label, file] }
    .groupTuple()  // Groups by first element (sample_id)
    .combine(ch_reference)
    .map { sample_id, labels, files, ref ->
        def meta_grouped = [
            id: sample_id,
            sample_id: sample_id,
            labels: labels.join(','),
            num_items: labels.size()
        ]
        tuple(meta_grouped, ref, files)
    }
```

**Why this pattern is important**:
- Enables per-sample processing (e.g., one OPAL run per biological sample)
- groupTuple() automatically groups by the first element in the tuple
- Creates a new meta map with aggregated information (labels, count)
- Embedding files in tuple solves Nextflow cardinality matching issues

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

