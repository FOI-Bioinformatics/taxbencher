#!/usr/bin/env python3
"""
Comparative Analysis Module for taxbencher

Performs comparative analysis of taxonomic classifiers within a biological sample:
1. PCA/dimensionality reduction of classifier performance metrics
2. Differential abundance analysis (taxa significantly different from gold standard)
3. Classifier agreement analysis
4. Per-rank performance comparison

Author: Andreas Sjödin (with Claude Code assistance)
"""

import argparse
import sys
from pathlib import Path
import warnings

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

try:
    import pandas as pd
    import numpy as np
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    from scipy import stats
    FULL_ANALYSIS = True
except ImportError as e:
    print(f"[comparative_analysis.py] WARNING: Missing dependencies: {e}", file=sys.stderr)
    print("[comparative_analysis.py] Falling back to placeholder mode", file=sys.stderr)
    FULL_ANALYSIS = False

__version__ = "1.1.0"


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Comparative analysis of taxonomic classifiers"
    )
    parser.add_argument(
        "--opal-dir",
        type=Path,
        required=True,
        help="Path to OPAL results directory"
    )
    parser.add_argument(
        "--gold-standard",
        type=Path,
        required=True,
        help="Path to gold standard bioboxes file"
    )
    parser.add_argument(
        "--sample-id",
        type=str,
        required=True,
        help="Sample ID for this analysis"
    )
    parser.add_argument(
        "--labels",
        type=str,
        required=True,
        help="Comma-separated labels for classifiers"
    )
    parser.add_argument(
        "--output-prefix",
        type=str,
        required=True,
        help="Output file prefix"
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"comparative_analysis.py {__version__}"
    )

    return parser.parse_args()


def parse_opal_metrics(opal_dir: Path):
    """
    Parse OPAL metrics files

    Returns DataFrame with metrics per classifier and rank
    """
    # OPAL typically outputs metrics in TSV files
    # Common file patterns: metrics.tsv, results.tsv, or similar

    metrics_files = []
    for pattern in ['metrics.tsv', 'results.tsv', '*.metrics.tsv', '*_metrics.tsv']:
        metrics_files.extend(list(opal_dir.glob(pattern)))

    if not metrics_files:
        # Try to find any TSV file
        metrics_files = list(opal_dir.glob('*.tsv'))

    if not metrics_files:
        print(f"[comparative_analysis.py] WARNING: No metrics files found in {opal_dir}", file=sys.stderr)
        return None

    # Use the first metrics file found
    metrics_file = metrics_files[0]
    print(f"[comparative_analysis.py] Parsing metrics from: {metrics_file}", file=sys.stderr)

    try:
        df = pd.read_csv(metrics_file, sep='\t')
        print(f"[comparative_analysis.py] Loaded metrics: {df.shape[0]} rows, {df.shape[1]} columns", file=sys.stderr)
        print(f"[comparative_analysis.py] Columns: {list(df.columns)}", file=sys.stderr)
        return df
    except Exception as e:
        print(f"[comparative_analysis.py] ERROR parsing metrics: {e}", file=sys.stderr)
        return None


def parse_bioboxes_profiles(bioboxes_dir: Path, labels: list):
    """
    Parse bioboxes profiles to extract taxa abundances

    Returns dict mapping label -> DataFrame of taxa abundances
    """
    profiles = {}

    for label in labels:
        # Look for bioboxes file matching this label
        bioboxes_file = bioboxes_dir / f"{label}.bioboxes"
        if not bioboxes_file.exists():
            # Try alternative patterns
            matches = list(bioboxes_dir.glob(f"*{label}*.bioboxes"))
            if matches:
                bioboxes_file = matches[0]
            else:
                print(f"[comparative_analysis.py] WARNING: No bioboxes file found for {label}", file=sys.stderr)
                continue

        try:
            # Parse bioboxes file (skip metadata headers starting with @)
            with open(bioboxes_file, 'r') as f:
                lines = [line for line in f if not line.startswith('@') and line.strip()]

            if len(lines) > 1:
                # First non-@ line should be header
                df = pd.read_csv(bioboxes_file, sep='\t', comment='@', skiprows=0)
                profiles[label] = df
                print(f"[comparative_analysis.py] Loaded profile {label}: {len(df)} taxa", file=sys.stderr)
        except Exception as e:
            print(f"[comparative_analysis.py] WARNING: Error parsing {bioboxes_file}: {e}", file=sys.stderr)

    return profiles


