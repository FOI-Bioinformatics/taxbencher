# Pipeline Architecture

This document describes the technical architecture of the taxbencher pipeline, including data flow, module interactions, and design decisions.

## Table of Contents
- [Pipeline Flow](#pipeline-flow)
- [Sample-Level Architecture](#sample-level-architecture)
- [Directory Structure](#directory-structure)
- [Key Concepts](#key-concepts)
- [Module Interactions](#module-interactions)
- [Design Decisions](#design-decisions)

## Pipeline Flow

### Overview

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

### Detailed Flow

#### Stage 1: Input and Format Detection

**Input Channel Creation** (`main.nf`):
```groovy
Channel
    .fromList(samplesheet)
    .map { meta ->
        [meta, file(meta.taxpasta_file, checkIfExists: true)]
    }
    .set { ch_input }
```

**Format Detection** (`workflows/taxbencher.nf:39-46`):
```groovy
ch_input
    .branch { meta, file ->
        standardised: file.name.endsWith('.tsv') || file.name.endsWith('.txt')
            return [meta, file]
        needs_standardisation: true
            return [meta, file]
    }
    .set { ch_branched }
```

This automatic branching enables the pipeline to accept both:
- **Pre-standardized**: `.tsv`, `.txt` files (taxpasta output)
- **Raw profiler output**: `.kreport`, `.profile`, `.out`, etc.

#### Stage 2: Standardization (Conditional)

**TAXPASTA_STANDARDISE** runs only for raw profiler outputs:

**Input**: Raw profiler output (e.g., `.kreport`, `.profile`)
**Output**: Standardized taxpasta TSV format
**When**: Automatically triggered for non-.tsv/.txt files

Supported profilers:
- Kraken2, Bracken (`.kreport`)
- MetaPhlAn (`.profile`, `.mpa`)
- Centrifuge (`.report`)
- Kaiju, ganon, KMCP, mOTUs (`.out`)
- DIAMOND, MEGAN6/MALT, KrakenUniq

#### Stage 3: Format Conversion

**TAXPASTA_TO_BIOBOXES** converts all taxpasta TSV files to CAMI Bioboxes format:

**Input**: Taxpasta TSV (standardized format)
**Output**: CAMI Bioboxes profiling format
**Process**:
1. Read taxpasta TSV (taxonomy_id, count columns)
2. Use ete3 to lookup full taxonomy lineages
3. Calculate percentages from counts
4. Generate CAMI Bioboxes format with headers and lineage paths

**Example transformation**:
```
# Taxpasta TSV
taxonomy_id,count
562,1000
```
↓
```
# CAMI Bioboxes
@SampleID:sample1_kraken2
@Version:0.9.1
@Ranks:superkingdom|phylum|class|order|family|genus|species
@TaxonomyID:NCBI
@@TAXID	RANK	TAXPATH	TAXPATHSN	PERCENTAGE
562	species	131567|2|1224|...|562	Biota|Bacteria|...|Escherichia coli	0.50
```

#### Stage 4: Per-Sample Grouping

**The Innovation: Grouping by `sample_id`**

```groovy
ch_bioboxes_per_sample = TAXPASTA_TO_BIOBOXES.out.bioboxes
    .map { meta, bioboxes ->
        [meta.sample_id, meta.label, bioboxes]
    }
    .groupTuple()  // Groups by first element (sample_id)
    .combine(ch_gold_standard)
    .map { sample_id, labels, bioboxes_files, gold_std ->
        def meta_grouped = [
            id: sample_id,
            sample_id: sample_id,
            labels: labels.join(','),
            num_classifiers: labels.size()
        ]
        tuple(meta_grouped, gold_std, bioboxes_files)
    }
```

**What happens**:
1. Extract `sample_id` as grouping key
2. `groupTuple()` collects all bioboxes with same `sample_id`
3. Create new meta with aggregated information
4. Combine with gold standard
5. Embed files in tuple (critical for Nextflow cardinality)

**Example**:
```
Input bioboxes:
[{sample_id:'s1', label:'s1_kraken2'}, bioboxes1]
[{sample_id:'s1', label:'s1_metaphlan'}, bioboxes2]
[{sample_id:'s2', label:'s2_kraken2'}, bioboxes3]

After groupTuple():
['s1', ['s1_kraken2','s1_metaphlan'], [bioboxes1, bioboxes2]]
['s2', ['s2_kraken2'], [bioboxes3]]

After map (final):
[{id:'s1', sample_id:'s1', labels:'s1_kraken2,s1_metaphlan', num_classifiers:2}, gold_std, [bioboxes1, bioboxes2]]
[{id:'s2', sample_id:'s2', labels:'s2_kraken2', num_classifiers:1}, gold_std, [bioboxes3]]
```

#### Stage 5: OPAL Evaluation

**OPAL_PER_SAMPLE** evaluates all classifiers for one biological sample:

**Input**: Tuple with meta, gold standard, and list of prediction files
**Output**: Directory with OPAL results (HTML reports, metrics TSV, confusion matrices)

**Process**:
1. Validate inputs (gold standard exists, predictions >0)
2. Create output directory
3. Run OPAL with all predictions for this sample
4. Generate comprehensive metrics and visualizations

**Metrics produced**:
- Precision, Recall, F1 score (per rank)
- UniFrac distance
- L1 norm
- Jaccard index
- Shannon diversity
- Bray-Curtis dissimilarity

#### Stage 6: Comparative Analysis

**COMPARATIVE_ANALYSIS** compares classifiers within each sample:

**Status**: Infrastructure complete, statistical features planned
**Input**: OPAL results directory + gold standard
**Output**: PCA plots, differential taxa, comparison reports

**Planned features**:
- PCA visualization of classifier performance
- Statistical testing for differential abundance
- Interactive HTML reports
- Jaccard similarity heatmaps
- Top misclassifications

#### Stage 7: Aggregation

**MULTIQC** aggregates all reports:
- Collects OPAL metrics across samples
- Generates unified HTML report
- Provides overview of all evaluations

## Sample-Level Architecture

### Core Concept: Per-Sample Comparative Analysis

**Problem**: Traditional benchmarking evaluates each classifier independently.

**Solution**: Group profiles by biological sample for fair comparison.

**Key Terminology**:

- **`sample_id`**: Biological sample identifier (grouping key)
  - Profiles with the same `sample_id` are evaluated together
  - Enables fair comparison (same input data, different tools)
  - Example: `sample1` → groups kraken2, metaphlan, centrifuge

- **`label`**: Unique identifier for each taxonomic profile
  - Format: `{sample_id}_{classifier}`
  - Used in OPAL reports and output files
  - Must be unique across entire samplesheet
  - Example: `sample1_kraken2`, `sample1_metaphlan`

### Example Samplesheet

```csv
sample_id,label,classifier,taxpasta_file,taxonomy_db
sample1,sample1_kraken2,kraken2,/path/to/sample1_kraken2.tsv,NCBI
sample1,sample1_metaphlan,metaphlan,/path/to/sample1_metaphlan.tsv,NCBI
sample1,sample1_centrifuge,centrifuge,/path/to/sample1_centrifuge.tsv,NCBI
sample2,sample2_kraken2,kraken2,/path/to/sample2_kraken2.tsv,NCBI
sample2,sample2_metaphlan,metaphlan,/path/to/sample2_metaphlan.tsv,NCBI
```

**Result**:
- **Sample1**: 1 OPAL run comparing 3 classifiers
  - Output: `results/opal/sample1/` with comparative metrics
  - Comparative analysis: `results/comparative_analysis/sample1/`
- **Sample2**: 1 OPAL run comparing 2 classifiers
  - Output: `results/opal/sample2/` with comparative metrics
  - Comparative analysis: `results/comparative_analysis/sample2/`

### Why Per-Sample Evaluation?

**Benefits**:
1. **Fair Comparison**: Same input → different classifiers → direct comparison
2. **Sample-Specific Insights**: Identify which classifiers work best for specific sample types
3. **Bias Detection**: Reveal classifier-specific biases per sample
4. **Statistical Power**: Enable meaningful PCA and statistical testing
5. **Practical Relevance**: Answers "Which classifier for MY data?"

## Directory Structure

```
taxbencher/
├── workflows/
│   └── taxbencher.nf                    # Main workflow logic
│
├── modules/
│   ├── local/                           # Custom modules
│   │   ├── taxpasta_standardise/        # Raw → taxpasta TSV
│   │   │   ├── main.nf
│   │   │   ├── meta.yml
│   │   │   ├── environment.yml
│   │   │   └── tests/
│   │   │       ├── main.nf.test
│   │   │       └── main.nf.test.snap
│   │   ├── taxpasta_to_bioboxes/        # Taxpasta TSV → Bioboxes
│   │   │   ├── main.nf
│   │   │   ├── meta.yml
│   │   │   ├── environment.yml
│   │   │   └── tests/
│   │   ├── opal_per_sample/             # Per-sample OPAL evaluation
│   │   │   ├── main.nf
│   │   │   ├── meta.yml
│   │   │   ├── environment.yml          # (shared with opal)
│   │   │   └── tests/
│   │   └── comparative_analysis/        # Classifier comparison
│   │       ├── main.nf
│   │       ├── meta.yml
│   │       ├── environment.yml
│   │       └── tests/
│   └── nf-core/                         # nf-core modules
│       └── multiqc/                     # Report aggregation
│
├── subworkflows/
│   ├── local/                           # Local subworkflows
│   │   └── utils_nfcore_taxbencher_pipeline/
│   └── nf-core/                         # nf-core utils
│       ├── utils_nextflow_pipeline/
│       ├── utils_nfcore_pipeline/
│       └── utils_nfschema_plugin/
│
├── bin/                                 # Executable scripts
│   ├── taxpasta_to_bioboxes.py          # CAMI format conversion
│   ├── comparative_analysis.py          # Classifier comparison (stub)
│   ├── validate_taxpasta.py             # Taxpasta validation
│   ├── validate_bioboxes.py             # Bioboxes validation
│   └── fix_gold_standard.py             # Gold standard auto-fixer
│
├── lib/                                 # Groovy libraries
│   ├── WorkflowMain.groovy
│   └── NfcoreSchema.groovy
│
├── conf/                                # Configuration files
│   ├── base.config                      # Resource allocations
│   ├── modules.config                   # Module-specific configs
│   ├── test.config                      # Test profile config
│   └── test_full.config                 # Full test config
│
├── assets/                              # Pipeline assets
│   ├── test_data/                       # Test datasets
│   │   ├── gold_standard.bioboxes
│   │   ├── gold_standard_realistic.bioboxes
│   │   └── samplesheet_*.csv
│   ├── schema_input.json                # Samplesheet schema
│   ├── samplesheet.csv                  # Example samplesheet
│   └── multiqc_config.yml               # MultiQC config
│
├── docs/                                # Documentation
│   ├── development/                     # Developer docs
│   ├── reports/                         # Quality reports
│   ├── usage.md                         # Usage guide
│   ├── output.md                        # Output documentation
│   └── troubleshooting.md               # Troubleshooting
│
├── tests/                               # Pipeline-level tests
│   ├── default.nf.test                  # Default test
│   └── nextflow.config                  # Test config
│
├── main.nf                              # Pipeline entry point
├── nextflow.config                      # Main configuration
├── nextflow_schema.json                 # Parameter schema
└── CLAUDE.md                            # Developer quick start
```

### Key Directories

**`workflows/`**: Main workflow logic
- `taxbencher.nf`: Orchestrates all modules and data flow

**`modules/local/`**: Custom Nextflow modules
- Each module is self-contained with tests and metadata

**`bin/`**: Python scripts called by modules
- Must be executable (`chmod +x`)
- Available on PATH during process execution

**`conf/`**: Configuration files
- `base.config`: Resource labels (process_low, process_medium, etc.)
- `modules.config`: Per-module configuration (publishDir, args, etc.)
- `test.config`: Test profile settings

**`assets/`**: Static files
- Test data committed to repository
- Schema for validation
- Example files for users

## Key Concepts

### 1. Meta Map Pattern

Every process uses a meta map for sample tracking:

```groovy
def meta = [
    id: 'sample1_kraken2',           // Unique process identifier
    sample_id: 'sample1',             // Biological sample (grouping key)
    label: 'sample1_kraken2',         // Display label
    classifier: 'kraken2',            // Classifier tool
    taxonomy_db: 'NCBI'               // Taxonomy database
]

// In process:
input:
tuple val(meta), path(input_file)

// Meta propagation:
output:
tuple val(meta), path("*.output"), emit: results
```

**Benefits**:
- Tracks sample information through pipeline
- Enables dynamic file naming
- Allows grouping and filtering
- Preserves provenance

### 2. Automatic Format Detection

Files are routed based on extension without user configuration:

```groovy
ch_input.branch { meta, file ->
    standardised: file.name.endsWith('.tsv') || file.name.endsWith('.txt')
    needs_standardisation: true
}
```

**Supported extensions**:
- **Standardised**: `.tsv`, `.txt`
- **Kraken2/Bracken**: `.kreport`, `.kreport2`, `.bracken`
- **MetaPhlAn**: `.profile`, `.mpa`, `.mpa3`
- **Centrifuge**: `.report`
- **Kaiju**: `.kaiju`, `.out`
- **Others**: `.ganon`, `.kmcp`, `.motus`, `.diamond`, `.megan`, `.krakenuniq`

### 3. Tuple-Embedded Channel Pattern

**Problem**: Nextflow cardinality matching sends ALL files to each invocation.

**Solution**: Embed files in tuple with metadata:

```groovy
// Traditional (problematic):
input:
tuple val(meta), path(gold_standard)
path(predictions)  // ALL predictions sent to EVERY invocation

// Tuple-embedded (solution):
input:
tuple val(meta), path(gold_standard), path(predictions)  // Bundled together
```

**How it works**:
```groovy
// Group by sample_id
.groupTuple()  // [sample_id, [labels...], [files...]]

// Combine with gold standard
.combine(ch_gold_standard)  // [sample_id, [labels...], [files...], gold_std]

// Create tuple with embedded files
.map { sample_id, labels, files, gold_std ->
    def meta = [id: sample_id, ...]
    tuple(meta, gold_std, files)  // Files embedded in tuple!
}
```

**Result**: Each OPAL invocation receives only ITS files.

### 4. Version Tracking Optimization

Version files are identical across parallel invocations:

```groovy
ch_versions = ch_versions.mix(MODULE.out.versions.first())
```

`.first()` takes only one copy, avoiding redundant collection.

## Module Interactions

### Data Flow Diagram

```
Samplesheet → CH_INPUT
                  ↓
          ┌───────┴────────┐
          ↓                ↓
    [Standardised]   [Needs Standardisation]
          ↓                ↓
          │          TAXPASTA_STANDARDISE
          │                ↓
          └────────┬───────┘
                   ↓
         TAXPASTA_TO_BIOBOXES
                   ↓
              CH_BIOBOXES
                   ↓
          .map { extract sample_id }
                   ↓
             .groupTuple()
                   ↓
          [sample_id, [labels], [files]]
                   ↓
        .combine(CH_GOLD_STANDARD)
                   ↓
    [sample_id, [labels], [files], gold_std]
                   ↓
          .map { create meta_grouped, embed files }
                   ↓
      [meta_grouped, gold_std, [files]]
                   ↓
           OPAL_PER_SAMPLE
                   ↓
          CH_OPAL_RESULTS
                   ↓
        COMPARATIVE_ANALYSIS
                   ↓
             MULTIQC
```

### Channel Cardinality

**Key principle**: Maintain 1:1 correspondence between meta and files.

**Branching** (1 → many):
```groovy
ch_input.branch { ... }
// Creates multiple output channels from one input
```

**Mixing** (many → 1):
```groovy
ch_standardised.mix(TAXPASTA_STANDARDISE.out.standardised)
// Combines channels into one
```

**Grouping** (many → fewer):
```groovy
.groupTuple()
// Collects items with same key
```

**Combining** (cross product):
```groovy
.combine(ch_gold_standard)
// Creates all combinations
```

## Design Decisions

### Why Per-Sample Grouping?

**Decision**: Group classifiers by biological sample for evaluation.

**Rationale**:
1. **Scientific validity**: Same input enables fair comparison
2. **Practical relevance**: Users want to know "which classifier for MY sample"
3. **Statistical power**: Enables meaningful comparative analysis
4. **Resource efficiency**: One OPAL run per sample (not per classifier)

**Trade-offs**:
- **Pro**: Fair comparison, meaningful statistics, efficient
- **Con**: Requires consistent sample_id naming, complex channel logic

### Why Tuple-Embedded Pattern?

**Decision**: Embed prediction files in tuple with metadata.

**Rationale**:
1. **Nextflow limitation**: Separate channels cause cardinality issues
2. **Correctness**: Ensures each invocation gets correct files
3. **Simplicity**: Cleaner than complex filtering logic

**Alternative considered**: Filter predictions by sample_id in process
- **Rejected**: Fragile, error-prone, requires passing all files

### Why Automatic Format Detection?

**Decision**: Branch based on file extension automatically.

**Rationale**:
1. **User experience**: No configuration needed
2. **Flexibility**: Supports mixed samplesheets
3. **Efficiency**: Only standardizes when needed
4. **Maintainability**: Logic centralized in workflow

**Alternative considered**: User-specified format parameter
- **Rejected**: More configuration burden, error-prone

### Why Wave Containers?

**Decision**: Use Seqera Wave for Python scientific stack.

**Rationale**:
1. **Dependency complexity**: pandas + ete3 not in single biocontainer
2. **Reproducibility**: Wave builds deterministic containers
3. **Flexibility**: Easy to update dependencies
4. **Fallback**: Conda available when Wave unavailable

**Trade-offs**:
- **Pro**: Reproducible, flexible, no custom Dockerfiles
- **Con**: Requires internet, slower first run, Wave dependency

### Why Stub Tests?

**Decision**: Use stub tests for OPAL_PER_SAMPLE and COMPARATIVE_ANALYSIS.

**Rationale**:
1. **OPAL limitations**: Version 1.0.13 fails with minimal test data
2. **Test infrastructure**: Validates structure without running full OPAL
3. **CI/CD**: Fast tests for structure validation

**Trade-offs**:
- **Pro**: Fast, reliable, no OPAL bugs
- **Con**: Doesn't test actual functionality
- **Mitigation**: Use test_realistic profile for functional validation

## See Also

- [Modules](modules.md) - Detailed module specifications
- [Workflow Patterns](workflow-patterns.md) - Channel operations guide
- [Development Guide](development-guide.md) - Contributing instructions
- [Testing](testing.md) - Test framework details
