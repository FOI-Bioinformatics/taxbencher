# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Subagent
**Active Subagent**: `bioinformatics-pipeline-dev`

## Overview

**taxbencher** is an nf-core compliant Nextflow pipeline for benchmarking taxonomic classifiers. It evaluates classifier predictions against ground truth using CAMI OPAL metrics.

**Key characteristics:**
- Nextflow DSL2 workflow (≥24.10.5)
- nf-core template v3.4.1 compliance
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

# Run with real data
nextflow run . \
  --input samplesheet.csv \
  --gold_standard gold_standard.bioboxes \
  --outdir results \
  -profile docker
```

## Technical Stack
- **Workflow Language**: Nextflow DSL2
- **Framework**: nf-core template v3.4.1
- **Testing**: nf-test
- **Containers**: Docker/Singularity/Conda
- **Languages**: Python for utility scripts

## Documentation

### For Users
- **[Usage Guide](docs/usage.md)** - How to run the pipeline
- **[Input Formats](docs/raw-inputs.md)** - Supported profiler outputs and samplesheet format
- **[Output Documentation](docs/output.md)** - Understanding pipeline results
- **[Troubleshooting](docs/troubleshooting.md)** - Common issues and solutions
- **[Gold Standard Troubleshooting](docs/troubleshooting-gold-standard.md)** - Fixing gold standard validation issues

### For Developers
- **[Development Hub](docs/development/README.md)** - Complete developer documentation
- **[Architecture](docs/development/architecture.md)** - Pipeline structure and design
- **[Modules](docs/development/modules.md)** - Module specifications
- **[Workflow Patterns](docs/development/workflow-patterns.md)** - Channel operations and patterns
- **[Development Guide](docs/development/development-guide.md)** - Contributing guide
- **[Testing](docs/development/testing.md)** - Test framework and coverage
- **[Code Quality](docs/development/code-quality.md)** - Best practices and patterns

### Reports
- **[Code Quality Report](docs/reports/code-quality.md)** - Latest quality assessment (Grade: A-)
- **[Test Coverage Report](docs/reports/test-coverage.md)** - Detailed test analysis
- **[Validation Report](docs/reports/validation.md)** - Validation infrastructure

## Architecture Overview

### Pipeline Flow
```
Input → TAXPASTA_STANDARDISE* → TAXPASTA_TO_BIOBOXES →
Group by sample_id → OPAL_PER_SAMPLE → COMPARATIVE_ANALYSIS → MULTIQC
```
*Auto-triggered for raw profiler outputs

### Key Concepts

**Per-Sample Evaluation**: The pipeline groups profiles by `sample_id` for fair classifier comparison. Each biological sample gets:
- One OPAL run comparing all its classifiers
- One comparative analysis report
- Per-sample metrics and visualizations

**Automatic Format Detection**: Files are automatically routed based on extension:
- `.tsv`, `.txt` → Already standardized, use directly
- `.kreport`, `.profile`, `.out`, etc. → Standardize with taxpasta

### Directory Structure
```
.
├── workflows/taxbencher.nf       # Main workflow
├── modules/local/                # Custom modules
├── bin/                          # Python scripts
├── conf/                         # Configuration
├── assets/test_data/             # Test datasets
└── docs/                         # Documentation
```

See [docs/development/architecture.md](docs/development/architecture.md) for detailed architecture documentation.

## Key Modules

### TAXPASTA_STANDARDISE
**Purpose**: Converts raw profiler outputs to taxpasta TSV format
**When**: Automatically for non-.tsv/.txt inputs
**Supports**: Kraken2, MetaPhlAn, Centrifuge, Kaiju, Bracken, ganon, KMCP, mOTUs, DIAMOND, MALT

### TAXPASTA_TO_BIOBOXES
**Purpose**: Converts taxpasta TSV to CAMI Bioboxes format
**Uses**: Python + ete3 for taxonomy lookups
**Container**: Seqera Wave (pandas + ete3)

### OPAL_PER_SAMPLE
**Purpose**: CAMI OPAL evaluation per biological sample
**Innovation**: Tuple-embedded channel pattern for per-sample multi-classifier evaluation
**Output**: HTML reports, metrics TSV, confusion matrices

### COMPARATIVE_ANALYSIS
**Purpose**: Statistical comparison of classifiers per sample
**Status**: Infrastructure complete, analysis features planned (PCA, differential taxa)
**Future**: Interactive visualizations, statistical testing

See [docs/development/modules.md](docs/development/modules.md) for complete module documentation.

## Development Workflow

### Before Committing
```bash
# 1. Lint the pipeline
nf-core pipelines lint

# 2. Run tests
nf-test test