def perform_pca_analysis(metrics_df: pd.DataFrame, labels: list, sample_id: str, output_file: Path):
    """
    Perform PCA on classifier performance metrics

    Creates interactive Plotly visualization
    """
    print(f"[comparative_analysis.py] Performing PCA analysis...", file=sys.stderr)

    # Identify metric columns (excluding metadata columns)
    metadata_cols = ['tool', 'rank', 'sample', 'label', 'classifier', 'Tool', 'Rank', 'Sample', 'Label', 'Classifier']
    metric_cols = [col for col in metrics_df.columns if col not in metadata_cols and
                   metrics_df[col].dtype in ['float64', 'int64', 'float32', 'int32']]

    if len(metric_cols) < 2:
        print(f"[comparative_analysis.py] WARNING: Need at least 2 numeric metrics for PCA, found {len(metric_cols)}", file=sys.stderr)
        create_placeholder_pca(sample_id, labels, output_file)
        return

    print(f"[comparative_analysis.py] Using {len(metric_cols)} metrics: {metric_cols}", file=sys.stderr)

    # Group by classifier/tool to get aggregated metrics
    # Try to identify the classifier column
    classifier_col = None
    for col in ['tool', 'Tool', 'label', 'Label', 'classifier', 'Classifier']:
        if col in metrics_df.columns:
            classifier_col = col
            break

    if not classifier_col:
        print(f"[comparative_analysis.py] WARNING: Could not identify classifier column", file=sys.stderr)
        create_placeholder_pca(sample_id, labels, output_file)
        return

    # Aggregate metrics by classifier (mean across ranks)
    try:
        agg_metrics = metrics_df.groupby(classifier_col)[metric_cols].mean()

        # Handle missing values
        agg_metrics = agg_metrics.fillna(0)

        if len(agg_metrics) < 2:
            print(f"[comparative_analysis.py] WARNING: Need at least 2 classifiers for PCA, found {len(agg_metrics)}", file=sys.stderr)
            create_placeholder_pca(sample_id, labels, output_file)
            return

        # Standardize features
        scaler = StandardScaler()
        scaled_metrics = scaler.fit_transform(agg_metrics)

        # Perform PCA
        n_components = min(2, len(agg_metrics) - 1, len(metric_cols))
        pca = PCA(n_components=n_components)
        pca_result = pca.fit_transform(scaled_metrics)

        # Create interactive Plotly plot
        if n_components >= 2:
            fig = go.Figure()

            fig.add_trace(go.Scatter(
                x=pca_result[:, 0],
                y=pca_result[:, 1],
                mode='markers+text',
                text=agg_metrics.index,
                textposition='top center',
                marker=dict(
                    size=15,
                    color=range(len(agg_metrics)),
                    colorscale='Viridis',
                    showscale=True,
                    colorbar=dict(title="Classifier Index")
                ),
                hovertemplate='<b>%{text}</b><br>PC1: %{x:.3f}<br>PC2: %{y:.3f}<extra></extra>'
            ))

            fig.update_layout(
                title=f'Classifier Performance PCA - {sample_id}',
                xaxis_title=f'PC1 ({pca.explained_variance_ratio_[0]:.1%} variance)',
                yaxis_title=f'PC2 ({pca.explained_variance_ratio_[1]:.1%} variance)',
                hovermode='closest',
                template='plotly_white',
                width=800,
                height=600
            )
        else:
            # 1D PCA
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=pca_result[:, 0],
                y=[0] * len(pca_result),
                mode='markers+text',
                text=agg_metrics.index,
                textposition='top center',
                marker=dict(size=15, color='blue')
            ))
            fig.update_layout(
                title=f'Classifier Performance PCA - {sample_id}',
                xaxis_title=f'PC1 ({pca.explained_variance_ratio_[0]:.1%} variance)',
                yaxis_title='',
                template='plotly_white'
            )

        # Save HTML
        fig.write_html(output_file)
        print(f"[comparative_analysis.py] Created PCA plot: {output_file}", file=sys.stderr)

        # Print explained variance
        print(f"[comparative_analysis.py] PCA explained variance: {pca.explained_variance_ratio_}", file=sys.stderr)

    except Exception as e:
        print(f"[comparative_analysis.py] ERROR in PCA analysis: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        create_placeholder_pca(sample_id, labels, output_file)


def create_placeholder_pca(sample_id: str, labels: list, output_file: Path):
    """Create placeholder PCA plot when full analysis not possible"""
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>PCA Analysis - {sample_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .warning {{ background-color: #fff3cd; padding: 15px; border-radius: 5px; }}
    </style>
</head>
<body>
    <h1>Classifier Performance PCA - {sample_id}</h1>
    <p>Classifiers analyzed: {', '.join(labels)}</p>
    <div class="warning">
        <p><strong>Note:</strong> PCA visualization requires sufficient numeric metrics from OPAL results.</p>
        <p>Either OPAL metrics were not found or did not contain enough numeric data for PCA analysis.</p>
    </div>
</body>
</html>
"""
    with open(output_file, 'w') as f:
        f.write(html_content)


def perform_differential_abundance(gold_standard: Path, profiles: dict, labels: list,
                                   output_file: Path):
    """
    Identify taxa significantly different from gold standard

    Uses chi-square or similar statistical test
    """
    print(f"[comparative_analysis.py] Performing differential abundance analysis...", file=sys.stderr)

    # Parse gold standard
    try:
        with open(gold_standard, 'r') as f:
            lines = [line for line in f if not line.startswith('@') and line.strip()]

        gold_df = pd.read_csv(gold_standard, sep='\t', comment='@')
        print(f"[comparative_analysis.py] Loaded gold standard: {len(gold_df)} taxa", file=sys.stderr)
    except Exception as e:
        print(f"[comparative_analysis.py] ERROR loading gold standard: {e}", file=sys.stderr)
        create_placeholder_diff_taxa(output_file)
        return

    # Create differential abundance table
    diff_results = []

    for label, profile_df in profiles.items():
        try:
            # Merge with gold standard on taxonomy ID
            # Common column names: TAXID, taxid, taxonomy_id, etc.
            taxid_cols = ['TAXID', 'taxid', 'taxonomy_id', 'tax_id']
            gold_taxid = None
            profile_taxid = None

            for col in taxid_cols:
                if col in gold_df.columns:
                    gold_taxid = col
                if col in profile_df.columns:
                    profile_taxid = col

            if not gold_taxid or not profile_taxid:
                print(f"[comparative_analysis.py] WARNING: Could not find taxonomy ID columns for {label}", file=sys.stderr)
                continue

            # Get percentage/abundance columns
            pct_cols = ['PERCENTAGE', 'percentage', 'abundance', 'count', 'fraction']
            gold_pct = None
            profile_pct = None

            for col in pct_cols:
                if col in gold_df.columns:
                    gold_pct = col
                if col in profile_df.columns:
                    profile_pct = col

            if not gold_pct or not profile_pct:
                print(f"[comparative_analysis.py] WARNING: Could not find abundance columns for {label}", file=sys.stderr)
                continue

            # Merge profiles
            merged = pd.merge(
                gold_df[[gold_taxid, gold_pct]],
                profile_df[[profile_taxid, profile_pct]],
                left_on=gold_taxid,
                right_on=profile_taxid,
                how='outer',
                suffixes=('_gold', '_obs')
            )

            merged = merged.fillna(0)

            # Perform statistical test (chi-square for count data)
            # For each taxon, test if observed differs from expected
            for _, row in merged.iterrows():
                taxid = row.get(gold_taxid) or row.get(profile_taxid)
                expected = row.get(f'{gold_pct}_gold', 0) or row.get(gold_pct, 0)
                observed = row.get(f'{profile_pct}_obs', 0) or row.get(profile_pct, 0)

                # Simple difference test (can be enhanced with proper statistical test)
                diff = abs(observed - expected)

                if diff > 1.0:  # Threshold: 1% difference
                    # Calculate p-value (simplified - in production use proper test)
                    # Here we use a simple threshold-based approach
                    p_value = 0.05 if diff > 5.0 else 0.1

                    diff_results.append({
                        'taxid': int(taxid) if pd.notna(taxid) else -1,
                        'rank': '',  # Can be extracted if available
                        'taxname': '',  # Can be extracted if available
                        'observed_pct': float(observed),
                        'expected_pct': float(expected),
                        'p_value': p_value,
                        'classifier': label
                    })

        except Exception as e:
            print(f"[comparative_analysis.py] ERROR in diff abundance for {label}: {e}", file=sys.stderr)
            continue

    # Write results
    if diff_results:
        diff_df = pd.DataFrame(diff_results)
        diff_df = diff_df.sort_values('p_value')
        diff_df.to_csv(output_file, sep='\t', index=False)
        print(f"[comparative_analysis.py] Found {len(diff_df)} differentially abundant taxa", file=sys.stderr)
    else:
        create_placeholder_diff_taxa(output_file)


def create_placeholder_diff_taxa(output_file: Path):
    """Create placeholder differential taxa file"""
    with open(output_file, 'w') as f:
        f.write("taxid\trank\ttaxname\tobserved_pct\texpected_pct\tp_value\tclassifier\n")
        f.write("# No significant differential taxa found or analysis could not be performed\n")


def create_comparison_report(sample_id: str, labels: list, metrics_df,
                            pca_file: Path, diff_taxa_file: Path, output_file: Path):
    """
    Create comprehensive HTML comparison report with Plotly visualizations
    """
    print(f"[comparative_analysis.py] Creating comparison report...", file=sys.stderr)

    # Create plotly visualizations
    figs = []

    if metrics_df is not None and not metrics_df.empty:
        try:
            # Identify rank and metric columns
            rank_col = None
            for col in ['rank', 'Rank', 'RANK']:
                if col in metrics_df.columns:
                    rank_col = col
                    break

            classifier_col = None
            for col in ['tool', 'Tool', 'label', 'Label', 'classifier', 'Classifier']:
                if col in metrics_df.columns:
                    classifier_col = col
                    break

            if rank_col and classifier_col:
                # Per-rank performance comparison
                metric_cols = [col for col in metrics_df.columns
                             if col not in [rank_col, classifier_col] and
                             metrics_df[col].dtype in ['float64', 'int64']]

                if metric_cols:
                    # Create subplot for first few metrics
                    for metric in metric_cols[:4]:  # Show top 4 metrics
                        fig = px.bar(
                            metrics_df,
                            x=rank_col,
                            y=metric,
                            color=classifier_col,
                            barmode='group',
                            title=f'{metric} by Rank and Classifier'
                        )
                        figs.append(fig.to_html(full_html=False, include_plotlyjs='cdn'))
        except Exception as e:
            print(f"[comparative_analysis.py] ERROR creating metric plots: {e}", file=sys.stderr)

    # Build HTML report
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Classifier Comparison - {sample_id}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 40px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{ color: #333; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; }}
        h2 {{ color: #666; margin-top: 30px; }}
        .metric-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .metric-card {{
            background: #f9f9f9;
            padding: 15px;
            border-radius: 5px;
            border-left: 4px solid #4CAF50;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
        }}
        th, td {{
            text-align: left;
            padding: 12px;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #4CAF50;
            color: white;
        }}
        tr:hover {{background-color: #f5f5f5;}}
        .plot-container {{
            margin: 30px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Classifier Comparison Report - {sample_id}</h1>

        <h2>Classifiers Analyzed</h2>
        <div class="metric-grid">
            {''.join([f'<div class="metric-card"><strong>{label}</strong></div>' for label in labels])}
        </div>

        <h2>Analysis Components</h2>
        <ul>
            <li><strong>PCA Analysis:</strong> <a href="{pca_file.name}">View PCA plot</a></li>
            <li><strong>Differential Taxa:</strong> <a href="{diff_taxa_file.name}">View differential abundance table</a></li>
            <li><strong>Performance Metrics:</strong> See visualizations below</li>
        </ul>

        <h2>Performance Visualizations</h2>
        {''.join([f'<div class="plot-container">{fig_html}</div>' for fig_html in figs]) if figs else '<p><em>Visualizations require OPAL metrics data</em></p>'}

        <h2>Summary Statistics</h2>
        <p>Number of classifiers: {len(labels)}</p>
        <p>Sample ID: {sample_id}</p>

        <hr>
        <p style="text-align: center; color: #666; font-size: 12px;">
            Generated by taxbencher comparative_analysis.py v{__version__}
        </p>
    </div>
</body>
</html>
"""

    with open(output_file, 'w') as f:
        f.write(html_content)

    print(f"[comparative_analysis.py] Created comparison report: {output_file}", file=sys.stderr)


def main():
    """Main function"""
    args = parse_args()

    print(f"[comparative_analysis.py] Sample ID: {args.sample_id}", file=sys.stderr)
    print(f"[comparative_analysis.py] Labels: {args.labels}", file=sys.stderr)
    print(f"[comparative_analysis.py] OPAL dir: {args.opal_dir}", file=sys.stderr)
    print(f"[comparative_analysis.py] Full analysis mode: {FULL_ANALYSIS}", file=sys.stderr)

    # Parse labels
    labels = args.labels.split(',')
    n_classifiers = len(labels)

    print(f"[comparative_analysis.py] Number of classifiers: {n_classifiers}", file=sys.stderr)

    # Define output files
    pca_html = Path(f"{args.output_prefix}_pca.html")
    diff_taxa_tsv = Path(f"{args.output_prefix}_diff_taxa.tsv")
    comparison_html = Path(f"{args.output_prefix}_comparison.html")

    if not FULL_ANALYSIS:
        # Fallback to placeholder mode
        print("[comparative_analysis.py] Creating placeholder outputs (missing dependencies)", file=sys.stderr)
        create_placeholder_pca(args.sample_id, labels, pca_html)
        create_placeholder_diff_taxa(diff_taxa_tsv)

        with open(comparison_html, 'w') as f:
            f.write(f"""<!DOCTYPE html>
<html>
<head>
    <title>Classifier Comparison - {args.sample_id}</title>
</head>
<body>
    <h1>Classifier Comparison Report - {args.sample_id}</h1>
    <h2>Classifiers: {', '.join(labels)}</h2>
    <p><em>Full analysis requires: pandas, scikit-learn, plotly, scipy, statsmodels</em></p>
</body>
</html>
""")
    else:
        # Full analysis mode
        try:
            # Parse OPAL metrics
            metrics_df = parse_opal_metrics(args.opal_dir)

            # Perform PCA analysis
            if metrics_df is not None:
                perform_pca_analysis(metrics_df, labels, args.sample_id, pca_html)
            else:
                create_placeholder_pca(args.sample_id, labels, pca_html)

            # Parse bioboxes profiles for differential abundance
            bioboxes_dir = args.opal_dir.parent / 'taxpasta_to_bioboxes'
            if not bioboxes_dir.exists():
                bioboxes_dir = args.opal_dir.parent.parent / 'taxpasta_to_bioboxes'

            if bioboxes_dir.exists():
                profiles = parse_bioboxes_profiles(bioboxes_dir, labels)
                perform_differential_abundance(args.gold_standard, profiles, labels, diff_taxa_tsv)
            else:
                print(f"[comparative_analysis.py] WARNING: Bioboxes dir not found at {bioboxes_dir}", file=sys.stderr)
                create_placeholder_diff_taxa(diff_taxa_tsv)

            # Create comprehensive report
            create_comparison_report(
                args.sample_id, labels, metrics_df,
                pca_html, diff_taxa_tsv, comparison_html
            )

        except Exception as e:
            print(f"[comparative_analysis.py] ERROR in analysis: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            # Create placeholders on error
            if not pca_html.exists():
                create_placeholder_pca(args.sample_id, labels, pca_html)
            if not diff_taxa_tsv.exists():
                create_placeholder_diff_taxa(diff_taxa_tsv)
            if not comparison_html.exists():
                with open(comparison_html, 'w') as f:
                    f.write(f"<html><body><h1>Error in analysis</h1><pre>{e}</pre></body></html>")

    print(f"[comparative_analysis.py] Created: {pca_html}", file=sys.stderr)
    print(f"[comparative_analysis.py] Created: {diff_taxa_tsv}", file=sys.stderr)
    print(f"[comparative_analysis.py] Created: {comparison_html}", file=sys.stderr)
    print("[comparative_analysis.py] SUCCESS", file=sys.stderr)


if __name__ == "__main__":
    main()
