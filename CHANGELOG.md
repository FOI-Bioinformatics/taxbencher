# FOI-Bioinformatics/taxbencher: Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
