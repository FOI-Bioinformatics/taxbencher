# FOI-Bioinformatics/taxbencher: Output

## Introduction

This document describes the output produced by the taxbencher pipeline. The pipeline evaluates taxonomic classifiers by comparing their predictions against a gold standard using the CAMI OPAL framework.

All output files are created in the directory specified with `--outdir`.

## Pipeline overview

The pipeline processes data using the following steps:

1. **Format Conversion** - Convert taxpasta TSV to CAMI Bioboxes format
2. **Evaluation** - Run OPAL benchmarking against gold standard
3. **Reporting** - Aggregate results with MultiQC

## Output Directory Structure

```
results/
├── taxpasta_to_bioboxes/     # Converted bioboxes files
├── opal/                      # Per-sample OPAL evaluation results
├── comparative_analysis/      # Per-sample comparative analysis reports
├── multiqc/                   # Aggregated reports
└── pipeline_info/             # Pipeline execution info
```

## Detailed Outputs

### taxpasta_to_bioboxes

<details markdown="1">
<summary>Output files</summary>

- `taxpasta_to_bioboxes/`
  - `<label>.bioboxes` - Converted profiles in CAMI Bioboxes format (one per taxonomic profile)

</details>

**Description:**

Taxpasta TSV files are converted to CAMI profiling Bioboxes format, which is required for OPAL evaluation. Each profile contains:

- Sample metadata headers (@SampleID, @Version, @Ranks, @TaxonomyID)
- Taxonomic assignments with:
  - **TAXID**: NCBI/GTDB taxonomy ID
  - **RANK**: Taxonomic rank (species, genus, etc.)
  - **TAXPATH**: Pipe-separated lineage
  - **TAXPATHSN**: Pipe-separated taxon names
  - **PERCENTAGE**: Relative abundance

**Example**:

```
@SampleID:sample1_kraken2
@Version:0.9.1
@Ranks:superkingdom|phylum|class|order|family|genus|species
@TaxonomyID:NCBI
@@TAXID	RANK	TAXPATH	TAXPATHSN	PERCENTAGE
562	species	131567|2|1224|1236|135622|543|561|562	Biota|Bacteria|Pseudomonadota|...	45.5
```

### OPAL

<details markdown="1">
<summary>Output files</summary>

- `opal/<sample_id>/`
  - `results.html` - Interactive HTML report with plots and metrics
  - `results.tsv` - Tab-separated metrics table
  - `confusion.tsv` - Confusion matrix data
  - `plot_*.{png,pdf}` - Individual metric plots (Shannon diversity, etc.)
  - `by_rank/` - Per-rank metrics breakdowns
  - `by_tool/` - Per-tool metrics breakdowns
  - `gold_standard/` - Gold standard profile visualizations

</details>

**Description:**

OPAL runs once per biological sample (sample_id), evaluating all classifiers for that sample together. Each sample gets its own OPAL results directory.

OPAL computes comprehensive benchmarking metrics for each classifier within the sample:

#### Accuracy Metrics

- **Precision** - Fraction of predicted taxa that are correct
- **Recall** - Fraction of true taxa that were detected
- **F1 Score** - Harmonic mean of precision and recall

#### Distance Metrics

- **UniFrac** - Phylogenetic distance considering evolutionary relationships
- **L1 Norm** - Manhattan distance between abundance profiles
- **L2 Norm** - Euclidean distance
- **Bray-Curtis** - Ecological dissimilarity index

#### Diversity Metrics

- **Shannon Diversity** - Species diversity comparison
- **Jaccard Index** - Set similarity

#### Per-Rank Analysis

Results are computed at multiple taxonomic ranks (species, genus, family, etc.)

#### HTML Report

The interactive HTML report includes:

- Heatmaps comparing all classifiers
- Rarefaction curves
- Beta diversity plots
- Rank-specific performance tables
- Tool-specific detailed breakdowns

### Comparative Analysis

<details markdown="1">
<parameter name="file_path">Output files</summary>

- `comparative_analysis/<sample_id>/`
  - `<sample_id>_pca.html` - PCA visualization of classifier performance metrics
  - `<sample_id>_diff_taxa.tsv` - Taxa significantly different from gold standard
  - `<sample_id>_comparison.html` - Comprehensive classifier comparison report

</details>

**Description:**

Comparative analysis is performed for each biological sample, comparing all classifiers evaluated for that sample:

