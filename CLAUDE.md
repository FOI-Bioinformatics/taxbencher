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

- **[Audit Report 2026-10](docs/reports/audit-2026-10.md)** - Latest code & functionality audit
- **[Code Quality Report](docs/reports/code-quality.md)** - Earlier quality assessment
- **[Test Coverage Report](docs/reports/test-coverage.md)** - Detailed test analysis
- **[Validation Report](docs/reports/validation.md)** - Validation infrastructure

## Architecture Overview

### Pipeline Flow

```
VALIDATE_GOLD_STANDARD ─┐
Input → TAXPASTA_STANDARDISE* → TAXPASTA_TO_BIOBOXES (+ ETE3_BUILD_TAXDB from --taxdump) →
Group by sample_id → OPAL_PER_SAMPLE → COMPARATIVE_ANALYSIS → BENCHMARK_SUMMARY → MULTIQC
```

\*Auto-triggered for files that are not taxpasta output (checked by extension and header)

### Key Concepts

**Per-Sample Evaluation**: The pipeline groups profiles by `sample_id` for fair classifier comparison. Each biological sample gets:

- One OPAL run comparing all its classifiers
- One comparative analysis report
- Per-sample metrics and visualizations

**Automatic Format Detection**: Files are routed by extension and header:

- `.tsv`/`.txt` with a `taxonomy_id`/`count` header → taxpasta output, use directly
- everything else (`.kreport`, `.profile`, `.out`, raw DIAMOND/MEGAN `.txt`, ...) → standardize with taxpasta

**CAMI semantics**: converted profiles have clade-cumulative abundances per rank (each rank sums to <= 100 %),
TAXPATH restricted to `@Ranks`. Direct read counts (Kraken2 etc.) are summed over descendants; MetaPhlAn
values are cumulative already (`--abundance-mode clade`, chosen from the classifier column). Gold standards must
follow the same per-rank convention and their `@SampleID` must equal the samplesheet `sample_id` (checked at start).

**Taxonomy**: `--taxdump taxdump.tar.gz` builds one ete3 database (`ETE3_BUILD_TAXDB`) shared by all
conversions. Tests use the reduced archive in `assets/test_data/taxonomy/` (offline, deterministic).

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

### ETE3_BUILD_TAXDB

**Purpose**: Builds the ete3 NCBI taxonomy sqlite database once from `--taxdump`
**Output**: `taxa.sqlite` (+ traverse index) passed to every TAXPASTA_TO_BIOBOXES task

### TAXPASTA_TO_BIOBOXES

**Purpose**: Converts taxpasta TSV to CAMI Bioboxes format (per-rank clade abundances)
**Uses**: Python + ete3 (or taxpasta lineage columns) for taxonomy lookups; `--abundance-mode direct|clade`
**Container**: Seqera Wave (pandas + ete3)
**Fails** instead of writing empty profiles (unknown taxids, inconsistent abundance mode)

### OPAL_PER_SAMPLE

**Purpose**: CAMI OPAL evaluation per biological sample
**Innovation**: Tuple-embedded channel pattern for per-sample multi-classifier evaluation
**Output**: HTML reports, metrics TSV, confusion matrices

### COMPARATIVE_ANALYSIS

**Purpose**: Comparison of classifiers per sample from OPAL's long-format `results.tsv` and the sample's profiles
**Outputs**: wide metrics table, PCA (plotly), per-taxon observed/expected table with TP/FP/FN, HTML report,
MultiQC custom-content table (`*_mqc.tsv`)
**Note**: descriptive only, no p-values (one profile per classifier gives no replication)

See [docs/development/modules.md](docs/development/modules.md) for complete module documentation.

## Development Workflow

### Before Committing

```bash
# 1. Lint the pipeline
nf-core pipelines lint

# 2. Run tests
nf-test test --profile +docker
pytest tests/python          # unit tests of bin/ scripts (pandas, ete3, pytest)

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

**Latest Assessment** (2026-10-28, see [docs/reports/audit-2026-10.md](docs/reports/audit-2026-10.md)):
the audit found that the evaluation path produced invalid CAMI profiles (abundances normalised across ranks,
no clade accumulation) and that the pipeline tests passed while OPAL never ran. Both are fixed; all three
test profiles now run end-to-end (conda) and module tests use pinned, offline taxonomy data.

**Innovative Patterns**:

1. **Tuple-Embedded Channels** - Solves Nextflow cardinality matching for per-sample evaluation
2. **Automatic Format Detection** - Branch-based routing by file extension
3. **Per-Sample Grouping** - groupTuple() for fair classifier comparison

See [docs/reports/code-quality.md](docs/reports/code-quality.md) for full analysis and [docs/development/code-quality.md](docs/development/code-quality.md) for best practices.

## Known Limitations

1. **OPAL 1.0.13 plotting with tiny inputs**
   - Earlier failures ("spider plot" shape errors) were caused by invalid, header-only profiles produced by the
     old converter; with valid profiles the `test` profile (12 taxa) runs through OPAL. Very small or
     single-rank profiles may still trip OPAL's plotting code.

2. **Wave Container Dependencies**
   - Issue: Some modules use Seqera Wave for dynamic container building
   - Workaround: Use `-profile conda` if Wave unavailable
   - Status: Working, well-documented

3. **COMPARATIVE_ANALYSIS**
   - Descriptive comparison only (no significance testing: one profile per classifier)
   - GTDB profiles are only supported via taxpasta lineage columns

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
python3 bin/validate_bioboxes.py --strict gold_standard.bioboxes
python3 bin/validate_taxpasta.py profile.tsv

# Regenerate derived test fixtures (gold standards, module testdata)
bin/regenerate_test_fixtures.sh

# Update modules
nf-core modules update --all

# Check git status
git status
```

For detailed technical documentation, see **[docs/development/](docs/development/)**.
