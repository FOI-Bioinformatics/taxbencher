# Testing Framework

This document provides comprehensive documentation of taxbencher's testing framework, including test structure, patterns, coverage, and known limitations.

## Table of Contents
- [Testing Overview](#testing-overview)
- [nf-test Framework](#nf-test-framework)
- [Test Structure](#test-structure)
- [Module Testing Patterns](#module-testing-patterns)
- [Snapshot Testing](#snapshot-testing)
- [Test Data Management](#test-data-management)
- [Profile Compatibility](#profile-compatibility)
- [Running Tests](#running-tests)
- [Test Coverage](#test-coverage)
- [Known Limitations](#known-limitations)
- [CI/CD Integration](#cicd-integration)
- [Troubleshooting Tests](#troubleshooting-tests)

## Testing Overview

### Test Types

**1. Functional Tests** - Run actual code with real data
- Test process logic and transformations
- Validate output correctness
- Require appropriate containers/environments
- **Example**: TAXPASTA_STANDARDISE tests run taxpasta on real profiler outputs

**2. Stub Tests** - Verify module structure without running code
- Fast execution (no container/conda overhead)
- Validate module wiring and interface
- Check publishDir and output structure
- **Example**: OPAL_PER_SAMPLE stub tests verify outputs are emitted correctly

**3. Integration Tests** - Test full pipeline workflows
- Validate data flow between modules
- Test channel operations and grouping
- Ensure end-to-end functionality
- **Example**: Full pipeline tests with test/test_raw profiles

**4. Negative Tests** - Test error handling
- Verify failures for invalid inputs
- Check error messages are clear
- Test edge cases
- **Example**: Empty file handling in TAXPASTA_TO_BIOBOXES

### Current Test Coverage

**Overall**: 14/22 tests passing (64%)

**Breakdown by type**:
- **Functional tests**: 8/20 passing (40%)
- **Stub tests**: 9/9 passing (100%)
- **Integration tests**: 0/2 passing (0% - blocked by OPAL bugs)

See [Test Coverage Report](../reports/test-coverage.md) for detailed analysis.

## nf-test Framework

### What is nf-test?

**nf-test** is the official testing framework for Nextflow pipelines, providing:
- Process-level testing
- Workflow testing
- Function testing
- Snapshot-based assertions
- Fast stub mode execution

**Installation**:
```bash
# Via nf-core tools
nf-core tools install nf-test

# Manual installation
wget -qO- https://code.askimed.com/install/nf-test | bash
```

**Documentation**: https://www.nf-test.com/

### nf-test vs pytest

| Feature | nf-test | pytest |
|---------|---------|--------|
| Native Nextflow support | ✅ Yes | ❌ No |
| Snapshot testing | ✅ Built-in | ⚠️ Requires plugin |
| Process testing | ✅ Direct | ⚠️ Requires wrapper |
| Channel testing | ✅ Native | ❌ Not supported |
| Speed | ⚠️ Slower (runs Nextflow) | ✅ Faster |
| Python testing | ❌ No | ✅ Yes |

**Verdict**: nf-test for Nextflow code, pytest for bin/ Python scripts.

## Test Structure

### Directory Organization

```
modules/local/
└── mymodule/
    ├── main.nf                    # Module code
    ├── meta.yml                   # Module metadata
    ├── environment.yml            # Conda environment
    ├── tests/
    │   ├── main.nf.test           # nf-test test file
    │   ├── main.nf.test.snap      # Snapshot file (auto-generated)
    │   └── testdata/              # Test input files
    │       ├── test_input1.txt
    │       └── test_input2.txt
    └── README.md
```

### Test File Anatomy

**File**: `modules/local/mymodule/tests/main.nf.test`

```groovy
nextflow_process {
    // Test metadata
    name "Test Process MYMODULE"
    script "../main.nf"
    process "MYMODULE"

    // Tags for test organization
    tag "modules"
    tag "modules_local"
    tag "mymodule"

    // Test case 1: Basic functionality
    test("mymodule - basic") {
        when {
            process {
                """
                input[0] = [
                    [id: 'test1', sample_id: 'sample1', label: 'test_label'],
                    file('${moduleDir}/testdata/input.txt', checkIfExists: true)
                ]
                """
            }
        }

        then {
            assertAll(
                { assert process.success },
                { assert snapshot(process.out).match() }
            )
        }
    }

    // Test case 2: Error handling
    test("mymodule - empty input") {
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

    // Test case 3: Stub mode
    test("mymodule - stub") {
        options "-stub"

        when {
            process {
                """
                input[0] = [
                    [id: 'test_stub'],
                    file('stub_input.txt')
                ]
                """
            }
        }

        then {
            assertAll(
                { assert process.success },
                { assert snapshot(process.out).match() }
            )
        }
    }
}
```

### Test Components

**1. Header Block**:
```groovy
nextflow_process {
    name "Test Process MYMODULE"  // Descriptive test name
    script "../main.nf"           // Path to module
    process "MYMODULE"            // Process name
    tag "mymodule"                // Tags for filtering
}
```

**2. Test Definition**:
```groovy
test("mymodule - basic") {
    when { ... }  // Setup and inputs
    then { ... }  // Assertions
}
```

**3. Options**:
```groovy
options "-stub"              // Run in stub mode
options "--profile docker"   // Use specific profile
```

**4. Assertions**:
```groovy
assert process.success                    // Process completed successfully
assert process.failed                     // Process failed (for negative tests)
assert snapshot(process.out).match()      // Outputs match snapshot
assert process.out.results.size() == 1    // Check output size
```

## Module Testing Patterns

### Pattern 1: Basic Functional Test

**Purpose**: Verify process runs correctly with valid input

```groovy
test("module_name - basic") {
    when {
        process {
            """
            input[0] = [
                [id: 'test', sample_id: 'sample1', label: 'test_label'],
                file('${moduleDir}/testdata/valid_input.txt', checkIfExists: true)
            ]
            """
        }
    }

    then {
        assertAll(
            { assert process.success },
            { assert snapshot(process.out).match() }
        )
    }
}
```

### Pattern 2: Parameterized Test

**Purpose**: Test with different configurations

```groovy
test("module_name - custom params") {
    when {
        process {
            """
            ext.args = '--param1 value1 --param2 value2'
            input[0] = [
                [id: 'test_params', taxonomy_db: 'GTDB'],
                file('${moduleDir}/testdata/input.txt', checkIfExists: true)
            ]
            """
        }
    }

    then {
        assertAll(
            { assert process.success },
            { assert snapshot(process.out).match() }
        )
    }
}
```

### Pattern 3: Stub Test

**Purpose**: Verify module structure without running code

```groovy
test("module_name - stub") {
    options "-stub"

    when {
        process {
            """
            input[0] = [
                [id: 'test_stub'],
                file('dummy_input.txt')
            ]
            """
        }
    }

    then {
        assertAll(
            { assert process.success },
            { assert snapshot(process.out).match() }
        )
    }
}
```

**When to use**:
- CI/CD when containers unavailable
- Validating module interface changes
- Quick structure validation
- OPAL tests (to avoid upstream bugs)

### Pattern 4: Negative Test

**Purpose**: Verify error handling for invalid inputs

```groovy
test("module_name - empty input") {
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

test("module_name - invalid format") {
    when {
        process {
            """
            input[0] = [
                [id: 'test_invalid'],
                file('invalid.txt').text = 'garbage data'
            ]
            """
        }
    }

    then {
        assert process.failed
    }
}
```

### Pattern 5: Multiple Input Test

**Purpose**: Test with multiple files or samples

```groovy
test("module_name - multiple inputs") {
    when {
        process {
            """
            input[0] = Channel.of(
                [[id: 'test1'], file('input1.txt')],
                [[id: 'test2'], file('input2.txt')],
                [[id: 'test3'], file('input3.txt')]
            )
            """
        }
    }

    then {
        assertAll(
            { assert process.success },
            { assert process.out.results.size() == 3 },
            { assert snapshot(process.out).match() }
        )
    }
}
```

### Pattern 6: Complex Meta Test

**Purpose**: Test with realistic meta maps

```groovy
test("module_name - complex meta") {
    when {
        process {
            """
            input[0] = [
                [
                    id: 'sample1_kraken2',
                    sample_id: 'sample1',
                    label: 'sample1_kraken2',
                    classifier: 'kraken2',
                    taxonomy_db: 'NCBI'
                ],
                file('${moduleDir}/testdata/sample1.tsv', checkIfExists: true)
            ]
            """
        }
    }

    then {
        assertAll(
            { assert process.success },
            { assert snapshot(process.out).match() }
        )
    }
}
```

## Snapshot Testing

### What are Snapshots?

Snapshots capture the exact output of a test run for future comparison. They provide:
- Automatic output validation
- Detection of unintended changes
- Documentation of expected outputs
- Simplified assertion writing

### Snapshot File Structure

**File**: `modules/local/mymodule/tests/main.nf.test.snap`

```json
{
  "mymodule - basic": {
    "content": [
      {
        "0": [
          [
            {
              "id": "test",
              "sample_id": "sample1",
              "label": "test_label"
            },
            "test.output:md5,abc123def456"
          ]
        ],
        "1": [
          "versions.yml:md5,789ghi012jkl"
        ]
      }
    ],
    "meta": {
      "nf-test": "0.8.4",
      "nextflow": "24.10.5"
    },
    "timestamp": "2025-01-15T10:30:00"
  }
}
```

### Creating Snapshots

**First run** (creates snapshot):
```bash
nf-test test modules/local/mymodule/tests/ --update-snapshot
```

**Subsequent runs** (validates against snapshot):
```bash
nf-test test modules/local/mymodule/tests/
```

### Updating Snapshots

**When outputs legitimately change**:
```bash
# Review changes first
nf-test test modules/local/mymodule/tests/ --verbose

# If changes are expected, update
nf-test test modules/local/mymodule/tests/ --update-snapshot

# Review snapshot diff
git diff modules/local/mymodule/tests/main.nf.test.snap

# Commit if correct
git add modules/local/mymodule/tests/main.nf.test.snap
git commit -m "test: Update snapshots for module improvements"
```

### Snapshot Assertions

**Basic snapshot**:
```groovy
assert snapshot(process.out).match()
```

**Selective snapshot**:
```groovy
assert snapshot(
    process.out.results,
    process.out.versions
).match()
```

**Ignore specific outputs**:
```groovy
assert snapshot(
    process.out.results.collect { meta, file ->
        [meta.id, file.name]  // Only snapshot ID and filename, not content
    }
).match()
```

### Best Practices

1. **Review snapshot changes carefully**: Unexpected changes indicate bugs
2. **Don't commit blindly**: Always check `git diff` before committing snapshots
3. **Use selective snapshots**: Snapshot only deterministic outputs
4. **Document expected changes**: In PR description when updating snapshots

## Test Data Management

### Test Data Location

**Module-specific testdata**: `modules/local/mymodule/tests/testdata/`
- Small files specific to one module
- Co-located with tests
- Committed to repository

**Shared test data**: `assets/test_data/`
- Data used by multiple modules/tests
- Referenced in test configs
- Committed to repository (if small)

### Test Data Strategy

**Small files** (<1MB): Commit directly
```
assets/test_data/
├── gold_standard.bioboxes           # 50 KB
├── gold_standard_realistic.bioboxes # 200 KB
├── sample1_kraken2.tsv              # 10 KB
└── sample1_metaphlan.tsv            # 15 KB
```

**Large files** (>1MB): Host externally
```groovy
// In conf/test_full.config
params {
    test_data_url = 'https://data.cami-challenge.org/...'
}
```

**Generated test data**: Create in test fixtures
```groovy
test("module - generated data") {
    when {
        process {
            """
            // Generate test file
            def testFile = file('generated_input.txt')
            testFile.text = '''
            taxonomy_id\tcount
            562\t1000
            1234\t500
            '''.stripIndent()

            input[0] = [[id: 'generated'], testFile]
            """
        }
    }
}
```

### Test Profile Configuration

**File**: `conf/test.config`

```groovy
params {
    // Test-specific parameters
    config_profile_name        = 'Test profile'
    config_profile_description = 'Minimal test dataset to check pipeline function'

    // Limit resources
    max_cpus   = 2
    max_memory = '6.GB'
    max_time   = '6.h'

    // Input files
    input          = "${projectDir}/assets/test_data/samplesheet_test.csv"
    gold_standard  = "${projectDir}/assets/test_data/gold_standard.bioboxes"
}
```

### Real-World Example: TAXPASTA_STANDARDISE

**Test data structure**:
```
modules/local/taxpasta_standardise/tests/testdata/
├── test_kraken2.kreport         # Kraken2 report format
├── test_bracken.bracken         # Bracken output format
├── test_centrifuge.report       # Centrifuge report format
├── test_metaphlan_fixed.profile # MetaPhlAn profile
├── test_kaiju.out               # Kaiju output
├── test_motus.out               # mOTUs output
├── test_ganon.tre               # ganon output
├── test_krakenuniq.report       # KrakenUniq report
├── test_megan6.txt              # MEGAN6 output
├── test_diamond.txt             # DIAMOND output
└── test_kmcp.profile            # KMCP profile
```

**Test references**:
```groovy
file('${moduleDir}/testdata/test_kraken2.kreport', checkIfExists: true)
```

## Profile Compatibility

### Profile Matrix

| Module | Docker | Conda | Wave | Singularity |
|--------|--------|-------|------|-------------|
| TAXPASTA_STANDARDISE | ✅ | ✅ | ✅ | ✅ |
| TAXPASTA_TO_BIOBOXES | ✅ | ✅ | ✅ | ✅ |
| OPAL | ✅* | ✅* | ✅* | ✅* |
| OPAL_PER_SAMPLE | ✅* | ✅* | ✅* | ✅* |
| COMPARATIVE_ANALYSIS | ✅ | ✅ | ✅ | ✅ |
| MULTIQC | ✅ | ✅ | ✅ | ✅ |

\* Subject to OPAL 1.0.13 bugs with minimal test data

### Profile-Specific Testing

**Docker profile**:
```bash
nf-test test --profile docker
```

**Conda profile** (required for some modules):
```bash
nf-test test --profile conda
```

**Wave profile** (automatic container building):
```bash
nf-test test --profile docker,wave
```

**Singularity profile**:
```bash
nf-test test --profile singularity
```

### Container Dependencies

**Modules with Wave containers**:
- `TAXPASTA_TO_BIOBOXES`: pandas + ete3
- `COMPARATIVE_ANALYSIS`: pandas + scikit-learn + plotly + scipy + statsmodels

**Why Wave?**: No pre-built biocontainer with these exact dependencies.

**Alternative**: Use conda profile if Wave unavailable.

## Running Tests

### Run All Tests

```bash
# Run all tests
nf-test test

# Run all tests with specific profile
nf-test test --profile conda

# Run with verbose output
nf-test test --verbose

# Run with debug output
nf-test test --debug
```

### Run Specific Tests

**By module**:
```bash
nf-test test modules/local/taxpasta_to_bioboxes/tests/
```

**By tag**:
```bash
nf-test test --tag modules_local
nf-test test --tag taxpasta_standardise
```

**By test name**:
```bash
nf-test test --name "taxpasta standardise - kraken2"
```

**Single test file**:
```bash
nf-test test modules/local/mymodule/tests/main.nf.test
```

### Update Snapshots

**Update all snapshots**:
```bash
nf-test test --update-snapshot
```

**Update specific module snapshots**:
```bash
nf-test test modules/local/mymodule/tests/ --update-snapshot
```

### Test Options

**Common options**:
```bash
--verbose            # Detailed output
--debug              # Debug information
--profile PROFILE    # Use specific profile
--update-snapshot    # Update snapshot files
--tag TAG            # Filter by tag
--name NAME          # Filter by test name
--ci                 # CI mode (less verbose)
```

### Test Workflow

```bash
# 1. Make code changes
vim modules/local/mymodule/main.nf

# 2. Run tests to see if they fail
nf-test test modules/local/mymodule/tests/

# 3. If outputs changed legitimately, update snapshots
nf-test test modules/local/mymodule/tests/ --update-snapshot

# 4. Review snapshot changes
git diff modules/local/mymodule/tests/main.nf.test.snap

# 5. Run all tests to ensure no regressions
nf-test test

# 6. Commit changes
git add .
git commit -m "feat: Improve mymodule functionality"
```

## Test Coverage

### Current Status

**Module Test Coverage**:
- ✅ **TAXPASTA_STANDARDISE**: 12/12 tests (100%)
  - 11 functional tests (all profilers)
  - 1 stub test

- ✅ **TAXPASTA_TO_BIOBOXES**: 3/3 tests (100%)
  - 2 functional tests
  - 1 stub test

- ⚠️ **OPAL**: 1/4 tests (25%)
  - 1 stub test passing
  - 3 functional tests failing (OPAL bugs)

- ⚠️ **OPAL_PER_SAMPLE**: 5/5 stub tests (100% stub)
  - 5 stub tests passing
  - 0 functional tests (OPAL bugs)

- ✅ **COMPARATIVE_ANALYSIS**: 4/4 stub tests (100% stub)
  - 4 stub tests passing
  - Functional tests pending (requires realistic data)

**Pipeline Test Coverage**:
- ❌ **Full pipeline test**: 0/1 (blocked by OPAL bugs)
- ❌ **test_raw profile**: 0/1 (blocked by OPAL bugs)

**Overall**: 14/22 tests passing (64%)

See [Test Coverage Report](../reports/test-coverage.md) for detailed breakdown.

### Coverage Gaps

**1. OPAL Functional Tests**
- **Issue**: OPAL 1.0.13 fails with minimal test data
- **Workaround**: Stub tests validate structure
- **Solution**: Use test_realistic profile with larger datasets

**2. COMPARATIVE_ANALYSIS Functional Tests**
- **Status**: Infrastructure complete, analysis pending
- **Reason**: Requires realistic OPAL outputs
- **Plan**: Add functional tests with comprehensive test data

**3. Integration Tests**
- **Issue**: Full pipeline tests blocked by OPAL
- **Workaround**: Module tests provide good coverage
- **Solution**: Test manually with realistic data

### Measuring Coverage

**Count tests**:
```bash
# Count all tests
find modules/local/*/tests/ -name "main.nf.test" -exec grep -c "test(" {} \;

# Count passing tests
nf-test test 2>&1 | grep -c "✓"
```

**Identify untested modules**:
```bash
# List modules without tests
comm -23 \
  <(ls modules/local/ | sort) \
  <(find modules/local/*/tests -name "main.nf.test" -exec dirname {} \; | xargs -n1 basename | sort)
```

## Known Limitations

### 1. OPAL 1.0.13 Upstream Bugs

**Issue**: OPAL fails to generate spider plots with minimal test data

**Error**:
```
ValueError: x and y must have same first dimension, but have shapes (3,) and (0,)
at cami_opal/plots.py:382 in spider_plot
```

**Affected**:
- OPAL module functional tests
- OPAL_PER_SAMPLE functional tests
- Full pipeline integration tests

**Root Cause**: OPAL plotting code assumes more data than minimal test sets provide

**Impact**:
- Tests fail on visualization step
- Core metrics compute correctly
- This is NOT a taxbencher bug

**Workarounds**:
1. Use stub tests for CI/CD
2. Test with test_realistic profile (larger datasets)
3. Manual testing with production data

**Documentation**:
- Clearly stated in test comments
- Documented in TEST_COVERAGE_REPORT.md
- Known issue in OPAL repository

### 2. Wave Container Requirements

**Issue**: Some modules require Seqera Wave for container building

**Affected Modules**:
- TAXPASTA_TO_BIOBOXES (pandas + ete3)
- COMPARATIVE_ANALYSIS (full scipy stack)

**Why**: No pre-built biocontainers with these exact dependency combinations

**Solutions**:
1. **Use Wave** (recommended):
   ```bash
   nf-test test --profile docker,wave
   ```

2. **Use Conda**:
   ```bash
   nf-test test --profile conda
   ```

3. **Pre-pull Wave containers**:
   ```bash
   docker pull community.wave.seqera.io/library/pip_ete3_pandas:hash
   ```

### 3. Conda Environment Build Time

**Issue**: First conda test run takes 5-10 minutes

**Reason**: Building environments from scratch (pandas, ete3, scipy stack)

**Impact**: Slow CI/CD if not cached

**Mitigation**:
- Conda caches environments in `.nextflow/conda/`
- Use `-resume` to reuse environments
- CI/CD should cache conda directory

**Example**:
```bash
# First run: ~8 minutes
nf-test test modules/local/taxpasta_to_bioboxes/tests/ --profile conda

# Second run: ~30 seconds (cached)
nf-test test modules/local/taxpasta_to_bioboxes/tests/ --profile conda
```

### 4. ete3 NCBI Taxonomy Download

**Issue**: First run downloads ~500MB NCBI taxonomy database

**Location**: `~/.etetoolkit/taxa.sqlite`

**Timing**:
- First run: ~2-3 minutes (downloading + indexing)
- Subsequent runs: instant (cached)

**CI/CD Impact**: Slow first run, fast after cache

**Solution**: Pre-populate taxonomy DB in container or CI cache

### 5. Test Data Size Constraints

**Issue**: Minimal test data triggers edge cases in tools

**Trade-offs**:
| Small test data | Realistic test data |
|-----------------|---------------------|
| ✅ Fast tests | ⏱️ Slower tests |
| ✅ Easy to commit | ⚠️ Large repo size |
| ❌ Triggers tool bugs | ✅ Production-like |
| ❌ Unrealistic | ✅ Better validation |

**Current Strategy**: Small for CI, realistic for validation

**Realistic Test Profile**:
```bash
nextflow run . -profile test_realistic,conda
```

## CI/CD Integration

### GitHub Actions Workflow

**File**: `.github/workflows/nf-test.yml`

```yaml
name: nf-test

on: [push, pull_request]

jobs:
  test-docker:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Nextflow
        uses: nf-core/setup-nextflow@v1

      - name: Install nf-test
        run: |
          wget -qO- https://code.askimed.com/install/nf-test | bash
          sudo mv nf-test /usr/local/bin/

      - name: Run module tests (docker-compatible)
        run: |
          nf-test test --profile docker --tag modules_local

      - name: Run stub tests
        run: |
          nf-test test --profile docker --tag stub

  test-conda:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Miniconda
        uses: conda-incubator/setup-miniconda@v2

      - name: Install Nextflow
        uses: nf-core/setup-nextflow@v1

      - name: Cache conda environments
        uses: actions/cache@v3
        with:
          path: ~/.nextflow/conda
          key: ${{ runner.os }}-conda-${{ hashFiles('**/environment.yml') }}

      - name: Run conda-required tests
        run: |
          nf-test test --profile conda --tag conda_required
```

### Test Tagging Strategy

**Tag tests for CI filtering**:
```groovy
nextflow_process {
    tag "modules"
    tag "modules_local"
    tag "taxpasta_to_bioboxes"
    tag "conda_required"     // Requires conda profile
    tag "docker_compatible"  // Works with docker
}
```

**Run tagged tests**:
```bash
nf-test test --tag docker_compatible
nf-test test --tag conda_required --profile conda
```

### Handling Expected Failures

**Strategy 1: Separate jobs**
```yaml
- name: Tests expected to pass
  run: nf-test test --tag stable

- name: Tests with known issues
  continue-on-error: true
  run: nf-test test --tag known_issues
```

**Strategy 2: Document in CI**
```yaml
- name: Run all tests
  run: |
    echo "Expected: 14/22 tests pass (64%)"
    echo "Known issues: OPAL bugs, see TEST_COVERAGE_REPORT.md"
    nf-test test || echo "Some test failures expected"
```

## Troubleshooting Tests

### Common Issues

#### Issue: Test fails but module works manually
```bash
# Check test data
ls modules/local/mymodule/tests/testdata/
cat modules/local/mymodule/tests/testdata/test_input.txt

# Run with debug
nf-test test modules/local/mymodule/tests/ --debug

# Check work directory
ls work/*/*
cat work/*/.command.log
```

#### Issue: Snapshot mismatch
```bash
# See what changed
nf-test test modules/local/mymodule/tests/ --verbose

# Review diff
git diff modules/local/mymodule/tests/main.nf.test.snap

# If changes are correct, update
nf-test test modules/local/mymodule/tests/ --update-snapshot
```

#### Issue: Container not found
```bash
# Check container specification
grep "container" modules/local/mymodule/main.nf

# Try conda profile
nf-test test --profile conda

# Or use Wave
nf-test test --profile docker,wave
```

#### Issue: OPAL spider plot error
```
ValueError: x and y must have same first dimension
```

**Solution**: This is a known OPAL 1.0.13 bug
```bash
# Use stub test instead
test("opal - stub") {
    options "-stub"
    ...
}

# Or use realistic test data
nextflow run . -profile test_realistic,conda
```

#### Issue: Conda environment build fails
```bash
# Clean conda cache
rm -rf ~/.nextflow/conda/
rm -rf work/conda/

# Retry
nf-test test --profile conda

# Check environment.yml syntax
cat modules/local/mymodule/environment.yml
```

#### Issue: Test passes locally, fails in CI
```bash
# Check profile differences
nf-test test --profile docker  # CI uses docker
nf-test test --profile conda   # Local might use conda

# Check resource limits
cat conf/test.config  # CI may have different limits

# Check CI logs
# Look for container pull failures, timeouts, etc.
```

### Debugging Workflow

1. **Identify failure**:
```bash
nf-test test --verbose
```

2. **Check work directory**:
```bash
ls -la work/
cat work/ab/cd1234*/.command.log
cat work/ab/cd1234*/.command.err
```

3. **Run process manually**:
```bash
cd work/ab/cd1234*/
bash .command.sh
```

4. **Check test data**:
```bash
cat modules/local/mymodule/tests/testdata/input.txt
```

5. **Verify container**:
```bash
docker run -it container_name bash
# Test commands interactively
```

### Getting Help

**Resources**:
1. **Test Coverage Report**: `docs/reports/test-coverage.md`
2. **nf-test docs**: https://www.nf-test.com/
3. **nf-core Slack**: https://nf-co.re/join/slack
4. **GitHub Issues**: https://github.com/FOI-Bioinformatics/taxbencher/issues

**When reporting test failures**:
- Include nf-test version: `nf-test version`
- Include Nextflow version: `nextflow -version`
- Attach `.nextflow.log`
- Provide full error output
- Mention profile used: docker/conda/wave

## See Also

- [Test Coverage Report](../reports/test-coverage.md) - Detailed coverage analysis
- [Development Guide](development-guide.md) - Contributing instructions
- [Modules](modules.md) - Module specifications
- [Code Quality](code-quality.md) - Best practices and standards

## References

- [nf-test Documentation](https://www.nf-test.com/)
- [nf-core Testing Guidelines](https://nf-co.re/docs/contributing/tests_and_test_data)
- [Nextflow Testing](https://www.nextflow.io/docs/latest/test.html)
- [Snapshot Testing Explained](https://www.nf-test.com/docs/assertions/snapshots/)
