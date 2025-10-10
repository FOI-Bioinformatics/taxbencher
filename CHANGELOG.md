# FOI-Bioinformatics/taxbencher: Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## v1.0.2 - Unreleased

Enhanced test coverage, comprehensive profiler support, and documentation for raw profiler input feature.

### Added

- **Test Coverage Enhancements (Sprint 1)**:
  - Added Centrifuge test to TAXPASTA_STANDARDISE module with correct report format
  - Added MetaPhlAn test to TAXPASTA_STANDARDISE module with 4-column profile format
  - Created `test_raw` profile configuration for end-to-end testing with raw inputs
  - Added pipeline-level nf-test for test_raw profile validation
  - New test data files for Centrifuge and MetaPhlAn raw formats

- **Pipeline Testing Infrastructure (Sprint 2)**:
  - Added end-to-end pipeline test for test_raw profile in `tests/default.nf.test`
  - Pipeline tests verify TAXPASTA_STANDARDISE execution in full workflow context
  - Tests validate channel branching and format detection logic
  - Snapshot-based validation of pipeline outputs and task counts

- **Extended Profiler Support (Sprint 3)**:
  - Comprehensive file extension support for all 11 taxpasta-supported profilers
  - Added extensions: `.kreport2`, `.mpa3`, `.krakenuniq`, `.diamond`, `.kmcp`, `.ganon`, `.motus`, `.megan`
  - Schema validation enhanced with descriptive error messages mapping extensions to profilers
  - Support for KMCP, ganon, DIAMOND, mOTUs, MEGAN6/MALT, and KrakenUniq raw outputs

- **Documentation (Sprints 1-3)**:
  - Comprehensive raw profiler input documentation in `docs/usage.md`
  - **NEW**: Dedicated `docs/raw-inputs.md` with detailed format specifications for all 11 profilers
  - Format examples, troubleshooting guide, and integration workflows
  - Table of supported formats with file extensions and format descriptions
  - Example samplesheets for raw profiler outputs, pre-standardized files, and mixed formats
  - Updated workflow overview to include standardization step
  - Updated samplesheet column descriptions for dual format support
  - Enhanced CLAUDE.md with architecture documentation for developers

### Fixed

- `.gitignore` pattern that was blocking test data directories from being committed
- Schema validation now accepts `.report` extension for Centrifuge files
- Removed nested profile from `test.config` (moved to separate `test_raw.config`)

### Changed

- Updated MetaPhlAn test data to include `additional_species` column (4 columns total)
- Added Centrifuge report format test data (6-column format)
- Enhanced test data now matches actual taxpasta expected formats
- Schema input validation pattern expanded to support all taxpasta-compatible extensions
- Improved schema error messages with profiler-specific extension mappings

### Testing

- All TAXPASTA_STANDARDISE module tests pass (4/4: Kraken2, Centrifuge, MetaPhlAn, Stub)
- Pipeline-level tests for both standard and raw input profiles
- Test fixtures now properly tracked in git repository
- Comprehensive test coverage for format detection and standardization workflow

## v1.0.1 - 2025-10-09

Critical validation enhancements to prevent OPAL failures and improve gold standard file handling.

### Added

- **Gold Standard Validation & Fixing**:
  - `fix_gold_standard.py`: Automatic fixing tool for common gold standard issues
    - Adds missing TAXPATH column
    - Filters unsupported OPAL ranks (root, no rank, unknown, cellular root, domain, kingdom, subspecies)
    - Maps non-standard ranks to OPAL-compatible equivalents
    - Renormalizes percentages after filtering
    - Fixes column count mismatches
  - `docs/troubleshooting-gold-standard.md`: Comprehensive troubleshooting guide with examples

- **Enhanced `validate_bioboxes.py`**:
  - **CRITICAL**: Column count mismatch detection (prevents "Column not found: TAXPATH" errors)
  - **CRITICAL**: Unsupported OPAL rank detection in data rows
  - Header rank validation against OPAL-supported ranks
  - Added `@TaxonomyID` to required headers
  - Clear error messages pointing to `fix_gold_standard.py`
  - Statistics on unsupported ranks found

- **Enhanced `taxpasta_to_bioboxes.py`**:
  - Filters unsupported OPAL ranks from prediction files
  - Maps ranks automatically (subspecies→strain, domain/kingdom→superkingdom)
  - Renormalizes percentages after filtering
  - Prevents pipeline failures due to rank incompatibilities

### Fixed

- OPAL failures caused by unsupported taxonomic ranks in gold standard files
- OPAL failures caused by column count mismatches between header and data
- Cryptic error messages replaced with actionable validation feedback

### Changed

- Updated README.md with validation workflow and troubleshooting guide link
- Updated CLAUDE.md with detailed validation infrastructure documentation
- Enhanced validation workflow examples with automatic fixing

### Documentation

- New troubleshooting guide with real-world examples
- Updated validation sections in README and CLAUDE.md
- Added examples of valid vs invalid gold standard files

## v1.0.0 - 2025-10-08

Initial release of FOI-Bioinformatics/taxbencher, created with the [nf-core](https://nf-core.com/) template.

This release provides a complete nf-core-compliant pipeline for benchmarking taxonomic classifiers using CAMI OPAL evaluation framework.

### Added

- **Modules**:
  - `TAXPASTA_TO_BIOBOXES`: Converts taxpasta TSV to CAMI Bioboxes format
  - `OPAL`: CAMI OPAL evaluation framework for taxonomic profiler benchmarking
  - `MULTIQC`: Aggregated reporting across all samples

- **Validation Tools**:
  - `validate_taxpasta.py`: Pre-flight validation for taxpasta TSV format
  - `validate_bioboxes.py`: Pre-flight validation for CAMI Bioboxes format
  - Comprehensive input data validation with detailed error messages

- **Testing Infrastructure**:
  - nf-test suite for all modules
  - TAXPASTA_TO_BIOBOXES: 3 tests (basic, custom parameters, stub)
  - OPAL: 4 tests (single prediction, multiple predictions, filtering, stub)
  - Full pipeline test configuration
  - Test data in `assets/test_data/`

- **Features**:
  - Integration with nf-core/taxprofiler outputs
  - Support for NCBI and GTDB taxonomy databases
  - Comprehensive OPAL metrics: precision, recall, F1, UniFrac, L1/L2 norms, Bray-Curtis, Shannon diversity
  - Per-rank analysis (species, genus, family, etc.)
  - HTML reports with interactive visualizations

- **Containerization**:
  - Docker support
  - Singularity support
  - Conda environments
  - All containers from biocontainers/bioconda

- **Documentation**:
  - Complete usage guide (`docs/usage.md`)
  - Output file descriptions (`docs/output.md`)
  - Local testing guide (`docs/local_testing.md`)
  - Developer guide (`CLAUDE.md`)
  - Validation report (`VALIDATION_REPORT.md`)

### Dependencies

- Nextflow ≥24.10.5
- nf-core template v3.3.2
- Python 3.11 (for taxpasta_to_bioboxes)
  - pandas
  - ete3 (for taxonomy lookups)
- OPAL 1.0.13
- MultiQC