#### PCA Analysis (`*_pca.html`)

- Principal Component Analysis of classifier performance metrics
- Visualizes similarity/differences between classifiers
- Based on precision, recall, F1 scores across taxonomic ranks
- **Current status**: Placeholder (requires pandas/sklearn/plotly for full implementation)

#### Differential Taxa (`*_diff_taxa.tsv`)

Tab-separated table identifying taxa that show significant differences from the gold standard:

| Column | Description |
|--------|-------------|
| taxid | NCBI/GTDB taxonomy ID |
| rank | Taxonomic rank |
| taxname | Taxon name |
| observed_pct | Observed percentage in prediction |
| expected_pct | Expected percentage from gold standard |
| p_value | Statistical significance (chi-square or similar) |
| classifier | Classifier name |

**Current status**: Placeholder structure (requires scipy/statsmodels for statistical testing)

#### Comparison Report (`*_comparison.html`)

Comprehensive HTML report including:

- Classifier agreement heatmap (Jaccard similarity)
- Per-rank performance bar charts
- Top misclassified taxa tables
- Summary statistics

**Current status**: Placeholder with defined structure for future implementation

> **Note**: The comparative_analysis module is currently implemented as a placeholder demonstrating the output structure. Full statistical analysis and visualizations require additional dependencies (pandas, scikit-learn, plotly, scipy, statsmodels) which will be added in future versions.

### MultiQC

<details markdown="1">
<summary>Output files</summary>

- `multiqc/`
  - `multiqc_report.html` - Standalone HTML report
  - `multiqc_data/` - Parsed statistics and data tables
  - `multiqc_plots/` - Static plot images

</details>

**Description:**

[MultiQC](http://multiqc.info) aggregates results from all pipeline steps into a single report:

- Pipeline execution summary
- Software versions used
- OPAL metrics summary (if MultiQC plugin available)
- Per-sample and per-tool comparisons

### Pipeline Information

<details markdown="1">
<summary>Output files</summary>

- `pipeline_info/`
  - `execution_report.html` - Nextflow execution report
  - `execution_timeline.html` - Timeline of all tasks
  - `execution_trace.txt` - Trace file with resource usage
  - `pipeline_dag.svg` - Pipeline directed acyclic graph
  - `samplesheet.valid.csv` - Validated samplesheet used
  - `params.json` - Parameters used for this run
  - `taxbencher_software_mqc_versions.yml` - Software versions

</details>

**Description:**

[Nextflow](https://www.nextflow.io/docs/latest/tracing.html) generates detailed execution reports showing:

- Task completion times
- Resource usage (CPU, memory, time)
- Failed tasks (if any)
- Complete audit trail

## Interpreting Results

### Good Classifier Performance

A good taxonomic classifier shows:

- **High precision** (>0.9) - Few false positives
- **High recall** (>0.8) - Detects most true taxa
- **Low UniFrac distance** (<0.2) - Phylogenetically accurate
- **High F1 score** (>0.85) - Balanced accuracy

### Comparing Classifiers

Use OPAL HTML report to compare:

1. **Overall metrics** - Which classifier has highest F1?
2. **Rank-specific** - Does performance vary by taxonomic level?
3. **Beta diversity** - Are all classifiers consistently wrong, or differently wrong?
4. **Species-level accuracy** - Critical for applications needing strain resolution

### Common Issues

#### Low Recall

- Classifier database may be incomplete
- Stringent filtering removing true positives
- Check tool-specific thresholds

#### Low Precision

- Over-classification (assigning reads too specifically)
- Database contamination
- Check for false positive patterns in confusion matrix

#### High UniFrac but good accuracy

- Classifier may be assigning to closely related taxa
- May indicate database/taxonomy version mismatch

## Quality Control

Before interpreting results, verify:

1. All input taxpasta files were valid (use `validate_taxpasta.py`)
2. Gold standard format is correct (use `validate_bioboxes.py`)
3. Pipeline completed without errors
4. Check `pipeline_info/execution_report.html` for warnings

For validation tools, see [Local Testing documentation](local_testing.md#validation-scripts).

## Additional Resources

- [OPAL Documentation](https://github.com/CAMI-challenge/OPAL)
- [CAMI Challenge](https://cami-challenge.org/)
- [Bioboxes Format Specification](https://github.com/bioboxes/rfc/tree/master/data-format)
