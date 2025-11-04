# Workflow Patterns and Channel Operations

This document provides a deep dive into the Nextflow patterns and channel operations used in taxbencher. For high-level architecture, see [Architecture](architecture.md).

## Table of Contents
- [Channel Operations Reference](#channel-operations-reference)
- [Pattern 1: Automatic Format Detection](#pattern-1-automatic-format-detection)
- [Pattern 2: Per-Sample Grouping](#pattern-2-per-sample-grouping)
- [Pattern 3: Tuple-Embedded Channels](#pattern-3-tuple-embedded-channels)
- [Pattern 4: Version Tracking Optimization](#pattern-4-version-tracking-optimization)
- [Pattern 5: Conditional Logging](#pattern-5-conditional-logging)
- [Channel Debugging Techniques](#channel-debugging-techniques)
- [Common Pitfalls and Solutions](#common-pitfalls-and-solutions)
- [Advanced Patterns](#advanced-patterns)

## Channel Operations Reference

### Basic Operations

#### `.branch { }`
Splits a channel into multiple output channels based on conditions.

```groovy
// Split channel based on file extension
ch_input
    .branch { meta, file ->
        tsv_files: file.name.endsWith('.tsv')
            return [meta, file]
        kreport_files: file.name.endsWith('.kreport')
            return [meta, file]
        other: true
            return [meta, file]
    }
    .set { ch_branched }

// Access branches:
ch_branched.tsv_files      // Only .tsv files
ch_branched.kreport_files  // Only .kreport files
ch_branched.other          // Everything else
```

**Key points**:
- Each branch needs a `return` statement
- Branches are mutually exclusive (first match wins)
- Use `true` for catch-all branch
- Set result to variable to access named branches

#### `.map { }`
Transforms each item in a channel.

```groovy
// Extract sample_id from meta
ch_input
    .map { meta, file ->
        [meta.sample_id, meta.label, file]
    }

// Add new meta field
ch_input
    .map { meta, file ->
        meta.new_field = 'value'
        [meta, file]
    }

// Create new meta
ch_input
    .map { meta, file ->
        def new_meta = [id: meta.sample_id, type: 'group']
        [new_meta, file]
    }
```

**Key points**:
- Returns transformed item
- Can change structure completely
- Use for reshaping tuples
- Careful with meta map mutation

#### `.groupTuple()`
Groups items by the first element (key).

```groovy
// Input: [sample_id, label, file]
ch_input
    .groupTuple()

// Output: [sample_id, [labels...], [files...]]
// Example: ['sample1', ['s1_kraken2', 's1_metaphlan'], [file1, file2]]
```

**Key points**:
- Groups by first tuple element
- Collects remaining elements into lists
- Emits when all items collected (end of channel)
- Use `.groupTuple(by: 1)` to group by different position

#### `.combine()`
Creates Cartesian product of two channels.

```groovy
// Combine each item with gold standard
ch_predictions
    .combine(ch_gold_standard)

// Input ch_predictions: [meta, prediction_file]
// Input ch_gold_standard: [gold_standard_file]
// Output: [meta, prediction_file, gold_standard_file]
```

**Key points**:
- Every item from ch1 paired with every item from ch2
- Use for adding reference files to all samples
- Can combine value channels (single item) efficiently

#### `.mix()`
Merges multiple channels into one.

```groovy
// Combine standardised and newly-standardised files
ch_standardised = ch_already_standardised
    .mix(TAXPASTA_STANDARDISE.out.standardised)
```

**Key points**:
- Order not guaranteed
- All channels must have same structure
- Use for merging parallel branches
- Does not wait for all channels to complete

#### `.first()`
Takes only the first emission from channel.

```groovy
// Take only one versions.yml (they're all identical)
ch_versions = ch_versions.mix(MODULE.out.versions.first())
```

**Key points**:
- Optimization for identical parallel outputs
- Prevents collecting redundant files
- Only takes first emission, ignores rest
- Use when all items are identical

#### `.subscribe { }`
Executes code for each item without consuming channel.

```groovy
// Log without consuming channel
ch_input
    .subscribe { meta, file ->
        log.info "[INFO] Processing ${meta.id}: ${file.name}"
    }
```

**Key points**:
- Side effect only (logging, validation)
- Does not transform channel
- Does not consume channel (items still flow)
- Use for debugging and logging

#### `.collect()`
Gathers all items into a single list.

```groovy
// Collect all files for MultiQC
ch_multiqc_files.collect()

// Output: [file1, file2, file3, ...]
```

**Key points**:
- Waits for entire channel to complete
- Emits single item (list)
- Use for processes requiring all inputs
- Can cause memory issues with large channels

### Advanced Operations

#### `.transpose()`
Flattens nested lists while preserving tuple structure.

```groovy
// Input: [meta, [file1, file2, file3]]
ch_input
    .transpose()

// Output:
// [meta, file1]
// [meta, file2]
// [meta, file3]
```

#### `.flatten()`
Completely flattens nested structures.

```groovy
// Input: [[meta1, file1], [meta2, file2]]
ch_input
    .flatten()

// Output: [meta1, file1, meta2, file2]
```

#### `.toList()`
Similar to `.collect()` but ensures single emission.

```groovy
// Ensure single list emission
MULTIQC.out.report.toList()
```

#### `.ifEmpty()`
Provides default value if channel is empty.

```groovy
ch_input
    .ifEmpty { log.warn "No input files found"; [] }
```

## Pattern 1: Automatic Format Detection

### Overview

The pipeline automatically detects input file format and routes to appropriate processing path without user configuration.

**Location**: `workflows/taxbencher.nf:39-74`

### Full Implementation

```groovy
//
// BRANCH: Separate inputs that need standardization from those that don't
// Check file extension to determine if taxpasta standardisation is needed
// .tsv or .txt files are already standardized, others need processing
//
ch_input
    .branch { meta, file ->
        standardised: file.name.endsWith('.tsv') || file.name.endsWith('.txt')
            return [meta, file]
        needs_standardisation: true
            return [meta, file]
    }
    .set { ch_branched }

//
// Log format detection for user visibility
//
ch_branched.standardised
    .subscribe { meta, file ->
        log.info "[TAXBENCHER] Sample ${meta.sample_id} | Label ${meta.label} | Classifier ${meta.classifier}: Using pre-standardised profile ${file.name}"
    }

ch_branched.needs_standardisation
    .subscribe { meta, file ->
        log.info "[TAXBENCHER] Sample ${meta.sample_id} | Label ${meta.label} | Classifier ${meta.classifier}: Standardising raw profiler output ${file.name}"
    }

//
// MODULE: Standardise raw profiler outputs (optional)
// Only runs for files that are not already in taxpasta TSV format
//
TAXPASTA_STANDARDISE(ch_branched.needs_standardisation)
ch_versions = ch_versions.mix(TAXPASTA_STANDARDISE.out.versions.first())

//
// CHANNEL: Combine standardised and already-standardised files
// This creates a unified channel of taxpasta TSV files for downstream processing
//
ch_taxpasta = ch_branched.standardised
    .mix(TAXPASTA_STANDARDISE.out.standardised)
```

### Step-by-Step Breakdown

**Step 1: Branch by extension**
```groovy
ch_input.branch { meta, file ->
    standardised: file.name.endsWith('.tsv') || file.name.endsWith('.txt')
    needs_standardisation: true
}
```

**Input**:
```
[{sample_id:'s1', label:'s1_kraken2', classifier:'kraken2'}, s1.tsv]
[{sample_id:'s1', label:'s1_metaphlan', classifier:'metaphlan'}, s1.profile]
[{sample_id:'s2', label:'s2_kraken2', classifier:'kraken2'}, s2.kreport]
```

**Output (two branches)**:
```
ch_branched.standardised:
  [{sample_id:'s1', label:'s1_kraken2'}, s1.tsv]

ch_branched.needs_standardisation:
  [{sample_id:'s1', label:'s1_metaphlan'}, s1.profile]
  [{sample_id:'s2', label:'s2_kraken2'}, s2.kreport]
```

**Step 2: Log decisions**
```groovy
ch_branched.standardised.subscribe { ... log.info ... }
ch_branched.needs_standardisation.subscribe { ... log.info ... }
```

Output to user:
```
[TAXBENCHER] Sample s1 | Label s1_kraken2 | Classifier kraken2: Using pre-standardised profile s1.tsv
[TAXBENCHER] Sample s1 | Label s1_metaphlan | Classifier metaphlan: Standardising raw profiler output s1.profile
[TAXBENCHER] Sample s2 | Label s2_kraken2 | Classifier kraken2: Standardising raw profiler output s2.kreport
```

**Step 3: Standardize if needed**
```groovy
TAXPASTA_STANDARDISE(ch_branched.needs_standardisation)
```

**Input**: `needs_standardisation` branch (s1.profile, s2.kreport)
**Output**: Standardized TSV files (s1_standardised.tsv, s2_standardised.tsv)

**Step 4: Merge branches**
```groovy
ch_taxpasta = ch_branched.standardised
    .mix(TAXPASTA_STANDARDISE.out.standardised)
```

**Result**: Unified channel with all files in taxpasta TSV format
```
[{sample_id:'s1', label:'s1_kraken2'}, s1.tsv]                    # From standardised branch
[{sample_id:'s1', label:'s1_metaphlan'}, s1_standardised.tsv]     # From TAXPASTA_STANDARDISE
[{sample_id:'s2', label:'s2_kraken2'}, s2_standardised.tsv]       # From TAXPASTA_STANDARDISE
```

### Benefits

1. **User convenience**: No configuration needed
2. **Flexibility**: Mixed samplesheets supported
3. **Efficiency**: Only standardizes when needed
4. **Transparency**: Logs inform user of decisions
5. **Maintainability**: Logic centralized in workflow

### Extension Points

To add support for new file types:

1. Update branch condition:
```groovy
standardised: file.name.endsWith('.tsv') ||
              file.name.endsWith('.txt') ||
              file.name.endsWith('.new_format')
```

2. Update `assets/schema_input.json` with new pattern
3. Add test case in `tests/`

## Pattern 2: Per-Sample Grouping

### Overview

Groups classifier outputs by biological sample for fair comparative evaluation.

**Location**: `workflows/taxbencher.nf:86-110`

### Full Implementation

```groovy
//
// Group bioboxes by sample_id for per-sample OPAL evaluation
// Each biological sample gets its own OPAL run with all its classifiers
//
// Step 1: Map to [sample_id, label, bioboxes]
// Step 2: Group by sample_id using groupTuple
// Step 3: Combine with gold standard
// Step 4: Create new meta with aggregated information
//
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
```

### Detailed Transformation Walkthrough

**Input**: TAXPASTA_TO_BIOBOXES output
```groovy
[{id:'s1_kraken2', sample_id:'s1', label:'s1_kraken2', classifier:'kraken2'}, s1_kraken2.bioboxes]
[{id:'s1_metaphlan', sample_id:'s1', label:'s1_metaphlan', classifier:'metaphlan'}, s1_metaphlan.bioboxes]
[{id:'s1_centrifuge', sample_id:'s1', label:'s1_centrifuge', classifier:'centrifuge'}, s1_centrifuge.bioboxes]
[{id:'s2_kraken2', sample_id:'s2', label:'s2_kraken2', classifier:'kraken2'}, s2_kraken2.bioboxes]
```

**After `.map { meta, bioboxes -> [meta.sample_id, meta.label, bioboxes] }`**:
```groovy
['s1', 's1_kraken2', s1_kraken2.bioboxes]
['s1', 's1_metaphlan', s1_metaphlan.bioboxes]
['s1', 's1_centrifuge', s1_centrifuge.bioboxes]
['s2', 's2_kraken2', s2_kraken2.bioboxes]
```

**Key insight**: Restructured to have `sample_id` as first element (grouping key).

**After `.groupTuple()`**:
```groovy
['s1', ['s1_kraken2', 's1_metaphlan', 's1_centrifuge'], [s1_kraken2.bioboxes, s1_metaphlan.bioboxes, s1_centrifuge.bioboxes]]
['s2', ['s2_kraken2'], [s2_kraken2.bioboxes]]
```

**Key insight**: `groupTuple()` groups by first element, collecting rest into lists.

**After `.combine(ch_gold_standard)`** (where `ch_gold_standard = [gold.bioboxes]`):
```groovy
['s1', ['s1_kraken2', 's1_metaphlan', 's1_centrifuge'], [s1_kraken2.bioboxes, s1_metaphlan.bioboxes, s1_centrifuge.bioboxes], gold.bioboxes]
['s2', ['s2_kraken2'], [s2_kraken2.bioboxes], gold.bioboxes]
```

**Key insight**: Gold standard added to every group.

**After final `.map { }`**:
```groovy
[
  {id:'s1', sample_id:'s1', labels:'s1_kraken2,s1_metaphlan,s1_centrifuge', num_classifiers:3},
  gold.bioboxes,
  [s1_kraken2.bioboxes, s1_metaphlan.bioboxes, s1_centrifuge.bioboxes]
]

[
  {id:'s2', sample_id:'s2', labels:'s2_kraken2', num_classifiers:1},
  gold.bioboxes,
  [s2_kraken2.bioboxes]
]
```

**Key insight**: Created new meta with aggregated info, embedded files in tuple.

### Why This Pattern Works

**Problem without grouping**:
- OPAL would run separately for each classifier
- No comparative analysis possible
- Inefficient (3 OPAL runs instead of 1)

**Solution with grouping**:
- One OPAL run per biological sample
- All classifiers compared fairly (same input)
- Enables statistical analysis
- Efficient resource usage

### OPAL_PER_SAMPLE Input Signature

```groovy
// Module expects:
input:
tuple val(meta), path(gold_standard), path(predictions)

// Our channel provides:
[meta_grouped, gold_std, [bioboxes_files]]

// Perfect match!
```

**Key detail**: Predictions embedded in tuple (not separate channel) to ensure correct cardinality.

## Pattern 3: Tuple-Embedded Channels

### Overview

Solves Nextflow cardinality matching problem by embedding files in tuple with metadata.

**Location**: `workflows/taxbencher.nf:100-110` and `modules/local/opal_per_sample/main.nf:16`

### The Problem

**Naive approach** (problematic):
```groovy
// OPAL module with separate inputs
process OPAL {
    input:
    tuple val(meta), path(gold_standard)
    path(predictions)  // Separate channel!

    // Problem: ALL predictions sent to EVERY invocation
}

// In workflow:
OPAL(
    ch_meta_and_gold,  // [meta, gold_std]
    ch_predictions     // [pred1, pred2, pred3, ...]
)
```

**What happens**:
```
Invocation 1 (sample1): Receives [meta1, gold], [pred1, pred2, pred3, pred_from_sample2]
Invocation 2 (sample2): Receives [meta2, gold], [pred1, pred2, pred3, pred_from_sample2]
```

Every OPAL run gets ALL predictions, not just its own!

### The Solution

**Tuple-embedded approach**:
```groovy
// OPAL_PER_SAMPLE module with embedded predictions
process OPAL_PER_SAMPLE {
    input:
    tuple val(meta), path(gold_standard), path(predictions)  // All in tuple!
}

// In workflow (from per-sample grouping):
ch_bioboxes_per_sample = ...
    .map { sample_id, labels, bioboxes_files, gold_std ->
        def meta_grouped = [id: sample_id, ...]
        tuple(meta_grouped, gold_std, bioboxes_files)  // Embed files in tuple
    }

OPAL_PER_SAMPLE(ch_bioboxes_per_sample)
```

**What happens**:
```
Invocation 1 (sample1): Receives [meta1, gold, [pred1_s1, pred2_s1, pred3_s1]]
Invocation 2 (sample2): Receives [meta2, gold, [pred1_s2]]
```

Each OPAL run gets ONLY its predictions!

### Why This Works

**Nextflow cardinality matching rules**:
1. **Tuple inputs**: Items matched 1:1 by position in tuple
2. **Separate inputs**: All items from second channel sent to every invocation

**Our solution**: Put everything in one tuple → perfect 1:1 matching.

### Code Comparison

**Before (doesn't work)**:
```groovy
// Workflow
ch_meta_and_gold = ch_bioboxes
    .map { meta, bio -> [meta, gold_std] }

OPAL(
    ch_meta_and_gold,
    ch_bioboxes.map { meta, bio -> bio }  // Separate channel!
)

// Result: Cardinality mismatch
```

**After (works perfectly)**:
```groovy
// Workflow
ch_grouped = ch_bioboxes
    .map { meta, bio -> [meta.sample_id, meta.label, bio] }
    .groupTuple()
    .combine(ch_gold_standard)
    .map { sample_id, labels, files, gold ->
        def meta = [id: sample_id, ...]
        tuple(meta, gold, files)  // All together!
    }

OPAL_PER_SAMPLE(ch_grouped)

// Result: Perfect match
```

### Module Implementation Detail

```groovy
// modules/local/opal_per_sample/main.nf
process OPAL_PER_SAMPLE {
    input:
    tuple val(meta), path(gold_standard), path(predictions)

    script:
    // Convert predictions to list if it's a single file
    def pred_files = predictions instanceof List ? predictions : [predictions]

    """
    opal.py \\
        -g ${gold_standard} \\
        -o ${prefix} \\
        ${pred_files.join(' ')}  // Expand list to space-separated args
    """
}
```

**Key detail**: `pred_files.join(' ')` expands `[file1, file2, file3]` to `"file1 file2 file3"` for command line.

## Pattern 4: Version Tracking Optimization

### Overview

Avoids collecting identical version files from parallel processes.

**Location**: Throughout `workflows/taxbencher.nf`

### The Pattern

```groovy
// Initialize version channel
ch_versions = Channel.empty()

// Add versions from module (optimization with .first())
ch_versions = ch_versions.mix(TAXPASTA_STANDARDISE.out.versions.first())
ch_versions = ch_versions.mix(TAXPASTA_TO_BIOBOXES.out.versions.first())
ch_versions = ch_versions.mix(OPAL_PER_SAMPLE.out.versions.first())
```

### Why `.first()`?

**Without `.first()` (wasteful)**:
```groovy
// TAXPASTA_TO_BIOBOXES runs 10 times (10 samples)
// Each emits identical versions.yml:
"""
"TAXPASTA_TO_BIOBOXES":
    python: 3.11.0
    pandas: 2.0.0
    ete3: 3.1.2
"""

ch_versions = ch_versions.mix(TAXPASTA_TO_BIOBOXES.out.versions)
// Collects 10 identical files → waste of memory and I/O
```

**With `.first()` (efficient)**:
```groovy
ch_versions = ch_versions.mix(TAXPASTA_TO_BIOBOXES.out.versions.first())
// Takes only first emission
// Remaining 9 identical files ignored
// Result: Same information, 90% less data
```

### When to Use

**Use `.first()` when**:
- Module runs multiple times in parallel
- Version info is identical across invocations
- Example: Same tool, same container, same code

**Don't use `.first()` when**:
- Different modules (versions differ)
- Version might vary by input
- Example: Conditional tool selection

### Complete Version Tracking Flow

```groovy
// 1. Initialize
ch_versions = Channel.empty()

// 2. Collect from modules (with optimization)
ch_versions = ch_versions.mix(MODULE1.out.versions.first())
ch_versions = ch_versions.mix(MODULE2.out.versions.first())
ch_versions = ch_versions.mix(MODULE3.out.versions.first())

// 3. Convert to YAML
softwareVersionsToYAML(ch_versions)
    .collectFile(
        storeDir: "${params.outdir}/pipeline_info",
        name: 'taxbencher_software_mqc_versions.yml',
        sort: true,
        newLine: true
    )
    .set { ch_collated_versions }

// 4. Include in MultiQC
ch_multiqc_files = ch_multiqc_files.mix(ch_collated_versions)
```

## Pattern 5: Conditional Logging

### Overview

Provides user feedback without consuming channels.

**Location**: `workflows/taxbencher.nf:51-59`

### Implementation

```groovy
// Log decisions for user visibility
ch_branched.standardised
    .subscribe { meta, file ->
        log.info "[TAXBENCHER] Sample ${meta.sample_id} | Label ${meta.label} | Classifier ${meta.classifier}: Using pre-standardised profile ${file.name}"
    }

ch_branched.needs_standardisation
    .subscribe { meta, file ->
        log.info "[TAXBENCHER] Sample ${meta.sample_id} | Label ${meta.label} | Classifier ${meta.classifier}: Standardising raw profiler output ${file.name}"
    }
```

### Key Characteristics

**`.subscribe { }` properties**:
1. **Non-consuming**: Items still flow through channel
2. **Side effect only**: For logging, validation, debugging
3. **No transformation**: Cannot change channel contents
4. **Immediate execution**: Runs as items arrive

### Use Cases

**1. Progress logging**:
```groovy
ch_input
    .subscribe { meta, file ->
        log.info "Processing ${meta.id}..."
    }
```

**2. Validation**:
```groovy
ch_input
    .subscribe { meta, file ->
        if (!file.exists()) {
            log.error "File not found: ${file}"
        }
    }
```

**3. Debugging**:
```groovy
ch_grouped
    .subscribe { sample_id, labels, files ->
        log.debug "Sample ${sample_id}: ${labels.size()} classifiers, ${files.size()} files"
    }
```

### Comparison with `.view()`

```groovy
// .view() - Simple inspection
ch_input.view()
// Output: [{id:'s1'}, /path/to/file.tsv]

// .view { } - Custom formatting
ch_input.view { meta, file -> "Processing: ${meta.id}" }
// Output: Processing: s1

// .subscribe { } - Full control
ch_input
    .subscribe { meta, file ->
        log.info "[${new Date()}] Starting ${meta.id}"
        // Can use conditionals, call functions, etc.
    }
// Output: [2024-01-15 10:30:45] Starting s1
```

## Channel Debugging Techniques

### 1. View Channel Contents

```groovy
// Simple view
ch_input.view()

// Custom formatting
ch_input.view { meta, file ->
    "Sample: ${meta.id}, File: ${file.name}"
}

// With label
ch_input.view { "DEBUG: $it" }
```

### 2. Inspect Channel Structure

```groovy
// Print structure
ch_grouped
    .subscribe {
        println "Tuple size: ${it.size()}"
        println "Elements: ${it}"
        println "First element type: ${it[0].getClass().name}"
    }
```

### 3. Count Channel Emissions

```groovy
// Count items
ch_input
    .count()
    .view { "Total items: $it" }
```

### 4. Save Channel State

```groovy
// Dump to file for inspection
ch_input
    .collectFile(name: 'debug_channel.txt', newLine: true) { meta, file ->
        "${meta.id}\t${file.name}"
    }
```

### 5. Validate Grouping

```groovy
// Check grouping results
ch_grouped
    .subscribe { sample_id, labels, files ->
        assert labels.size() == files.size(),
            "Mismatch: ${labels.size()} labels but ${files.size()} files"
        log.info "✓ Sample ${sample_id}: ${labels.size()} items"
    }
```

### 6. Trace Channel Flow

```groovy
ch_input
    .view { "A: $it" }
    .map { meta, file -> [meta.sample_id, file] }
    .view { "B: $it" }
    .groupTuple()
    .view { "C: $it" }
```

### 7. Use Nextflow's Built-in Debugging

```bash
# Run with trace
nextflow run main.nf -with-trace

# Run with report
nextflow run main.nf -with-report

# Run with timeline
nextflow run main.nf -with-timeline

# Enable debug logging
nextflow run main.nf -log .nextflow.log -debug
```

## Common Pitfalls and Solutions

### Pitfall 1: Channel Cardinality Mismatch

**Problem**:
```groovy
// This doesn't work as expected
process FOO {
    input:
    tuple val(meta), path(gold_standard)
    path(predictions)  // ALL predictions sent to EVERY invocation!
}
```

**Solution**: Embed in tuple
```groovy
process FOO {
    input:
    tuple val(meta), path(gold_standard), path(predictions)
}
```

### Pitfall 2: Forgetting to Return in `.branch { }`

**Problem**:
```groovy
ch_input.branch { meta, file ->
    tsv: file.name.endsWith('.tsv')
        // Missing return!
    other: true
}
```

**Solution**: Always return
```groovy
ch_input.branch { meta, file ->
    tsv: file.name.endsWith('.tsv')
        return [meta, file]
    other: true
        return [meta, file]
}
```

### Pitfall 3: Mutating Meta Map

**Problem**:
```groovy
ch_input.map { meta, file ->
    meta.new_field = 'value'  // Mutates original meta!
    [meta, file]
}
// All downstream processes see mutation
```

**Solution**: Create new meta
```groovy
ch_input.map { meta, file ->
    def new_meta = meta.clone()
    new_meta.new_field = 'value'
    [new_meta, file]
}
```

Or use map constructor:
```groovy
ch_input.map { meta, file ->
    def new_meta = [
        id: meta.id,
        sample_id: meta.sample_id,
        new_field: 'value'
    ]
    [new_meta, file]
}
```

### Pitfall 4: Using `.collect()` Too Early

**Problem**:
```groovy
// Collects all files into memory immediately
ch_all_files = ch_input.collect()
PROCESS(ch_all_files)
// Risk: OutOfMemoryError with large datasets
```

**Solution**: Collect only when needed
```groovy
// Let files flow through pipeline
PROCESS(ch_input)

// Collect only for final aggregation
MULTIQC(ch_results.collect())
```

### Pitfall 5: Incorrect `.groupTuple()` Key

**Problem**:
```groovy
// Wants to group by sample_id, but sample_id is in meta (position 0)
ch_input.groupTuple()  // Groups by entire meta map (wrong!)
```

**Solution**: Extract key first
```groovy
ch_input
    .map { meta, file -> [meta.sample_id, meta.label, file] }
    .groupTuple()  // Now groups by sample_id (position 0)
```

### Pitfall 6: Channel Reuse

**Problem**:
```groovy
ch_input = Channel.fromPath('*.tsv')
PROCESS1(ch_input)
PROCESS2(ch_input)  // Empty! Channel already consumed
```

**Solution**: Split channel
```groovy
ch_input = Channel.fromPath('*.tsv')
ch_input.into { ch_for_proc1; ch_for_proc2 }
PROCESS1(ch_for_proc1)
PROCESS2(ch_for_proc2)
```

Or use value channel:
```groovy
ch_reference = Channel.value(file('reference.fa'))
PROCESS1(ch_input, ch_reference)  // Works!
PROCESS2(ch_input2, ch_reference)  // Works! Value channels can be reused
```

## Advanced Patterns

### Pattern: Conditional Process Execution

```groovy
// Skip process if condition met
ch_input
    .branch { meta, file ->
        skip: meta.skip == true
            return [meta, file]
        process: true
            return [meta, file]
    }
    .set { ch_branched }

// Process only non-skipped items
PROCESS(ch_branched.process)

// Merge results
ch_output = ch_branched.skip.mix(PROCESS.out.results)
```

### Pattern: Error Recovery

```groovy
// Retry with different parameters on failure
process PROCESS_WITH_RETRY {
    errorStrategy { task.attempt <= 3 ? 'retry' : 'ignore' }
    maxRetries 3

    input:
    tuple val(meta), path(input_file)

    script:
    def memory = task.attempt == 1 ? '4.GB' :
                 task.attempt == 2 ? '8.GB' : '16.GB'
    """
    tool --memory ${memory} ${input_file}
    """
}
```

### Pattern: Dynamic Process Parallelization

```groovy
// Split large file into chunks for parallel processing
ch_input
    .splitFasta(by: 1000, file: true)
    .map { chunk -> [[id: chunk.baseName], chunk] }
    .set { ch_chunks }

PROCESS_CHUNK(ch_chunks)

// Merge results
ch_merged = PROCESS_CHUNK.out.results
    .groupTuple()
    .map { meta, chunks -> [meta, chunks.sort()] }

MERGE(ch_merged)
```

### Pattern: Multi-Path Processing

```groovy
// Process same data through multiple pipelines
ch_input
    .into { ch_for_path_a; ch_for_path_b; ch_for_path_c }

// Path A: Fast, low sensitivity
FAST_PROCESS(ch_for_path_a)

// Path B: Slow, high sensitivity
SLOW_PROCESS(ch_for_path_b)

// Path C: Alternative algorithm
ALT_PROCESS(ch_for_path_c)

// Combine results for comparison
ch_all_results = FAST_PROCESS.out
    .mix(SLOW_PROCESS.out)
    .mix(ALT_PROCESS.out)
    .groupTuple()

COMPARE_METHODS(ch_all_results)
```

### Pattern: Incremental Processing

```groovy
// Skip already-processed samples
ch_input
    .map { meta, file ->
        def output = file("${params.outdir}/${meta.id}/results.txt")
        [meta, file, output.exists()]
    }
    .branch { meta, file, exists ->
        skip: exists
            return [meta, file]
        process: true
            return [meta, file]
    }
    .set { ch_branched }

ch_branched.skip
    .subscribe { meta, file ->
        log.info "Skipping ${meta.id} (already processed)"
    }

PROCESS(ch_branched.process.map { meta, file, exists -> [meta, file] })
```

## See Also

- [Architecture](architecture.md) - High-level pipeline architecture
- [Modules](modules.md) - Module specifications
- [Development Guide](development-guide.md) - Contributing instructions
- [Testing](testing.md) - Test framework details

## References

- [Nextflow Channel API](https://www.nextflow.io/docs/latest/channel.html)
- [Nextflow Operators](https://www.nextflow.io/docs/latest/operator.html)
- [nf-core Channel Patterns](https://nf-co.re/docs/contributing/tutorials/creating_with_nf_core#channels)
