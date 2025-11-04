# Development Guide

This guide provides comprehensive instructions for contributing to taxbencher. For architecture details, see [Architecture](architecture.md). For workflow patterns, see [Workflow Patterns](workflow-patterns.md).

## Table of Contents
- [Getting Started](#getting-started)
- [Development Environment Setup](#development-environment-setup)
- [Development Workflow](#development-workflow)
- [Adding New Modules](#adding-new-modules)
- [Writing Tests](#writing-tests)
- [Configuration Management](#configuration-management)
- [Code Style and Standards](#code-style-and-standards)
- [Git Workflow](#git-workflow)
- [Pull Request Process](#pull-request-process)
- [Documentation Requirements](#documentation-requirements)
- [Troubleshooting Development Issues](#troubleshooting-development-issues)

## Getting Started

### Prerequisites

**Required**:
- Nextflow ≥24.10.5
- Docker, Singularity, or Conda
- Git
- Java 11+ (for Nextflow)
- Python 3.11+ (for bin/ scripts)

**Recommended**:
- nf-core tools (`pip install nf-core`)
- nf-test (`nf-core tools install nf-test`)
- Visual Studio Code with Nextflow extension

### Initial Setup

1. **Fork the repository** on GitHub:
   ```bash
   # Visit: https://github.com/FOI-Bioinformatics/taxbencher
   # Click "Fork" button
   ```

2. **Clone your fork**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/taxbencher.git
   cd taxbencher
   ```

3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/FOI-Bioinformatics/taxbencher.git
   git fetch upstream
   ```

4. **Verify setup**:
   ```bash
   nextflow run . -profile test,docker
   ```

### Project Structure Quick Reference

```
taxbencher/
├── workflows/           # Main workflow logic
│   └── taxbencher.nf
├── modules/
│   ├── local/          # Custom modules
│   └── nf-core/        # nf-core modules
├── subworkflows/
│   ├── local/          # Custom subworkflows
│   └── nf-core/        # nf-core utils
├── bin/                # Executable scripts
├── lib/                # Groovy libraries
├── conf/               # Configuration files
├── assets/             # Test data and schemas
├── docs/               # Documentation
└── tests/              # Pipeline-level tests
```

## Development Environment Setup

### Option 1: Local Development

**Install dependencies**:
```bash
# Install Nextflow
curl -s https://get.nextflow.io | bash
sudo mv nextflow /usr/local/bin/

# Install nf-core tools
pip install nf-core

# Install nf-test
nf-core tools install nf-test

# Install Python dependencies (for bin/ scripts)
pip install pandas ete3 biopython
```

**Configure editor**:
```bash
# VS Code extensions (recommended)
code --install-extension nextflow.nextflow
code --install-extension ms-python.python
```

### Option 2: GitHub Codespaces

**Launch Codespace**:
1. Visit repository on GitHub
2. Click "Code" → "Codespaces" → "Create codespace on dev"
3. Wait for environment setup (includes Nextflow + nf-core)

**Verify installation**:
```bash
nextflow -version
nf-core --version
nf-test version
```

### Option 3: Docker Development Container

**Use devcontainer**:
```bash
# Install Docker and VS Code Dev Containers extension
code --install-extension ms-vscode-remote.remote-containers

# Open in container
code .
# VS Code will prompt to "Reopen in Container"
```

Configuration: `.devcontainer/devcontainer.json`

## Development Workflow

### Before Starting Development

1. **Check for existing issues**:
   ```bash
   # Visit: https://github.com/FOI-Bioinformatics/taxbencher/issues
   # Avoid duplicating work
   ```

2. **Create or comment on issue**:
   ```
   "I'm working on adding module X / fixing bug Y"
   ```

3. **Sync with upstream**:
   ```bash
   git fetch upstream
   git checkout dev
   git merge upstream/dev
   ```

4. **Create feature branch**:
   ```bash
   git checkout -b feature/my-new-feature
   # or
   git checkout -b fix/bug-description
   ```

### Development Cycle

```bash
# 1. Make changes
vim modules/local/mymodule/main.nf

# 2. Test locally
nf-test test modules/local/mymodule/tests/

# 3. Lint code
nf-core pipelines lint

# 4. Check tests
nf-test test

# 5. Commit changes
git add modules/local/mymodule/
git commit -m "feat: Add mymodule for X functionality"

# 6. Push to your fork
git push origin feature/my-new-feature

# 7. Create pull request on GitHub
```

### Pre-Commit Checklist

- [ ] Code follows nf-core guidelines
- [ ] New parameters added to `nextflow_schema.json`
- [ ] Tests pass: `nf-test test`
- [ ] Lint passes: `nf-core pipelines lint`
- [ ] Documentation updated
- [ ] CHANGELOG.md updated (if applicable)
- [ ] No TODO/FIXME comments without issues

## Adding New Modules

### Step-by-Step Guide

#### 1. Create Module Structure

**Option A: Using nf-core tools** (recommended for nf-core modules):
```bash
nf-core modules create MODULE_NAME
```

**Option B: Manual creation** (for local modules):
```bash
mkdir -p modules/local/mymodule
cd modules/local/mymodule
touch main.nf meta.yml environment.yml
mkdir tests
touch tests/main.nf.test
```

#### 2. Implement Module

**File**: `modules/local/mymodule/main.nf`

```groovy
process MYMODULE {
    tag "$meta.id"
    label 'process_low'  // or process_medium, process_high

    conda "${moduleDir}/environment.yml"
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/tool:version' :
        'quay.io/biocontainers/tool:version' }"

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
    # Validate input
    if [ ! -s ${input_file} ]; then
        echo "ERROR: Input file ${input_file} is empty or missing" >&2
        exit 1
    fi

    # Run tool
    tool \\
        --input ${input_file} \\
        --output ${prefix}.output \\
        ${args}

    # Verify output
    if [ ! -s ${prefix}.output ]; then
        echo "ERROR: Tool failed to produce output" >&2
        exit 1
    fi

    echo "[MYMODULE] Successfully processed ${meta.id}" >&2

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        tool: \$(tool --version | sed 's/^.*version //')
    END_VERSIONS
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    touch ${prefix}.output

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        tool: 1.0.0
    END_VERSIONS
    """
}
```

**Key patterns to follow**:
- Use `tag "$meta.id"` for process identification
- Always include `when:` block
- Implement input validation
- Provide error messages to stderr
- Verify outputs before completing
- Emit `versions.yml` for tracking
- Include `stub:` block for testing

#### 3. Create Meta File

**File**: `modules/local/mymodule/meta.yml`

```yaml
name: mymodule
description: Brief description of what this module does
keywords:
  - taxonomic profiling
  - benchmarking
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
        e.g. [id: 'sample1', sample_id: 'sample1', label: 'sample1_kraken2']
  - input_file:
      type: file
      description: Input file in format X
      pattern: "*.{tsv,txt}"
output:
  - meta:
      type: map
      description: Groovy Map containing sample information
  - results:
      type: file
      description: Output file in format Y
      pattern: "*.output"
  - versions:
      type: file
      description: File containing software versions
      pattern: "versions.yml"
authors:
  - "@your_github_username"
maintainers:
  - "@your_github_username"
```

#### 4. Create Conda Environment

**File**: `modules/local/mymodule/environment.yml`

```yaml
name: mymodule
channels:
  - conda-forge
  - bioconda
  - defaults
dependencies:
  - tool=1.0.0
```

**Or use Wave containers** (preferred for Python scientific stack):
```groovy
// In main.nf
conda "${moduleDir}/environment.yml"
container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
    'https://community.wave.seqera.io/library/package_name:hash' :
    'community.wave.seqera.io/library/package_name:hash' }"
```

#### 5. Write Tests

**File**: `modules/local/mymodule/tests/main.nf.test`

```groovy
nextflow_process {
    name "Test MYMODULE"
    script "../main.nf"
    process "MYMODULE"

    test("Should run successfully with valid input") {
        when {
            process {
                """
                input[0] = [
                    [id: 'test', sample_id: 'test', label: 'test_sample'],
                    file(params.test_data['taxpasta']['sample1_kraken2'], checkIfExists: true)
                ]
                """
            }
        }

        then {
            assert process.success
            assert snapshot(process.out).match()
        }
    }

    test("Should handle empty input") {
        when {
            process {
                """
                input[0] = [
                    [id: 'test_empty'],
                    file('empty.txt').text = ''
                ]
                """
            }
        }

        then {
            assert process.failed
        }
    }

    test("Stub run") {
        options "-stub"

        when {
            process {
                """
                input[0] = [
                    [id: 'test_stub'],
                    file('test.txt').text = 'content'
                ]
                """
            }
        }

        then {
            assert process.success
        }
    }
}
```

**Run tests**:
```bash
# Run module tests
nf-test test modules/local/mymodule/tests/

# Create snapshots
nf-test test modules/local/mymodule/tests/ --update-snapshot

# Run with verbose output
nf-test test modules/local/mymodule/tests/ --verbose
```

#### 6. Add Module Configuration

**File**: `conf/modules.config`

```groovy
withName: 'MYMODULE' {
    ext.args = ''
    publishDir = [
        path: { "${params.outdir}/mymodule" },
        mode: params.publish_dir_mode,
        saveAs: { filename -> filename.equals('versions.yml') ? null : filename }
    ]
}
```

**Optional parameters** in `nextflow_schema.json`:
```json
{
  "mymodule_option": {
    "type": "string",
    "default": "default_value",
    "description": "Option description",
    "help_text": "Detailed help text"
  }
}
```

#### 7. Integrate into Workflow

**File**: `workflows/taxbencher.nf`

```groovy
// Add import at top
include { MYMODULE } from '../modules/local/mymodule/main'

// Add to workflow
workflow TAXBENCHER {
    // ... existing code ...

    // Run module
    MYMODULE(ch_input)
    ch_versions = ch_versions.mix(MYMODULE.out.versions.first())
    ch_multiqc_files = ch_multiqc_files.mix(MYMODULE.out.results.map { meta, file -> file })

    // ... rest of workflow ...
}
```

#### 8. Update Documentation

**Update files**:
- `docs/output.md` - Document output files
- `docs/development/modules.md` - Add module specification
- `README.md` - Update pipeline steps if major feature
- `CHANGELOG.md` - Add entry under "Unreleased"

#### 9. Test Full Pipeline

```bash
# Test with minimal data
nextflow run . -profile test,docker

# Test with realistic data
nextflow run . -profile test_realistic,docker

# Test with resume
nextflow run . -profile test,docker -resume
```

## Writing Tests

### Test Structure

taxbencher uses **nf-test** for module and pipeline testing.

**Test types**:
1. **Functional tests**: Run module with real data
2. **Stub tests**: Verify module structure without running tool
3. **Negative tests**: Test error handling
4. **Snapshot tests**: Verify outputs match expected

### Module Test Template

```groovy
nextflow_process {
    name "Test MYMODULE"
    script "../main.nf"
    process "MYMODULE"

    tag "modules"
    tag "modules_local"
    tag "mymodule"

    test("Test 1: Basic functionality") {
        when {
            process {
                """
                input[0] = Channel.of(
                    [[id:'test1'], file('test1.txt')],
                    [[id:'test2'], file('test2.txt')]
                )
                """
            }
        }

        then {
            assert process.success
            assert snapshot(
                process.out.results,
                process.out.versions
            ).match()
        }
    }

    test("Test 2: Error handling") {
        when {
            process {
                """
                input[0] = [[id:'empty'], file('empty.txt')]
                """
            }
        }

        then {
            assert process.failed
        }
    }

    test("Test 3: Stub") {
        options "-stub"

        when {
            process {
                """
                input[0] = [[id:'stub_test'], file('stub.txt')]
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

### Snapshot Management

**Update snapshots** when outputs legitimately change:
```bash
nf-test test --update-snapshot
```

**Review snapshot changes**:
```bash
git diff tests/
```

**Snapshot files** are stored in `tests/*.nf.test.snap`:
```json
{
  "Test 1: Basic functionality": {
    "content": [
      {
        "0": [
          [
            { "id": "test1" },
            "test1.output:md5,abc123"
          ]
        ],
        "1": [
          "versions.yml:md5,def456"
        ]
      }
    ]
  }
}
```

### Test Data Management

**Location**: `assets/test_data/`

**Add test data**:
```bash
# Small files can be committed
cp new_test.tsv assets/test_data/

# Large files should be hosted externally
# Reference via URL in test configs
```

**Reference test data** in tests:
```groovy
file(params.test_data['taxpasta']['sample1_kraken2'], checkIfExists: true)
```

**Define test data** in `conf/test.config`:
```groovy
params {
    test_data = [
        'taxpasta': [
            'sample1_kraken2': "${projectDir}/assets/test_data/sample1_kraken2.tsv",
            'sample1_metaphlan': "${projectDir}/assets/test_data/sample1_metaphlan.tsv"
        ]
    ]
}
```

## Configuration Management

### Configuration Files

**`nextflow.config`** - Main configuration:
```groovy
params {
    // Input/output options
    input                      = null
    gold_standard              = null
    outdir                     = null

    // Optional parameters
    save_standardised_profiles = false

    // Boilerplate options
    publish_dir_mode           = 'copy'
    multiqc_config             = null
}

includeConfig 'conf/base.config'
includeConfig 'conf/modules.config'
```

**`conf/base.config`** - Resource labels:
```groovy
process {
    // Default resources
    cpus   = { 1 * task.attempt }
    memory = { 6.GB * task.attempt }
    time   = { 4.h * task.attempt }

    errorStrategy = { task.exitStatus in [143,137,104,134,139] ? 'retry' : 'finish' }
    maxRetries    = 1
    maxErrors     = '-1'

    // Process labels
    withLabel: process_single {
        cpus   = { 1 }
        memory = { 6.GB * task.attempt }
        time   = { 4.h * task.attempt }
    }
    withLabel: process_low {
        cpus   = { 2 * task.attempt }
        memory = { 12.GB * task.attempt }
        time   = { 4.h * task.attempt }
    }
    withLabel: process_medium {
        cpus   = { 6 * task.attempt }
        memory = { 36.GB * task.attempt }
        time   = { 8.h * task.attempt }
    }
    withLabel: process_high {
        cpus   = { 12 * task.attempt }
        memory = { 72.GB * task.attempt }
        time   = { 16.h * task.attempt }
    }
}
```

**`conf/modules.config`** - Per-module config:
```groovy
process {
    withName: 'MYMODULE' {
        ext.args = ''  // Additional CLI arguments
        ext.prefix = { "${meta.id}_custom" }  // Custom output prefix
        publishDir = [
            path: { "${params.outdir}/mymodule" },
            mode: params.publish_dir_mode,
            saveAs: { filename -> filename.equals('versions.yml') ? null : filename }
        ]
    }
}
```

### Adding New Parameters

1. **Add to `nextflow.config`**:
```groovy
params {
    new_parameter = 'default_value'
}
```

2. **Generate schema**:
```bash
nf-core pipelines schema build
```

3. **Customize in `nextflow_schema.json`**:
```json
{
  "new_parameter": {
    "type": "string",
    "default": "default_value",
    "description": "Short description",
    "help_text": "Detailed help text with examples",
    "fa_icon": "fas fa-cog"
  }
}
```

4. **Validate schema**:
```bash
nf-core pipelines schema validate
```

## Code Style and Standards

### Nextflow Style

**Naming conventions**:
```groovy
// Channels: ch_ prefix
ch_input
ch_taxpasta
ch_versions

// Processes: UPPERCASE
TAXPASTA_TO_BIOBOXES
OPAL_PER_SAMPLE

// Variables: camelCase
def sampleId = meta.sample_id
def outputFile = "${prefix}.output"
```

**Indentation**: 4 spaces (Nextflow standard)

**Comments**:
```groovy
//
// SECTION: Brief section description
//
// Detailed explanation of what this section does
// and why it's structured this way
//

// Inline comment for single line
def value = compute()  // Explain non-obvious logic
```

### Groovy Best Practices

**Safe file handling**:
```groovy
// Good: Check if file exists
def myFile = file(params.input, checkIfExists: true)

// Good: Handle null
def value = params.optional ?: 'default'

// Good: Type checking
def files = predictions instanceof List ? predictions : [predictions]
```

**String interpolation**:
```groovy
// Good: Use """ for multi-line, variables
"""
tool --input ${input_file} \\
    --output ${prefix}.out \\
    ${args}
"""

// Good: Use ''' for literal strings (no interpolation)
'''
echo "Literal text with $variable not interpolated"
'''
```

### Python Style

**Follow PEP 8** for bin/ scripts:
```python
#!/usr/bin/env python3
"""
Script description.

Author: Your Name
"""

import argparse
import sys
from pathlib import Path

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Script purpose")
    parser.add_argument('-i', '--input', required=True, help='Input file')
    parser.add_argument('-o', '--output', required=True, help='Output file')
    args = parser.parse_args()

    # Implementation
    process_file(args.input, args.output)

def process_file(input_path: str, output_path: str) -> None:
    """Process file logic."""
    # Implementation
    pass

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
```

### nf-core Compliance

**Run linting** before committing:
```bash
nf-core pipelines lint
```

**Common lint warnings** and fixes:

1. **Missing meta.yml**: Create comprehensive module metadata
2. **Container not specified**: Add container directive to all processes
3. **Missing test**: Create nf-test suite for new modules
4. **TODO comments**: Remove or create GitHub issues
5. **Outdated template**: Run `nf-core pipelines sync`

## Git Workflow

### Branch Strategy

**Main branches**:
- `main` - Stable releases only
- `dev` - Active development (target for PRs)

**Feature branches**:
```bash
# Format: type/description
git checkout -b feat/add-new-classifier-support
git checkout -b fix/opal-error-handling
git checkout -b docs/update-architecture
git checkout -b test/improve-coverage
```

### Commit Messages

**Format**: Conventional Commits

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `test`: Adding missing tests
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `perf`: Performance improvement
- `chore`: Changes to build process or auxiliary tools

**Examples**:
```bash
git commit -m "feat(modules): Add TAXPASTA_STANDARDISE module"

git commit -m "fix(opal): Handle empty prediction files gracefully

Added validation to check prediction count before running OPAL.
Now provides clear error message instead of cryptic failure.

Closes #42"

git commit -m "docs(architecture): Document tuple-embedded channel pattern"

git commit -m "test(modules): Add snapshot tests for COMPARATIVE_ANALYSIS"
```

### Keeping Fork Updated

```bash
# Fetch upstream changes
git fetch upstream

# Update dev branch
git checkout dev
git merge upstream/dev

# Update feature branch
git checkout feature/my-feature
git rebase dev

# Force push if already pushed
git push origin feature/my-feature --force-with-lease
```

## Pull Request Process

### Before Creating PR

**Checklist**:
- [ ] All tests pass locally
- [ ] Code linted successfully
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Commits follow conventional format
- [ ] Branch up to date with `dev`

### Creating Pull Request

1. **Push branch** to your fork:
```bash
git push origin feature/my-feature
```

2. **Create PR** on GitHub:
   - Target branch: `dev` (not `main`)
   - Title: Clear, descriptive (follows conventional commits)
   - Description: Use PR template

3. **PR description template**:
```markdown
## Description
Brief description of changes

## Motivation
Why is this change needed?

## Changes
- Change 1
- Change 2
- Change 3

## Testing
How was this tested?

## Checklist
- [ ] Tests pass
- [ ] Lint passes
- [ ] Documentation updated
- [ ] CHANGELOG.md updated

## Related Issues
Closes #123
```

### CI/CD Checks

**Automated checks run on PR**:
1. **nf-test**: All tests must pass
2. **Linting**: nf-core lint must pass
3. **Prettier**: Markdown formatting
4. **GitHub Actions**: Workflow syntax

**If CI fails**:
```bash
# Check logs on GitHub Actions tab
# Fix issues locally
# Push fixes (CI will re-run automatically)
git add .
git commit -m "fix(ci): Address linting issues"
git push origin feature/my-feature
```

### Code Review Process

**Review timeline**: Expect response within 1-2 weeks

**Common review comments**:
- "Please add tests for this functionality"
- "Can you update the documentation?"
- "This should follow nf-core guidelines"
- "Consider using existing pattern from module X"

**Addressing feedback**:
```bash
# Make requested changes
git add .
git commit -m "refactor: Address review comments"
git push origin feature/my-feature
```

**After approval**: Maintainers will merge PR

## Documentation Requirements

### Required Documentation

**For new modules**:
1. `meta.yml` - Complete module metadata
2. Inline comments in `main.nf`
3. Entry in `docs/development/modules.md`
4. Output description in `docs/output.md`
5. Test description in tests

**For new features**:
1. Update `README.md`
2. Update `docs/usage.md`
3. Add to `CHANGELOG.md`
4. Update `docs/development/architecture.md` if significant

**For bug fixes**:
1. Add to `CHANGELOG.md`
2. Update troubleshooting docs if relevant
3. Add test to prevent regression

### Documentation Standards

**Markdown formatting**:
- Use headers hierarchically (##, ###, ####)
- Code blocks with language specification
- Tables for structured data
- Links to related documentation

**Code documentation**:
```groovy
//
// MODULE: Brief module description
// Purpose and context for this step in the workflow
//
MYMODULE(ch_input)

// Extract specific output for downstream processing
ch_results = MYMODULE.out.results
    .map { meta, file ->
        // Explain non-obvious transformation
        [meta.sample_id, file]
    }
```

## Troubleshooting Development Issues

### Common Issues

#### Issue: Tests fail locally but examples work
```bash
# Solution: Check test data paths
nf-test test --verbose

# Verify test data exists
ls assets/test_data/

# Check params.test_data definition in conf/test.config
```

#### Issue: Module not found
```bash
# Solution: Check include statement
# workflows/taxbencher.nf
include { MYMODULE } from '../modules/local/mymodule/main'

# Verify file exists
ls modules/local/mymodule/main.nf
```

#### Issue: Lint fails with "TODO comment"
```bash
# Solution: Remove TODOs or create GitHub issues
grep -r "TODO" modules/ workflows/

# Create issue for each TODO
# Replace TODO with issue link or remove
```

#### Issue: Container not found
```bash
# Solution: Check container exists on quay.io/biocontainers
# Or use Wave for custom dependencies

# Search biocontainers
curl -s "https://api.biocontainers.pro/ga4gh/trs/v2/tools/tool_name/versions"

# Or specify Wave container
container "community.wave.seqera.io/library/package:hash"
```

#### Issue: Tests pass but real data fails
```bash
# Solution: Test with larger dataset
nextflow run . -profile test_realistic,docker

# Enable debug output
nextflow run . -profile test,docker -with-trace -with-report

# Check work directory
ls work/*/*
cat work/*/.command.log
```

#### Issue: nf-test snapshot mismatch
```bash
# Solution: Review differences
nf-test test --verbose

# If changes are expected, update snapshot
nf-test test --update-snapshot

# Review snapshot changes before committing
git diff tests/
```

### Debugging Workflows

**Enable debug mode**:
```bash
nextflow run . -profile test,docker -with-trace -with-report -with-timeline
```

**Check process outputs**:
```bash
# Work directory structure
ls work/
ls work/ab/cd1234*/

# Process logs
cat work/ab/cd1234*/.command.log
cat work/ab/cd1234*/.command.err
```

**Use `.view()` for channel debugging**:
```groovy
ch_input
    .view { "DEBUG: $it" }
    .map { ... }
```

### Getting Help

**Resources**:
1. **GitHub Issues**: https://github.com/FOI-Bioinformatics/taxbencher/issues
2. **nf-core Slack**: https://nf-co.re/join/slack
3. **Nextflow Slack**: https://www.nextflow.io/slack-invite.html
4. **Documentation**: https://nf-co.re/docs/

**When asking for help**:
- Provide error logs
- Share `.nextflow.log`
- Include command used
- Mention Nextflow version
- Describe expected vs actual behavior

## See Also

- [Architecture](architecture.md) - Pipeline architecture and design decisions
- [Modules](modules.md) - Module specifications and implementation details
- [Workflow Patterns](workflow-patterns.md) - Channel operations and patterns
- [Testing](testing.md) - Testing framework and coverage
- [Code Quality](code-quality.md) - Best practices and quality standards
- [.github/CONTRIBUTING.md](../../.github/CONTRIBUTING.md) - Official contribution guidelines

## References

- [nf-core Guidelines](https://nf-co.re/docs/contributing/guidelines)
- [Nextflow Documentation](https://www.nextflow.io/docs/latest/)
- [nf-test Documentation](https://www.nf-test.com/)
- [Conventional Commits](https://www.conventionalcommits.org/)
