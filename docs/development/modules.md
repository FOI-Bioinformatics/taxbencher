# Module Specifications

This document provides detailed specifications for all modules in the taxbencher pipeline.

## Table of Contents
- [Module Overview](#module-overview)
- [TAXPASTA_STANDARDISE](#taxpasta_standardise)
- [TAXPASTA_TO_BIOBOXES](#taxpasta_to_bioboxes)
- [OPAL_PER_SAMPLE](#opal_per_sample)
- [COMPARATIVE_ANALYSIS](#comparative_analysis)
- [MULTIQC](#multiqc)
- [Module Development Guidelines](#module-development-guidelines)

## Module Overview

### Local Modules

| Module | Purpose | Status | Container Strategy |
|--------|---------|--------|-------------------|
| TAXPASTA_STANDARDISE | Convert raw profiler outputs to taxpasta TSV | ✅ Production | Biocontainer |
| TAXPASTA_TO_BIOBOXES | Convert taxpasta TSV to CAMI Bioboxes | ✅ Production | Wave (pandas+ete3) |
| OPAL_PER_SAMPLE | Per-sample OPAL evaluation | ✅ Production | Biocontainer |
| COMPARATIVE_ANALYSIS | Classifier comparison per sample | ⚠️ Stub | Wave (scipy stack) |

### nf-core Modules

| Module | Purpose | Version |
|--------|---------|---------|
| MULTIQC | Aggregate reports | Latest from nf-core |

---

## TAXPASTA_STANDARDISE

### Overview

Converts raw profiler outputs to standardized taxpasta TSV format. Automatically triggered for non-.tsv/.txt file extensions.

**Location**: `modules/local/taxpasta_standardise/`

**Status**: ✅ Production-ready

**Container**: `biocontainers/taxpasta:0.7.0--pyhdfd78af_0`

### Inputs

```groovy
input:
tuple val(meta), path(profiler_output)
```

**Meta map structure**:
```groovy
meta = [
    id: 'sample1_kraken2',      // Process identifier
    classifier: 'kraken2',       // Profiler tool (required)
    taxonomy_db: 'NCBI'          // Optional (inherited)
]
```

**Input file**: Raw profiler output (any supported format)

### Outputs

```groovy
output:
tuple val(meta), path("*.tsv"), emit: standardised
path "versions.yml"           , emit: versions
```

**Output file**: `{meta.id}.tsv` - Standardized taxpasta format with columns:
- `taxonomy_id`: NCBI taxonomy ID
- `count`: Read count assigned to this taxon

### Implementation Details

**Supported Profilers**:
- bracken
- centrifuge
- diamond
- ganon
- kaiju
- kmcp
- kraken2
- krakenuniq
- megan6
- metaphlan
- motus

**Validation**:
- Classifier parameter validated against supported list
- Input file existence and size checked
- Output file creation verified

**Error Handling**:
- Clear error messages for unsupported classifiers
- Troubleshooting hints for common issues
- taxpasta log captured for debugging

**Script**:
```bash
# Validate classifier
SUPPORTED_PROFILERS="bracken centrifuge diamond ganon kaiju kmcp kraken2 krakenuniq megan6 metaphlan motus"
if ! echo "$SUPPORTED_PROFILERS" | grep -qw "${meta.classifier}"; then
    echo "ERROR: Classifier '${meta.classifier}' is not supported"
    exit 1
fi

# Run taxpasta with error handling
if ! taxpasta standardise \
    --profiler ${meta.classifier} \
    --output ${prefix}.tsv \
    $profiler_output; then
    echo "ERROR: taxpasta standardisation failed"
    exit 1
fi

# Verify output
if [ ! -s ${prefix}.tsv ]; then
    echo "ERROR: Output file was not created or is empty"
    exit 1
fi
```

### When It Runs

Automatically triggered for files with these extensions:
- `.kreport`, `.kreport2` (Kraken2, Bracken)
- `.profile`, `.mpa`, `.mpa3` (MetaPhlAn)
- `.report` (Centrifuge)
- `.kaiju`, `.out` (Kaiju, ganon, kmcp, mOTUs)
- `.bracken` (Bracken)
- `.diamond` (DIAMOND)
- `.megan`, `.rma6` (MEGAN6/MALT)
- `.krakenuniq` (KrakenUniq)

**Skip** for:
- `.tsv`, `.txt` (already standardized)

### Example Usage

```groovy
// In workflow
TAXPASTA_STANDARDISE(ch_branched.needs_standardisation)

// Input example
[[id:'sample1_kraken2', classifier:'kraken2'], 'sample1.kreport']

// Output example
[[id:'sample1_kraken2', classifier:'kraken2'], 'sample1_kraken2.tsv']
```

### Configuration

In `conf/modules.config`:
```groovy
withName: 'TAXPASTA_STANDARDISE' {
    ext.args = ''  // Additional taxpasta arguments
    publishDir = [
        path: { "${params.outdir}/taxpasta_standardise" },
        mode: params.publish_dir_mode,
        enabled: params.save_standardised_profiles,
        saveAs: { filename -> filename.equals('versions.yml') ? null : filename }
    ]
}
```

### Testing

**Location**: `modules/local/taxpasta_standardise/tests/main.nf.test`

**Test cases**:
- Kraken2 standardization
- MetaPhlAn standardization
- Stub run

**Test data**: `assets/test_data/`

---

## TAXPASTA_TO_BIOBOXES

### Overview

Converts taxpasta TSV format to CAMI profiling Bioboxes format required by OPAL.

**Location**: `modules/local/taxpasta_to_bioboxes/`

**Status**: ✅ Production-ready

**Container**: Seqera Wave (pandas + ete3)
- Wave URL: `community.wave.seqera.io/library/pip_ete3_pandas:3d986008f4614a7f`
- Fallback: Conda environment

### Inputs

```groovy
input:
tuple val(meta), path(taxpasta_tsv)
```

**Meta map structure**:
```groovy
meta = [
    id: 'sample1_kraken2',           // Process identifier
    sample_id: 'sample1',             // Biological sample (for grouping)
    ranks: 'superkingdom|phylum|...',// Taxonomy ranks (optional)
    taxonomy_db: 'NCBI'               // Taxonomy database (default: NCBI)
]
```

**Input file**: Taxpasta TSV with columns:
- `taxonomy_id`: NCBI taxonomy ID
- `count`: Read count

### Outputs

```groovy
output:
tuple val(meta), path("*.bioboxes"), emit: bioboxes
path "versions.yml"                , emit: versions
```

**Output file**: `{meta.id}.bioboxes` - CAMI Bioboxes format with:
- Headers: `@SampleID`, `@Version`, `@Ranks`, `@TaxonomyID`
- Columns: `TAXID`, `RANK`, `TAXPATH`, `TAXPATHSN`, `PERCENTAGE`

### Implementation Details

**Python script**: `bin/taxpasta_to_bioboxes.py`

**Key features**:
1. **Taxonomy lookup**: Uses ete3 to get full lineage paths
2. **Percentage calculation**: Converts counts to percentages
3. **Lineage paths**: Generates TAXPATH (IDs) and TAXPATHSN (names)
4. **CAMI format**: Proper Bioboxes headers and formatting

**Validation**:
- Taxonomy database validated (NCBI, GTDB)
- Input file existence and size checked
- Output file creation verified
- Graceful fallback if ete3 unavailable (uses placeholder paths)

**Error Handling**:
- Explicit validation before conversion
- Clear error messages for failures
- Output verification after completion

**Script**:
```bash
# Validate taxonomy database
VALID_DBS="NCBI GTDB"
if ! echo "$VALID_DBS" | grep -qw "${taxonomy_db}"; then
    echo "ERROR: Unsupported taxonomy_db: ${taxonomy_db}"
    exit 1
fi

# Validate input file
if [ ! -s ${taxpasta_tsv} ]; then
    echo "ERROR: Input file does not exist or is empty"
    exit 1
fi

# Run conversion with error handling
if ! taxpasta_to_bioboxes.py \
    -i ${taxpasta_tsv} \
    -o ${prefix}.bioboxes \
    -s ${sample_id} \
    -r "${ranks}" \
    -d ${taxonomy_db} \
    --version-bioboxes ${version_bioboxes}; then
    echo "ERROR: Conversion failed"
    exit 1
fi

# Verify output
if [ ! -s ${prefix}.bioboxes ]; then
    echo "ERROR: Output file was not created or is empty"
    exit 1
fi
```

### Example Transformation

**Input (taxpasta TSV)**:
```
taxonomy_id,count
562,1000
2,500
```

**Output (CAMI Bioboxes)**:
```
@SampleID:sample1_kraken2
@Version:0.9.1
@Ranks:superkingdom|phylum|class|order|family|genus|species
@TaxonomyID:NCBI
@@TAXID	RANK	TAXPATH	TAXPATHSN	PERCENTAGE
562	species	131567|2|1224|1236|543|561|562	cellular organisms|Bacteria|Proteobacteria|Gammaproteobacteria|Enterobacteriales|Enterobacteriaceae|Escherichia coli	0.666667
2	superkingdom	131567|2	cellular organisms|Bacteria	0.333333
```

### Configuration

In `conf/modules.config`:
```groovy
withName: 'TAXPASTA_TO_BIOBOXES' {
    ext.args = ''
    publishDir = [
        path: { "${params.outdir}/taxpasta_to_bioboxes" },
        mode: params.publish_dir_mode,
        saveAs: { filename -> filename.equals('versions.yml') ? null : filename }
    ]
}
```

### Testing

**Location**: `modules/local/taxpasta_to_bioboxes/tests/main.nf.test`

**Test cases**:
- NCBI taxonomy database
- GTDB taxonomy database (if supported)
- Stub run

---

## OPAL_PER_SAMPLE

### Overview

Runs CAMI OPAL evaluation for a single biological sample with all its classifiers. Uses innovative tuple-embedded channel pattern for per-sample evaluation.

**Location**: `modules/local/opal_per_sample/`

**Status**: ✅ Production-ready (with known OPAL 1.0.13 limitations)

**Container**: `quay.io/biocontainers/cami-opal:1.0.13--pyhdfd78af_0`

### Inputs

```groovy
input:
tuple val(meta), path(gold_standard), path(predictions)
```

**Critical design**: Predictions embedded in tuple (not separate channel)

**Meta map structure**:
```groovy
meta = [
    id: 'sample1',                         // Sample identifier
    sample_id: 'sample1',                   // Biological sample
    labels: 'sample1_kraken2,sample1_metaphlan',  // Comma-separated labels
    num_classifiers: 2                      // Number of predictions
]
```

**Inputs**:
- `gold_standard`: CAMI Bioboxes gold standard file
- `predictions`: List of prediction bioboxes files for this sample

### Outputs

```groovy
output:
tuple val(meta), path("*", type: 'dir'), emit: results
path "versions.yml"                     , emit: versions
```

**Output directory**: `{meta.id}/` containing:
- `results.html` - Interactive HTML report
- `results.tsv` - Metrics table
- `confusion.tsv` - Confusion matrix
- `by_rank/` - Per-rank breakdowns
- Various plots and visualizations

### Implementation Details

**OPAL Metrics**:
- **Precision**: Fraction of predicted taxa that are correct
- **Recall**: Fraction of true taxa that are predicted
- **F1 Score**: Harmonic mean of precision and recall
- **UniFrac Distance**: Phylogenetic distance metric
- **L1 Norm**: Abundance difference
- **Jaccard Index**: Set similarity
- **Shannon Diversity**: Diversity metric
- **Bray-Curtis**: Abundance-based dissimilarity

**Validation**:
- Prediction count validated (warn if <2)
- Gold standard file existence checked
- Output directory explicitly created
- OPAL output verification after execution

**Error Handling**:
- Comprehensive error messages with context
- Common issues documented in error output
- OPAL log captured for debugging
- Known OPAL 1.0.13 bugs documented

**Known Limitations**:
- OPAL 1.0.13 has spider plot bug with minimal datasets (<100 taxa)
- Workaround: Use realistic datasets for production
- Test profile may fail (expected and documented)

**Script**:
```bash
# Validate prediction count
NUM_PREDICTIONS=${num_predictions}
if [ $NUM_PREDICTIONS -lt 1 ]; then
    echo "ERROR: No prediction files provided"
    exit 1
fi
if [ $NUM_PREDICTIONS -eq 1 ]; then
    echo "WARNING: Only 1 prediction. Comparison requires at least 2"
fi

# Validate gold standard
if [ ! -s ${gold_standard} ]; then
    echo "ERROR: Gold standard file does not exist or is empty"
    exit 1
fi

# Create output directory explicitly
mkdir -p ${prefix}

# Run OPAL with error handling
if ! opal.py \
    -g ${gold_standard} \
    -o ${prefix} \
    ${label_arg} \
    ${predictions}; then
    echo "ERROR: OPAL evaluation failed"
    echo "Common issues:"
    echo "  1. Incompatible formats"
    echo "  2. Missing taxonomy ranks"
    echo "  3. OPAL 1.0.13 bug with minimal datasets"
    exit 1
fi

# Verify OPAL created expected outputs
if [ ! -d ${prefix} ] || [ ! -s ${prefix}/results.tsv ]; then
    echo "ERROR: OPAL did not create expected outputs"
    exit 1
fi
```

### Tuple-Embedded Pattern

**Why**: Solves Nextflow cardinality matching problem.

**Problem**: Separate prediction channel sends ALL files to EVERY invocation:
```groovy
# This would be wrong:
input:
tuple val(meta), path(gold_standard)
path(predictions)  // ALL predictions to EVERY process
```

**Solution**: Embed predictions in tuple:
```groovy
# Correct:
input:
tuple val(meta), path(gold_standard), path(predictions)  // Bundled
```

This allows `groupTuple()` to create sample-specific tuples with only relevant files.

### Configuration

In `conf/modules.config`:
```groovy
withName: 'OPAL_PER_SAMPLE' {
    ext.args = ''
    publishDir = [
        path: { "${params.outdir}/opal/${meta.id}" },
        mode: params.publish_dir_mode,
        saveAs: { filename ->
            filename.equals('versions.yml') ? null : filename
        }
    ]
}
```

### Testing

**Location**: `modules/local/opal_per_sample/tests/main.nf.test`

**Test cases**:
- Stub run (passes)
- Functional tests with minimal data (may fail due to OPAL bugs - expected)
- Use `test_realistic` profile for functional validation

**Known**: Functional tests expected to fail with minimal test data due to OPAL 1.0.13 limitations.

---

## COMPARATIVE_ANALYSIS

### Overview

Performs statistical and visual comparison of classifiers within a biological sample.

**Location**: `modules/local/comparative_analysis/`

**Status**: ⚠️ Infrastructure complete, statistical features planned

**Container**: Seqera Wave (scipy stack)
- Dependencies: pandas, scikit-learn, plotly, scipy, statsmodels, numpy, kaleido

### Inputs

```groovy
input:
tuple val(meta), path(opal_dir)
path gold_standard
```

**Meta map structure**:
```groovy
meta = [
    id: 'sample1',
    sample_id: 'sample1',
    labels: 'sample1_kraken2,sample1_metaphlan',
    num_classifiers: 2
]
```

**Inputs**:
- `opal_dir`: OPAL results directory for this sample
- `gold_standard`: Gold standard bioboxes for differential analysis

### Outputs

```groovy
output:
tuple val(meta), path("*_pca.html")       , emit: pca          , optional: true
tuple val(meta), path("*_diff_taxa.tsv")  , emit: diff_taxa    , optional: true
tuple val(meta), path("*_comparison.html"), emit: comparison   , optional: true
path "versions.yml"                       , emit: versions
```

**Output files**:
- `{sample_id}_pca.html` - PCA plot of classifiers
- `{sample_id}_diff_taxa.tsv` - Taxa significantly different from gold standard
- `{sample_id}_comparison.html` - Comprehensive comparison report

### Implementation Details

**Current Status**: Stub implementation

**Python script**: `bin/comparative_analysis.py` (infrastructure complete)

**Planned Features**:
1. **PCA Analysis**: Plot classifiers in PC space based on performance metrics
2. **Statistical Testing**: Chi-square or similar tests for differential abundance
3. **Interactive Visualizations**: Plotly-based HTML reports
4. **Jaccard Similarity**: Heatmap of classifier agreement
5. **Top Misclassifications**: Identify commonly misclassified taxa

**Dependencies Available**:
- pandas: Data manipulation
- scikit-learn: PCA and machine learning
- plotly: Interactive visualizations
- scipy: Statistical tests
- statsmodels: Advanced statistical modeling
- numpy: Numerical operations
- kaleido: Static image export

### Stub Implementation

**Current**:
```bash
touch ${prefix}_pca.html
touch ${prefix}_diff_taxa.tsv
touch ${prefix}_comparison.html
```

**Purpose**: Validates process structure and output channels for testing.

### Roadmap

**High Priority**:
1. PCA visualization from OPAL metrics
2. Basic comparison tables
3. HTML report generation

**Medium Priority**:
4. Statistical testing for differential abundance
5. Jaccard similarity heatmaps
6. Interactive plots

**Low Priority**:
7. Advanced visualizations
8. Custom metric calculations
9. Export options

### Configuration

In `conf/modules.config`:
```groovy
withName: 'COMPARATIVE_ANALYSIS' {
    ext.args = ''
    publishDir = [
        path: { "${params.outdir}/comparative_analysis/${meta.id}" },
        mode: params.publish_dir_mode,
        saveAs: { filename -> filename.equals('versions.yml') ? null : filename }
    ]
}
```

### Testing

**Location**: `modules/local/comparative_analysis/tests/main.nf.test`

**Test cases**:
- Stub run (passes)

**Note**: Functional tests require implementation of analysis features.

---

## MULTIQC

### Overview

Aggregates results from all modules into a single HTML report.

**Location**: `modules/nf-core/multiqc/`

**Status**: ✅ nf-core module (standard)

**Container**: Biocontainer from nf-core

### Inputs

Collects outputs from:
- TAXPASTA_STANDARDISE (if saved)
- TAXPASTA_TO_BIOBOXES
- OPAL_PER_SAMPLE
- Software versions
- Workflow summary

### Outputs

```groovy
output:
path "*multiqc_report.html", emit: report
path "*_data"              , emit: data
path "*_plots"             , emit: plots, optional: true
path "versions.yml"        , emit: versions
```

### Configuration

**Location**: `assets/multiqc_config.yml`

**Custom sections**:
- Software versions
- Workflow summary
- OPAL metrics (if parseable)

---

## Module Development Guidelines

### Creating a New Module

**1. Use nf-core tools**:
```bash
nf-core modules create MODULE_NAME
```

**2. Follow template structure**:
```groovy
process MODULE_NAME {
    tag "$meta.id"
    label 'process_low'  // or medium/high

    conda "${moduleDir}/environment.yml"
    container "biocontainers/tool:version"

    input:
    tuple val(meta), path(input_file)

    output:
    tuple val(meta), path("*.out"), emit: results
    path "versions.yml"           , emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    tool $args --input $input_file --output ${prefix}.out

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        tool: \$(tool --version)
    END_VERSIONS
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    touch ${prefix}.out
    echo "tool: 1.0" > versions.yml
    """
}
```

### Best Practices

**1. Meta Map Pattern**:
- Always use `tuple val(meta), path(file)` for inputs
- Propagate meta to outputs
- Use `meta.id` for unique identifiers

**2. Version Tracking**:
- Always emit `versions.yml`
- Include all relevant tool versions
- Use robust version extraction

**3. Error Handling**:
- Validate inputs before processing
- Provide clear error messages
- Check output creation
- Capture logs for debugging

**4. Stub Runs**:
- Always implement stub section
- Create realistic output structure
- Enable fast CI/CD testing

**5. Configuration**:
- Support `task.ext.args` for flexibility
- Support `task.ext.prefix` for custom naming
- Support `task.ext.when` for conditional execution

**6. Testing**:
- Write comprehensive nf-test tests
- Test normal cases, edge cases, failures
- Use snapshot testing
- Provide test data

### See Also

- [Architecture](architecture.md) - Pipeline flow and design
- [Workflow Patterns](workflow-patterns.md) - Channel operations
- [Development Guide](development-guide.md) - Contributing guide
- [Testing](testing.md) - Test framework details
