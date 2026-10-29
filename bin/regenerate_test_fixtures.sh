#!/usr/bin/env bash
# Regenerate the derived test fixtures (gold standards, converted CAMI profiles and
# OPAL results) from the primary test inputs using the pipeline's own scripts.
#
# Requirements on PATH: python3 with pandas + ete3, taxpasta, opal.py
# Usage: bin/regenerate_test_fixtures.sh   (from the repository root)
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
BIN="$ROOT/bin"
TD="$ROOT/assets/test_data"
TAXDUMP="$TD/taxonomy/taxdump.tar.gz"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
export DISABLE_PANDERA_IMPORT_WARNING=True

echo "== building ete3 database from $TAXDUMP"
python3 - "$TAXDUMP" "$WORK/taxa.sqlite" <<'PY'
import sys
from ete3 import NCBITaxa
NCBITaxa(dbfile=sys.argv[2], taxdump_file=sys.argv[1])
PY
DB="$WORK/taxa.sqlite"

echo "== gold standards"
python3 "$BIN/fix_gold_standard.py" -i "$TD/truth/truth_test_sample.tsv"     -o "$TD/gold_standard.bioboxes"           --ete3-db "$DB" --fill-higher-ranks
python3 "$BIN/fix_gold_standard.py" -i "$TD/truth/truth_test_sample_raw.tsv" -o "$TD/gold_standard_raw.bioboxes"       --ete3-db "$DB" --fill-higher-ranks
python3 "$BIN/fix_gold_standard.py" -i "$TD/truth/truth_test1.tsv"           -o "$TD/gold_standard_realistic.bioboxes" --ete3-db "$DB" --fill-higher-ranks
for f in "$TD"/gold_standard*.bioboxes; do python3 "$BIN/validate_bioboxes.py" --strict --quiet "$f" > /dev/null; done

echo "== OPAL_PER_SAMPLE test data"
OPAL_TD="$ROOT/modules/local/opal_per_sample/testdata"
cp "$TD/gold_standard.bioboxes" "$OPAL_TD/gold_standard.bioboxes"
cp "$TD/gold_standard_realistic.bioboxes" "$OPAL_TD/gold_standard_realistic.bioboxes"
conv() { # input tsv, output, sample, mode
    python3 "$BIN/taxpasta_to_bioboxes.py" -i "$1" -o "$2" -s "$3" --abundance-mode "$4" --ete3-db "$DB" > /dev/null 2>&1
}
conv "$TD/taxpasta/sample1_kraken2.tsv"      "$OPAL_TD/prediction1.bioboxes" test_sample direct
conv "$TD/taxpasta/sample1_metaphlan.tsv"    "$OPAL_TD/prediction2.bioboxes" test_sample clade
conv "$TD/taxpasta/sample2_kraken2.tsv"      "$OPAL_TD/prediction3.bioboxes" test_sample direct
conv "$TD/taxpasta/realistic_kraken2.tsv"    "$OPAL_TD/prediction_realistic1.bioboxes" test1 direct
conv "$TD/taxpasta/realistic_metaphlan.tsv"  "$OPAL_TD/prediction_realistic2.bioboxes" test1 clade
conv "$TD/taxpasta/realistic_centrifuge.tsv" "$OPAL_TD/prediction_realistic3.bioboxes" test1 direct

echo "== COMPARATIVE_ANALYSIS test data (OPAL run on realistic predictions)"
CA_TD="$ROOT/modules/local/comparative_analysis/testdata"
cp "$TD/gold_standard.bioboxes" "$CA_TD/gold_standard.bioboxes"
cp "$TD/gold_standard_realistic.bioboxes" "$CA_TD/gold_standard_realistic.bioboxes"
rm -rf "$CA_TD/opal_results_realistic" "$CA_TD/bioboxes_realistic"
mkdir -p "$CA_TD/bioboxes_realistic"
cp "$OPAL_TD/prediction_realistic1.bioboxes" "$CA_TD/bioboxes_realistic/test1_kraken2.bioboxes"
cp "$OPAL_TD/prediction_realistic2.bioboxes" "$CA_TD/bioboxes_realistic/test1_metaphlan.bioboxes"
cp "$OPAL_TD/prediction_realistic3.bioboxes" "$CA_TD/bioboxes_realistic/test1_centrifuge.bioboxes"
opal.py -g "$TD/gold_standard_realistic.bioboxes" -o "$CA_TD/opal_results_realistic" \
    -l "test1_kraken2,test1_metaphlan,test1_centrifuge" \
    "$CA_TD/bioboxes_realistic/test1_kraken2.bioboxes" \
    "$CA_TD/bioboxes_realistic/test1_metaphlan.bioboxes" \
    "$CA_TD/bioboxes_realistic/test1_centrifuge.bioboxes" > "$WORK/opal.log" 2>&1 || { cat "$WORK/opal.log"; exit 1; }
# keep the fixture small: metrics tables only
find "$CA_TD/opal_results_realistic" -type f ! -name '*.tsv' -delete
find "$CA_TD/opal_results_realistic" -type d -empty -delete
printf 'tool\trank\tmetric\tsample\tvalue\n' > "$CA_TD/opal_results/results.tsv"

echo "== done"
