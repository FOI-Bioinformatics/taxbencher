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

Taxpasta TSV files are converted to CAMI profiling Bioboxes format, which is required for OPAL evaluation.
Abundances are _clade cumulative per rank_: the abundance of a genus includes all of its species, and the
entries of one rank sum to at most 100 % (exactly 100 % when every classified read could be placed at that
rank). Read counts assigned directly to a taxon (Kraken2, Centrifuge, Kaiju, ...) are summed over
descendants; MetaPhlAn clade abundances are used as they are. Unclassified reads (taxonomy ID 0) are excluded
from the denominator unless `--include_unclassified` is set. Each profile contains:

- Sample metadata headers (@SampleID, @Version, @Ranks, @TaxonomyID)
- Taxonomic assignments with:
  - **TAXID**: NCBI/GTDB taxonomy ID
  - **RANK**: Taxonomic rank (species, genus, etc.)
  - **TAXPATH**: Pipe-separated taxonomy IDs, one per rank of `@Ranks` up to the entry's rank (empty for missing ranks)
  - **TAXPATHSN**: Matching scientific names
  - **PERCENTAGE**: Relative abundance at that rank

**Example**:

```
@SampleID:sample1
@Version:0.9.1
@Ranks:superkingdom|phylum|class|order|family|genus|species|strain
@TaxonomyID:NCBI
@@TAXID	RANK	TAXPATH	TAXPATHSN	PERCENTAGE
2	superkingdom	2	Bacteria	100.000000
1224	phylum	2|1224	Bacteria|Pseudomonadota	97.904856
562	species	2|1224|1236|91347|543|561|562	Bacteria|Pseudomonadota|Gammaproteobacteria|Enterobacterales|Enterobacteriaceae|Escherichia|Escherichia coli	45.500000
```

### OPAL

<details markdown="1">
<summary>Output files</summary>

- `opal/<sample_id>/`
  - `results.html` - Interactive HTML report with plots and metrics
  - `results.tsv` - Tab-separated metrics table (long format: tool, rank, metric, sample, value)
  - `opal.log` - OPAL log of this run
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
<summary>Output files</summary>

- `comparative_analysis/`
  - `<sample_id>_metrics_wide.tsv` - OPAL metrics pivoted to one row per classifier and rank
  - `<sample_id>_pca.html` - Interactive PCA of classifiers (and the gold standard) on all OPAL metric/rank features
  - `<sample_id>_diff_taxa.tsv` - Per-taxon comparison of every classifier with the gold standard
  - `<sample_id>_comparison.html` - HTML report with per-rank metric plots, metric table and TP/FP/FN counts
  - `<sample_id>_opal_summary_mqc.tsv` - MultiQC custom-content table (key metrics per classifier)

</details>

**Description:**

Comparative analysis is performed once per biological sample, using that sample's OPAL results and the
converted classifier profiles.

#### Metrics table (`*_metrics_wide.tsv`)

OPAL writes metrics in a long format (`tool, rank, metric, sample, value`). This table pivots them to one row
per `tool` and `rank` with one column per metric (Completeness, Purity, F1 score, L1 norm error, Bray-Curtis
distance, Shannon diversity, True/False positives, False negatives, Taxon counts, ...). Rank independent
metrics (weighted and unweighted UniFrac) are repeated on every rank row of a tool.

#### PCA (`*_pca.html`)

Principal component analysis of the classifiers, using the standardised OPAL metric values of every rank as
features. The gold standard is included as a reference point (perfect scores), so distance to it summarises
overall accuracy. PCA needs at least two classifiers and two non-constant features; otherwise an explanatory
placeholder page is written.

#### Per-taxon comparison (`*_diff_taxa.tsv`)

| Column       | Description                                                                       |
| ------------ | --------------------------------------------------------------------------------- |
| classifier   | Classifier label                                                                  |
| rank         | Taxonomic rank                                                                    |
| taxid        | Taxonomy ID                                                                       |
| taxname      | Taxon name (from TAXPATHSN)                                                       |
| observed_pct | Abundance reported by the classifier                                              |
| expected_pct | Abundance in the gold standard                                                    |
| abs_diff_pct | observed - expected (percentage points)                                           |
| log2_ratio   | log2(observed / expected); `+inf` for false positives, `-inf` for false negatives |
| status       | `TP` (in both), `FP` (classifier only) or `FN` (gold standard only)               |

No p-values are reported: with a single profile per classifier there is no replication to test against, so
the comparison is descriptive. Use `--diff-min-abs` (module `ext.args`) to restrict the table to larger
differences.

#### Comparison report (`*_comparison.html`)

Interactive bar charts of Completeness, Purity, F1, L1 norm error, weighted UniFrac and Bray-Curtis per rank
and classifier, the full metrics table and a TP/FP/FN summary per classifier and rank.

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

- Pipeline execution summary and methods description with tool citations
- Software versions used
- **OPAL summary** table: Completeness, Purity, F1, L1 norm error, Bray-Curtis, UniFrac errors, Shannon
  diversity and TP/FP/FN counts at the species rank (configurable with `--summary-rank` in the
  `COMPARATIVE_ANALYSIS` `ext.args`) for every sample and classifier

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
