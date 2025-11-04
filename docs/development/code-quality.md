# Code Quality and Best Practices

This document provides comprehensive guidelines for maintaining high code quality in taxbencher. For specific implementation details, see [Development Guide](development-guide.md).

## Table of Contents
- [Code Quality Overview](#code-quality-overview)
- [nf-core Compliance](#nf-core-compliance)
- [Nextflow Best Practices](#nextflow-best-practices)
- [Groovy Best Practices](#groovy-best-practices)
- [Python Best Practices](#python-best-practices)
- [Module Design Patterns](#module-design-patterns)
- [Channel Operations Best Practices](#channel-operations-best-practices)
- [Error Handling Patterns](#error-handling-patterns)
- [Documentation Standards](#documentation-standards)
- [Performance Optimization](#performance-optimization)
- [Security Considerations](#security-considerations)
- [Maintainability Patterns](#maintainability-patterns)
- [Anti-Patterns to Avoid](#anti-patterns-to-avoid)
- [Code Review Checklist](#code-review-checklist)

## Code Quality Overview

### Current Status

**Grade: A-**

**nf-core Lint Results**:
- ✅ 205/205 tests passing
- ❌ 0 failures
- ⚠️ 5 minor warnings

**Innovative Patterns**:
1. Tuple-embedded channels for per-sample evaluation
2. Automatic format detection and branching
3. Per-sample grouping with groupTuple()

See [Code Quality Report](../reports/code-quality.md) for detailed analysis.

### Quality Standards

**We prioritize**:
1. **Correctness** - Code does what it's supposed to
2. **Readability** - Easy to understand and maintain
3. **Reliability** - Handles errors gracefully
4. **Performance** - Efficient resource usage
5. **Maintainability** - Easy to modify and extend

**Quality gates**:
- nf-core lint must pass (205/205)
- All tests must pass (or known failures documented)
- Code review approved
- Documentation updated

## nf-core Compliance

### Required nf-core Standards

#### 1. DSL2 Syntax

**Required**:
```groovy
// nextflow.config
nextflow.enable.dsl = 2
```

**Process structure**:
```groovy
process MYPROCESS {
    tag "$meta.id"
    label 'process_low'

    conda "${moduleDir}/environment.yml"
    container "..."

    input:
    tuple val(meta), path(input_file)

    output:
    tuple val(meta), path("*.output"), emit: results
    path "versions.yml"              , emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    """
    ...

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        tool: \$(tool --version)
    END_VERSIONS
    """

    stub:
    """
    touch stub.output
    cat <<-END_VERSIONS > versions.yml
    ...
    END_VERSIONS
    """
}
```

#### 2. Meta Map Pattern

**Always use meta maps** for sample tracking:
```groovy
// Required fields
def meta = [
    id: 'unique_identifier',  // Required
    sample_id: 'sample1'      // For grouping
]

// Optional fields
def meta = [
    id: 'sample1_kraken2',
    sample_id: 'sample1',
    label: 'sample1_kraken2',
    classifier: 'kraken2',
    taxonomy_db: 'NCBI'
]
```

**Meta propagation**:
```groovy
// Input
input:
tuple val(meta), path(input_file)

// Output
output:
tuple val(meta), path("*.out"), emit: results
```

#### 3. Version Tracking

**All processes must emit versions**:
```groovy
output:
path "versions.yml", emit: versions

script:
"""
# Process logic

cat <<-END_VERSIONS > versions.yml
"${task.process}":
    tool: \$(tool --version | sed 's/^version //g')
    python: \$(python --version | sed 's/Python //g')
END_VERSIONS
"""
```

**Workflow version collection**:
```groovy
ch_versions = Channel.empty()
ch_versions = ch_versions.mix(PROCESS1.out.versions.first())
ch_versions = ch_versions.mix(PROCESS2.out.versions.first())

softwareVersionsToYAML(ch_versions)
    .collectFile(name: 'pipeline_software_mqc_versions.yml')
```

#### 4. Process Labels

**Use standard resource labels**:
```groovy
label 'process_single'   // 1 CPU, 6 GB memory
label 'process_low'      // 2 CPUs, 12 GB memory
label 'process_medium'   // 6 CPUs, 36 GB memory
label 'process_high'     // 12 CPUs, 72 GB memory
```

**Custom labels** (defined in `conf/base.config`):
```groovy
withLabel: process_custom {
    cpus   = { 4 * task.attempt }
    memory = { 24.GB * task.attempt }
    time   = { 8.h * task.attempt }
}
```

#### 5. Stub Implementation

**All processes must support stub mode**:
```groovy
stub:
def prefix = task.ext.prefix ?: "${meta.id}"
"""
# Create empty output files
touch ${prefix}.output

# Still emit versions
cat <<-END_VERSIONS > versions.yml
"${task.process}":
    tool: 1.0.0
END_VERSIONS
"""
```

#### 6. when: Directive

**Always include when block**:
```groovy
when:
task.ext.when == null || task.ext.when
```

This allows users to conditionally skip processes via config.

### nf-core Linting

**Run before every commit**:
```bash
nf-core pipelines lint
```

**Common lint requirements**:
1. `meta.yml` for every module
2. `tests/main.nf.test` for every module
3. Container specifications for all processes
4. No TODO comments (create GitHub issues instead)
5. All parameters in `nextflow_schema.json`

**Fix lint issues**:
```bash
# Auto-fix formatting
nf-core pipelines lint --fix

# Update to latest template
nf-core pipelines sync
```

## Nextflow Best Practices

### 1. Naming Conventions

**Channels**: `ch_` prefix
```groovy
ch_input
ch_taxpasta
ch_bioboxes_per_sample
```

**Processes**: UPPERCASE
```groovy
TAXPASTA_TO_BIOBOXES
OPAL_PER_SAMPLE
```

**Variables**: camelCase
```groovy
def sampleId = meta.sample_id
def outputFile = "${prefix}.output"
def numClassifiers = labels.size()
```

### 2. Channel Operations

**Use descriptive variable names**:
```groovy
// Good
ch_input
    .map { meta, file -> [meta.sample_id, meta.label, file] }
    .set { ch_grouped_by_sample }

// Bad
ch_input
    .map { meta, file -> [meta.sample_id, meta.label, file] }
    .set { ch_temp }
```

**Document complex transformations**:
```groovy
//
// Group bioboxes by sample_id for per-sample OPAL evaluation
// Each biological sample gets its own OPAL run with all its classifiers
//
ch_bioboxes_per_sample = TAXPASTA_TO_BIOBOXES.out.bioboxes
    .map { meta, bioboxes ->
        // Extract sample_id as grouping key
        [meta.sample_id, meta.label, bioboxes]
    }
    .groupTuple()  // Groups by first element (sample_id)
```

**Avoid channel reuse**:
```groovy
// Bad: Channel consumed twice
ch_input = Channel.fromPath('*.tsv')
PROCESS1(ch_input)
PROCESS2(ch_input)  // Empty! Already consumed

// Good: Split channel
ch_input = Channel.fromPath('*.tsv')
ch_input.into { ch_for_proc1; ch_for_proc2 }
PROCESS1(ch_for_proc1)
PROCESS2(ch_for_proc2)

// Better: Use value channel if single item
ch_reference = Channel.value(file('reference.fa'))
PROCESS1(ch_input1, ch_reference)  // Can reuse
PROCESS2(ch_input2, ch_reference)  // Can reuse
```

### 3. Process Organization

**One purpose per process**:
```groovy
// Good: Clear, single responsibility
process CONVERT_FORMAT {
    // Only converts format
}

process VALIDATE_OUTPUT {
    // Only validates
}

// Bad: Multiple responsibilities
process CONVERT_AND_VALIDATE {
    // Mixing concerns
}
```

**Input/output clarity**:
```groovy
// Good: Clear input/output structure
input:
tuple val(meta), path(taxpasta_tsv)

output:
tuple val(meta), path("*.bioboxes"), emit: bioboxes
path "versions.yml"                , emit: versions

// Bad: Ambiguous outputs
output:
path "*"  // What files? What format?
```

### 4. Script Organization

**Use heredoc for multi-line scripts**:
```groovy
script:
"""
#!/bin/bash
set -euo pipefail

# Validate input
if [ ! -s ${input_file} ]; then
    echo "ERROR: Input file is empty" >&2
    exit 1
fi

# Run tool
tool \\
    --input ${input_file} \\
    --output ${prefix}.out \\
    ${args}

# Verify output
if [ ! -s ${prefix}.out ]; then
    echo "ERROR: Tool failed to produce output" >&2
    exit 1
fi
"""
```

**Escape variables properly**:
```groovy
"""
# Nextflow variables (evaluated by Nextflow)
input_file=${input_file}
prefix=${prefix}

# Shell variables (evaluated by shell)
NUM_LINES=\$(wc -l < ${input_file})
echo "Processing \$NUM_LINES lines"
"""
```

### 5. Error Handling

**Validate inputs in script**:
```groovy
"""
# Validate input exists and is not empty
if [ ! -s ${input_file} ]; then
    echo "ERROR: Input file ${input_file} does not exist or is empty" >&2
    exit 1
fi

# Validate output was created
if [ ! -s ${output_file} ]; then
    echo "ERROR: Tool failed to produce output ${output_file}" >&2
    exit 1
fi
"""
```

**Use error strategies**:
```groovy
// In conf/base.config
process {
    errorStrategy = { task.exitStatus in [143,137,104,134,139] ? 'retry' : 'finish' }
    maxRetries    = 1
    maxErrors     = '-1'
}

// In conf/modules.config (process-specific)
withName: 'OPAL_PER_SAMPLE' {
    errorStrategy = 'retry'
    maxRetries    = 3
}
```

**Provide helpful error messages**:
```groovy
"""
if ! tool --validate ${input_file}; then
    echo "" >&2
    echo "ERROR: Input validation failed for ${meta.id}" >&2
    echo "File: ${input_file}" >&2
    echo "" >&2
    echo "Common issues:" >&2
    echo "  1. Incorrect file format" >&2
    echo "  2. Missing required columns" >&2
    echo "  3. Invalid data types" >&2
    echo "" >&2
    exit 1
fi
"""
```

## Groovy Best Practices

### 1. Safe Navigation

**Use safe navigation operator**:
```groovy
// Good: Safe navigation
def value = params.optional_param ?: 'default'
def length = meta?.labels?.size() ?: 0

// Bad: Null pointer risk
def value = params.optional_param
def length = meta.labels.size()  // Crashes if labels is null
```

### 2. String Handling

**Choose appropriate quote type**:
```groovy
// Single quotes: Literal strings (no interpolation)
def literal = 'This is $variable'  // Output: "This is $variable"

// Double quotes: String interpolation
def interpolated = "This is ${variable}"  // Output: "This is actual_value"

// Triple quotes: Multi-line strings
def multiline = """
This is a
multi-line string
with ${variable} interpolation
"""

// Triple single quotes: Multi-line literal
def literal_multiline = '''
No ${interpolation} here
Just literal text
'''
```

### 3. Collections

**Use appropriate collection methods**:
```groovy
// Map
def mapped = list.collect { it * 2 }

// Filter
def filtered = list.findAll { it > 5 }

// Reduce
def sum = list.inject(0) { acc, val -> acc + val }

// Check existence
def exists = list.any { it > 10 }
def allMatch = list.every { it > 0 }

// Join
def joined = list.join(', ')
```

### 4. Closures

**Understand closure scope**:
```groovy
// Good: Clear closure parameter
def doubled = list.collect { item ->
    item * 2
}

// Acceptable: Implicit 'it' for simple operations
def doubled = list.collect { it * 2 }

// Bad: Unclear with multiple operations
def result = list.collect {
    def temp = it * 2
    temp + 10  // Return value
}
```

### 5. Type Safety

**Use type declarations when helpful**:
```groovy
// Good: Clear types for complex structures
def Map<String, Integer> countMap = [:]

// Good: Type for function parameters
def processFile(File inputFile, String outputDir) {
    // Implementation
}

// Acceptable: Groovy's dynamic typing
def result = compute()  // Type inferred
```

## Python Best Practices

### 1. Script Structure

**Standard template for bin/ scripts**:
```python
#!/usr/bin/env python3
"""
Brief description of what this script does.

Author: Your Name
Date: YYYY-MM-DD
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Detailed script description"
    )
    parser.add_argument(
        '-i', '--input',
        type=Path,
        required=True,
        help='Input file path'
    )
    parser.add_argument(
        '-o', '--output',
        type=Path,
        required=True,
        help='Output file path'
    )
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 1.0.0'
    )

    args = parser.parse_args()

    # Validate inputs
    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        sys.exit(1)

    # Process
    try:
        process_file(args.input, args.output)
        logger.info(f"Successfully processed {args.input}")
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        sys.exit(1)


def process_file(input_path: Path, output_path: Path) -> None:
    """
    Process input file and write output.

    Args:
        input_path: Path to input file
        output_path: Path to output file

    Raises:
        ValueError: If input format is invalid
        IOError: If file operations fail
    """
    # Implementation
    pass


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
```

### 2. Error Handling

**Specific exception handling**:
```python
# Good: Specific exceptions
try:
    with open(file_path) as f:
        data = parse_file(f)
except FileNotFoundError:
    logger.error(f"File not found: {file_path}")
    sys.exit(1)
except PermissionError:
    logger.error(f"Permission denied: {file_path}")
    sys.exit(1)
except ValueError as e:
    logger.error(f"Invalid file format: {e}")
    sys.exit(1)

# Bad: Catch-all exception
try:
    process()
except:  # Too broad
    print("Something failed")
```

### 3. Type Hints

**Use type hints for clarity**:
```python
from typing import List, Dict, Optional, Tuple

def process_taxonomy(
    taxonomy_id: int,
    count: int,
    taxonomy_db: str = "NCBI"
) -> Dict[str, any]:
    """
    Process taxonomy information.

    Args:
        taxonomy_id: NCBI taxonomy ID
        count: Read count
        taxonomy_db: Taxonomy database name

    Returns:
        Dictionary with processed taxonomy information
    """
    return {
        'taxid': taxonomy_id,
        'count': count,
        'db': taxonomy_db
    }
```

### 4. File Operations

**Use pathlib for file operations**:
```python
from pathlib import Path

# Good: pathlib
input_path = Path(args.input)
if not input_path.exists():
    logger.error(f"File not found: {input_path}")
    sys.exit(1)

output_path = Path(args.output)
output_path.parent.mkdir(parents=True, exist_ok=True)

with input_path.open() as f:
    data = f.read()

# Bad: string paths
import os
if not os.path.exists(args.input):
    print("File not found")
```

### 5. Code Style

**Follow PEP 8**:
```python
# Good: PEP 8 compliant
def process_sample_data(
    sample_id: str,
    taxonomy_db: str = "NCBI"
) -> Dict[str, int]:
    """Process sample with specified taxonomy database."""
    results = {}

    for taxid, count in read_sample_file(sample_id):
        if count > MIN_COUNT_THRESHOLD:
            results[taxid] = count

    return results

# Bad: Style violations
def processSampleData(sampleId,taxonomyDb="NCBI"):
    results={}
    for taxid,count in readSampleFile(sampleId):
        if count>MIN_COUNT_THRESHOLD:results[taxid]=count
    return results
```

**Format with black and ruff**:
```bash
# Format code
black bin/*.py

# Lint
ruff check bin/*.py

# Type check
mypy bin/*.py
```

## Module Design Patterns

### Pattern 1: Standard Module Structure

```groovy
process MODULE_NAME {
    tag "$meta.id"
    label 'process_low'

    conda "${moduleDir}/environment.yml"
    container "biocontainers/tool:version"

    input:
    tuple val(meta), path(input_file)

    output:
    tuple val(meta), path("*.output"), emit: results
    path "versions.yml"              , emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    def prefix = task.ext.prefix ?: "${meta.id}"

    """
    # Input validation
    [ -s ${input_file} ] || { echo "ERROR: Empty input" >&2; exit 1; }

    # Process
    tool \\
        --input ${input_file} \\
        --output ${prefix}.output \\
        ${args}

    # Output validation
    [ -s ${prefix}.output ] || { echo "ERROR: No output" >&2; exit 1; }

    # Versions
    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        tool: \$(tool --version)
    END_VERSIONS
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    touch ${prefix}.output
    echo '"${task.process}": tool: 1.0.0' > versions.yml
    """
}
```

### Pattern 2: Multi-Tool Module

```groovy
process MULTI_TOOL {
    tag "$meta.id"
    label 'process_medium'

    input:
    tuple val(meta), path(input_file)

    output:
    tuple val(meta), path("*.primary.out"), emit: primary
    tuple val(meta), path("*.secondary.out"), emit: secondary, optional: true
    path "versions.yml", emit: versions

    script:
    def args = task.ext.args ?: ''
    def args2 = task.ext.args2 ?: ''
    def prefix = task.ext.prefix ?: "${meta.id}"

    """
    # Tool 1
    tool1 \\
        --input ${input_file} \\
        --output ${prefix}.primary.out \\
        ${args}

    # Tool 2 (optional)
    if [ -n "${args2}" ]; then
        tool2 \\
            --input ${prefix}.primary.out \\
            --output ${prefix}.secondary.out \\
            ${args2}
    fi

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        tool1: \$(tool1 --version)
        tool2: \$(tool2 --version || echo "not run")
    END_VERSIONS
    """
}
```

### Pattern 3: Conditional Output Module

```groovy
process CONDITIONAL_OUTPUT {
    tag "$meta.id"
    label 'process_low'

    input:
    tuple val(meta), path(input_file)

    output:
    tuple val(meta), path("*.main.out"), emit: main
    tuple val(meta), path("*.stats.txt"), emit: stats, optional: true
    tuple val(meta), path("*.plot.pdf"), emit: plot, optional: true
    path "versions.yml", emit: versions

    script:
    def args = task.ext.args ?: ''
    def prefix = task.ext.prefix ?: "${meta.id}"
    def generate_stats = params.generate_stats ?: false
    def generate_plot = params.generate_plot ?: false

    """
    # Main processing (always runs)
    tool --input ${input_file} --output ${prefix}.main.out ${args}

    # Optional stats
    if [ "${generate_stats}" = "true" ]; then
        tool --stats ${prefix}.main.out > ${prefix}.stats.txt
    fi

    # Optional plot
    if [ "${generate_plot}" = "true" ]; then
        tool --plot ${prefix}.main.out ${prefix}.plot.pdf
    fi

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        tool: \$(tool --version)
    END_VERSIONS
    """
}
```

### Pattern 4: Python Script Wrapper

```groovy
process PYTHON_SCRIPT {
    tag "$meta.id"
    label 'process_single'

    conda "${moduleDir}/environment.yml"
    container "community.wave.seqera.io/library/package:hash"

    input:
    tuple val(meta), path(input_file)

    output:
    tuple val(meta), path("*.output"), emit: results
    path "versions.yml", emit: versions

    script:
    def args = task.ext.args ?: ''
    def prefix = task.ext.prefix ?: "${meta.id}"

    """
    script.py \\
        --input ${input_file} \\
        --output ${prefix}.output \\
        --sample-id ${meta.sample_id} \\
        ${args}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: \$(python --version | sed 's/Python //g')
        script: \$(script.py --version 2>&1 | sed 's/script.py //g')
    END_VERSIONS
    """
}
```

## Channel Operations Best Practices

### Use Tuple-Embedded Pattern for Multi-File Processes

**Problem**: Separate channels cause cardinality mismatch
```groovy
// Bad: ALL predictions sent to EVERY invocation
input:
tuple val(meta), path(gold_standard)
path(predictions)  // Separate channel

// Good: Predictions embedded in tuple
input:
tuple val(meta), path(gold_standard), path(predictions)
```

**Implementation**:
```groovy
ch_grouped = ch_input
    .map { meta, file -> [meta.sample_id, meta.label, file] }
    .groupTuple()
    .combine(ch_reference)
    .map { sample_id, labels, files, ref ->
        def meta_grouped = [id: sample_id, labels: labels.join(',')]
        tuple(meta_grouped, ref, files)  // Files embedded!
    }
```

### Optimize Version Collection

**Use `.first()` for identical parallel outputs**:
```groovy
// Good: Collect only one copy
ch_versions = ch_versions.mix(PROCESS.out.versions.first())

// Bad: Collects redundant copies
ch_versions = ch_versions.mix(PROCESS.out.versions)
```

### Document Complex Transformations

```groovy
// Good: Well-documented transformation
//
// CHANNEL TRANSFORMATION: Group by sample_id
// Input:  [{id:'s1_k', sample_id:'s1'}, file1], [{id:'s1_m', sample_id:'s1'}, file2]
// Step 1: Extract sample_id as first element: ['s1', 's1_k', file1], ['s1', 's1_m', file2]
// Step 2: groupTuple() groups by first element: ['s1', ['s1_k','s1_m'], [file1,file2]]
// Step 3: Create aggregated meta: [{id:'s1', labels:'s1_k,s1_m'}, [file1, file2]]
//
ch_grouped = ch_input
    .map { meta, file -> [meta.sample_id, meta.label, file] }
    .groupTuple()
    .map { sample_id, labels, files ->
        def meta_grouped = [id: sample_id, labels: labels.join(',')]
        [meta_grouped, files]
    }
```

## Error Handling Patterns

### Pattern 1: Input Validation

```groovy
script:
"""
#!/bin/bash
set -euo pipefail

# Validate input exists and is not empty
if [ ! -s ${input_file} ]; then
    echo "ERROR: Input file ${input_file} does not exist or is empty" >&2
    exit 1
fi

# Validate file format
if ! head -1 ${input_file} | grep -q "expected_header"; then
    echo "ERROR: Invalid file format for ${input_file}" >&2
    echo "Expected header: expected_header" >&2
    exit 1
fi

# Process...
"""
```

### Pattern 2: Dependency Validation

```groovy
script:
"""
# Validate required tools are available
command -v tool1 >/dev/null 2>&1 || {
    echo "ERROR: tool1 is required but not found" >&2
    exit 127
}

command -v tool2 >/dev/null 2>&1 || {
    echo "ERROR: tool2 is required but not found" >&2
    exit 127
}

# Process...
"""
```

### Pattern 3: Output Validation

```groovy
script:
"""
# Run tool
tool --input ${input_file} --output ${output_file}

# Verify output was created
if [ ! -f ${output_file} ]; then
    echo "ERROR: Tool did not create output file ${output_file}" >&2
    exit 1
fi

# Verify output is not empty
if [ ! -s ${output_file} ]; then
    echo "ERROR: Output file ${output_file} is empty" >&2
    exit 1
fi

# Verify output format (optional)
if ! head -1 ${output_file} | grep -q "@@TAXID"; then
    echo "ERROR: Output file ${output_file} has invalid format" >&2
    exit 1
fi
"""
```

### Pattern 4: Graceful Degradation

```groovy
script:
"""
# Try primary method
if tool --mode advanced ${input_file} > ${output_file} 2>tool.err; then
    echo "[INFO] Processing succeeded with advanced mode" >&2
else
    echo "[WARN] Advanced mode failed, trying basic mode" >&2

    # Fallback to basic method
    if tool --mode basic ${input_file} > ${output_file} 2>tool.err; then
        echo "[INFO] Processing succeeded with basic mode" >&2
    else
        echo "[ERROR] Both advanced and basic modes failed" >&2
        cat tool.err >&2
        exit 1
    fi
fi
"""
```

### Pattern 5: Error Strategy Configuration

```groovy
// conf/base.config
process {
    // Retry on resource-related errors
    errorStrategy = {
        task.exitStatus in [143,137,104,134,139] ? 'retry' : 'finish'
    }
    maxRetries = 1
    maxErrors = '-1'
}

// conf/modules.config
withName: 'CRITICAL_PROCESS' {
    errorStrategy = 'retry'
    maxRetries = 3
    memory = { check_max( 12.GB * task.attempt, 'memory' ) }
}

withName: 'OPTIONAL_PROCESS' {
    errorStrategy = 'ignore'  // Don't fail pipeline if this fails
}
```

## Documentation Standards

### Module Documentation

**Required files**:
1. `main.nf` - Inline comments
2. `meta.yml` - Complete metadata
3. `README.md` - Usage examples (optional)

**meta.yml template**:
```yaml
name: module_name
description: Brief description of what this module does
keywords:
  - keyword1
  - keyword2
tools:
  - tool:
      description: Tool description
      homepage: https://tool.homepage
      documentation: https://tool.docs
      tool_dev_url: https://github.com/tool/repo
      doi: "10.1234/doi"
      licence: ["MIT"]
input:
  - meta:
      type: map
      description: |
        Groovy Map containing sample information
        e.g. [id: 'sample1', sample_id: 'sample1']
  - input_file:
      type: file
      description: Input file description
      pattern: "*.{tsv,txt}"
output:
  - meta:
      type: map
      description: Groovy Map containing sample information
  - results:
      type: file
      description: Output file description
      pattern: "*.output"
  - versions:
      type: file
      description: File containing software versions
      pattern: "versions.yml"
authors:
  - "@github_username"
maintainers:
  - "@github_username"
```

### Inline Comments

**Process-level comments**:
```groovy
//
// MODULE: TAXPASTA_TO_BIOBOXES
// Converts taxpasta TSV format to CAMI Bioboxes format for OPAL evaluation
//
// Input: Taxpasta TSV with taxonomy_id and count columns
// Output: CAMI Bioboxes profiling format with lineage paths
//
// Note: Uses ete3 for NCBI taxonomy lookups (~500MB download on first run)
//
TAXPASTA_TO_BIOBOXES(ch_taxpasta)
```

**Complex logic comments**:
```groovy
// Convert predictions to list if it's a single file
// OPAL accepts either single file or list, but we need consistent handling
def pred_files = predictions instanceof List ? predictions : [predictions]
```

### Workflow Documentation

**Section headers**:
```groovy
//
// SECTION: Input validation and format detection
//
// Automatically detects input format based on file extension
// .tsv/.txt → Already standardized, skip TAXPASTA_STANDARDISE
// Other → Raw profiler output, run TAXPASTA_STANDARDISE
//
```

**Rationale comments**:
```groovy
// NOTE: .first() optimization - versions.yml content is identical across all invocations
// Taking first emission prevents collecting redundant files (memory optimization)
ch_versions = ch_versions.mix(TAXPASTA_TO_BIOBOXES.out.versions.first())
```

## Performance Optimization

### Resource Allocation

**Start conservative, scale with retries**:
```groovy
withName: 'MEMORY_INTENSIVE' {
    memory = { check_max( 12.GB * task.attempt, 'memory' ) }
    time   = { check_max( 8.h * task.attempt, 'time' ) }
    cpus   = 4
}
```

**Profile-specific overrides**:
```groovy
profiles {
    bigmem {
        process {
            withName: 'OPAL_PER_SAMPLE' {
                memory = { check_max( 64.GB * task.attempt, 'memory' ) }
            }
        }
    }
}
```

### Channel Operations

**Avoid premature `.collect()`**:
```groovy
// Bad: Collects all files into memory early
ch_all_files = ch_input.collect()
PROCESS(ch_all_files)

// Good: Let files stream through pipeline
PROCESS(ch_input)
// Only collect when needed
FINAL_AGGREGATION(PROCESS.out.collect())
```

**Use `.first()` for optimization**:
```groovy
// Save memory by taking only one version file
ch_versions = ch_versions.mix(PROCESS.out.versions.first())
```

### Process Optimization

**Minimize container layers**:
```groovy
// Good: Single conda/container
conda "bioconda::tool=1.0"

// Bad: Multiple containers
conda "bioconda::tool1=1.0 bioconda::tool2=1.0 bioconda::tool3=1.0"
// Consider: Create multi-tool container or use Wave
```

**Use scratch for temp files**:
```groovy
process BIG_TEMP_FILES {
    scratch true  // Use local scratch space

    script:
    """
    # Large temporary files written to scratch
    tool --temp-dir \$TMPDIR ${input} ${output}
    """
}
```

## Security Considerations

### Input Validation

**Sanitize user inputs**:
```python
# Good: Validate input
def validate_sample_id(sample_id: str) -> str:
    """Validate and sanitize sample ID."""
    if not re.match(r'^[a-zA-Z0-9_-]+$', sample_id):
        raise ValueError(f"Invalid sample ID: {sample_id}")
    return sample_id

# Bad: Trust user input
sample_id = args.sample_id  # Could contain shell injection
```

**Avoid command injection**:
```groovy
// Good: Variables in Nextflow
"""
tool --sample ${meta.sample_id} --output ${output_file}
"""

// Bad: String interpolation with user input
"""
tool --sample \$(echo ${user_input}) --output ${output_file}
"""
```

### File Permissions

**Set appropriate permissions**:
```bash
# In bin/ scripts
chmod 755 bin/*.py
chmod 644 assets/test_data/*
```

**Don't commit secrets**:
```bash
# .gitignore
*.key
*.pem
credentials.json
.env
```

### Container Security

**Use specific versions**:
```groovy
// Good: Pinned version
container "quay.io/biocontainers/tool:1.0.0--abc123"

// Bad: Latest tag
container "quay.io/biocontainers/tool:latest"
```

**Prefer official containers**:
```groovy
// Best: Official biocontainers
container "quay.io/biocontainers/tool:version"

// Good: Seqera Wave (reproducible)
container "wave.seqera.io/wt/hash/wave/build:name--hash"

// Caution: Custom containers (document provenance)
container "dockerhub/user/tool:version"
```

## Maintainability Patterns

### Code Organization

**Logical file grouping**:
```
modules/local/
├── format_conversion/      # Group related modules
│   ├── taxpasta_standardise/
│   └── taxpasta_to_bioboxes/
├── evaluation/
│   ├── opal_per_sample/
│   └── comparative_analysis/
└── utilities/
    └── validation/
```

**Consistent naming**:
- Processes: `VERB_NOUN` (e.g., `CONVERT_FORMAT`, `VALIDATE_INPUT`)
- Channels: `ch_description` (e.g., `ch_bioboxes_per_sample`)
- Variables: `camelCase` (e.g., `sampleId`, `numClassifiers`)

### Avoid Magic Numbers

```groovy
// Bad
if (count > 100) {
    // Why 100?
}

// Good
def MIN_COUNT_THRESHOLD = 100  // Minimum count for reliable classification
if (count > MIN_COUNT_THRESHOLD) {
    // Clear intent
}
```

### DRY Principle

**Extract reusable code**:
```groovy
// Bad: Repeated logic
def meta1 = [id: sample1, sample_id: sample1, ...]
def meta2 = [id: sample2, sample_id: sample2, ...]

// Good: Function
def createMeta(sample_id, classifier) {
    return [
        id: "${sample_id}_${classifier}",
        sample_id: sample_id,
        classifier: classifier
    ]
}
```

### Dependency Management

**Pin versions**:
```yaml
# environment.yml
dependencies:
  - python=3.11
  - pandas=2.0.0      # Specific version
  - ete3>=3.1.2,<4.0  # Version range
```

**Document dependencies**:
```groovy
// In module main.nf
// NOTE: This module requires:
// - pandas >= 2.0 for DataFrame operations
// - ete3 >= 3.1 for NCBI taxonomy lookups
// Wave container includes both dependencies
```

## Anti-Patterns to Avoid

### 1. Channel Reuse

```groovy
// ❌ Bad: Channel consumed twice
ch_input = Channel.fromPath('*.tsv')
PROCESS1(ch_input)
PROCESS2(ch_input)  // Empty!

// ✅ Good: Split channel
ch_input = Channel.fromPath('*.tsv')
ch_input.into { ch_for_1; ch_for_2 }
```

### 2. Silent Failures

```groovy
// ❌ Bad: Failures hidden
"""
tool ${input} > ${output} || true
"""

// ✅ Good: Fail explicitly
"""
if ! tool ${input} > ${output}; then
    echo "ERROR: Tool failed" >&2
    exit 1
fi
"""
```

### 3. Hardcoded Paths

```groovy
// ❌ Bad: Hardcoded paths
"""
/usr/local/bin/tool ${input}
"""

// ✅ Good: Rely on PATH
"""
tool ${input}
"""
```

### 4. Unclear Variable Names

```groovy
// ❌ Bad: Unclear names
def x = meta.sample_id
def y = labels.size()
def z = files.join(' ')

// ✅ Good: Descriptive names
def sampleId = meta.sample_id
def numClassifiers = labels.size()
def predictionFiles = files.join(' ')
```

### 5. Missing Error Messages

```groovy
// ❌ Bad: Generic error
"""
tool ${input} || exit 1
"""

// ✅ Good: Informative error
"""
if ! tool ${input}; then
    echo "ERROR: Tool failed processing ${meta.id}" >&2
    echo "Input: ${input}" >&2
    exit 1
fi
"""
```

### 6. Mutable State

```groovy
// ❌ Bad: Mutating meta
ch_input.map { meta, file ->
    meta.new_field = 'value'  // Mutates original!
    [meta, file]
}

// ✅ Good: Create new meta
ch_input.map { meta, file ->
    def new_meta = meta + [new_field: 'value']
    [new_meta, file]
}
```

### 7. Premature Optimization

```groovy
// ❌ Bad: Complex optimization that hurts readability
ch_result = ch_input
    .flatMap { it.split(',').collect { [it, counter++] } }
    .filter { it[1] % 2 == 0 }
    .map { it[0] }

// ✅ Good: Clear, readable code
ch_result = ch_input
    .map { it.split(',') }
    .flatten()
    .filter { /* clear condition */ }
```

## Code Review Checklist

### Pre-Review (Author)

- [ ] Code follows nf-core guidelines
- [ ] nf-core lint passes (205/205)
- [ ] All tests pass (or failures documented)
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Commit messages follow conventional commits
- [ ] No TODOs without GitHub issues

### Functionality Review

- [ ] Code does what it's supposed to
- [ ] Edge cases handled
- [ ] Error messages are clear
- [ ] Input validation present
- [ ] Output validation present

### Code Quality Review

- [ ] Naming is clear and consistent
- [ ] Comments explain "why", not "what"
- [ ] No magic numbers
- [ ] No code duplication
- [ ] Functions/processes have single responsibility

### Nextflow-Specific Review

- [ ] Meta maps used correctly
- [ ] Channels not reused inappropriately
- [ ] Version tracking implemented
- [ ] Stub mode implemented
- [ ] Process labels appropriate
- [ ] when: block present

### Testing Review

- [ ] Tests cover main functionality
- [ ] Tests cover error cases
- [ ] Test data is appropriate size
- [ ] Snapshots updated (if needed)
- [ ] Test documentation clear

### Documentation Review

- [ ] meta.yml complete
- [ ] Inline comments present
- [ ] README updated (if needed)
- [ ] Output files documented
- [ ] Parameters documented in schema

### Security Review

- [ ] No hardcoded secrets
- [ ] Input validation present
- [ ] No command injection risks
- [ ] Container versions pinned
- [ ] No suspicious file operations

### Performance Review

- [ ] Resource allocation appropriate
- [ ] No premature .collect()
- [ ] Channel operations efficient
- [ ] Temp files cleaned up

## See Also

- [Code Quality Report](../reports/code-quality.md) - Latest quality assessment
- [Development Guide](development-guide.md) - Contributing instructions
- [Testing](testing.md) - Test framework and patterns
- [Modules](modules.md) - Module specifications
- [Workflow Patterns](workflow-patterns.md) - Channel operation patterns

## References

- [nf-core Guidelines](https://nf-co.re/docs/contributing/guidelines)
- [Nextflow Best Practices](https://www.nextflow.io/docs/latest/amazonnext.html#best-practices)
- [PEP 8 Style Guide](https://peps.python.org/pep-0008/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [Clean Code Principles](https://www.goodreads.com/book/show/3735293-clean-code)