# 3. Check for issues
grep -r "TODO\|FIXME" modules/ workflows/
```

### Adding a Module
```bash
# 1. Create structure
nf-core modules create MODULE_NAME

# 2. Implement following existing patterns
# 3. Write nf-test tests
# 4. Add to conf/modules.config
# 5. Integrate into workflow
```

See [docs/development/development-guide.md](docs/development/development-guide.md) for detailed instructions.

## Testing

### Test Profiles
- `test` - Minimal dataset (may trigger OPAL bugs)
- `test_raw` - Raw profiler outputs
- `test_realistic` - Larger dataset (recommended for validation)

### Running Tests
```bash
# Module tests
nf-test test modules/local/MODULE_NAME/tests/

# Full pipeline
nextflow run . -profile test_realistic,docker

# Update snapshots
nf-test test --update-snapshot
```

See [docs/development/testing.md](docs/development/testing.md) and [docs/reports/test-coverage.md](docs/reports/test-coverage.md) for details.

## Validation Infrastructure

### Pre-Flight Validation
```bash
# Validate taxpasta files
python3 bin/validate_taxpasta.py input.tsv

# Validate gold standard (CRITICAL)
python3 bin/validate_bioboxes.py gold_standard.bioboxes

# Auto-fix gold standard if needed
python3 bin/fix_gold_standard.py \
  -i gold_standard.bioboxes \
  -o gold_standard_fixed.bioboxes \
  -s sample_id
```

See [docs/reports/validation.md](docs/reports/validation.md) for complete validation workflow.

## Code Quality

**Status**: Production-ready with excellent nf-core compliance

**Latest Assessment** (2025-11-04):
- ✅ 205/205 nf-core lint tests passed
- ✅ 0 failures
- ⚠️ 5 minor warnings (all addressed)
- **Grade: A-**

**Innovative Patterns**:
1. **Tuple-Embedded Channels** - Solves Nextflow cardinality matching for per-sample evaluation
2. **Automatic Format Detection** - Branch-based routing by file extension
3. **Per-Sample Grouping** - groupTuple() for fair classifier comparison

See [docs/reports/code-quality.md](docs/reports/code-quality.md) for full analysis and [docs/development/code-quality.md](docs/development/code-quality.md) for best practices.

## Known Limitations

1. **OPAL 1.0.13 Spider Plot Bug**
   - Issue: Fails with minimal test data (<100 taxa)
   - Workaround: Use realistic datasets
   - Status: Upstream bug, documented

2. **Wave Container Dependencies**
   - Issue: Some modules use Seqera Wave for dynamic container building
   - Workaround: Use `-profile conda` if Wave unavailable
   - Status: Working, well-documented

3. **COMPARATIVE_ANALYSIS Implementation**
   - Status: Infrastructure complete, statistical features planned
   - Available: Stub outputs for testing
   - Roadmap: PCA, differential taxa, statistical testing

See [docs/development/code-quality.md#known-limitations](docs/development/code-quality.md) for details and workarounds.

## Integration Points

### Upstream: nf-core/taxprofiler
taxbencher accepts taxpasta files from taxprofiler:
```bash
# Run taxprofiler with taxpasta output
nextflow run nf-core/taxprofiler --run_taxpasta ...

# Use outputs in taxbencher
nextflow run taxbencher --input from_taxprofiler.csv ...
```

### Test Data
- **Included**: `assets/test_data/` - Minimal but complete
- **CAMI datasets**: https://data.cami-challenge.org/participate
- **Custom data**: Use validation scripts before running

## Contributing

1. **Read**: [docs/development/development-guide.md](docs/development/development-guide.md)
2. **Check**: [docs/development/code-quality.md](docs/development/code-quality.md) for standards
3. **Test**: All new features must have nf-test coverage
4. **Lint**: `nf-core pipelines lint` must pass
5. **Document**: Update relevant documentation

## References

- **nf-core**: https://nf-co.re/
- **Nextflow docs**: https://nextflow.io/docs/latest/
- **nf-test**: https://www.nf-test.com/
- **CAMI OPAL**: https://github.com/CAMI-challenge/OPAL
- **taxpasta**: https://taxpasta.readthedocs.io/
- **nf-core/taxprofiler**: https://nf-co.re/taxprofiler
- **Bioboxes format**: https://github.com/bioboxes/rfc/tree/master/data-format

## Quick Reference Commands

```bash
# Lint pipeline
nf-core pipelines lint

# Run tests
nf-test test

# Test with realistic data
nextflow run . -profile test_realistic,docker

# Validate inputs
python3 bin/validate_bioboxes.py gold_standard.bioboxes
python3 bin/validate_taxpasta.py profile.tsv

# Update modules
nf-core modules update --all

# Check git status
git status
```

For detailed technical documentation, see **[docs/development/](docs/development/)**.
