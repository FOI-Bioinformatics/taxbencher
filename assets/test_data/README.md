# Test data

All test inputs are small, synthetic profiles restricted to a handful of taxa.

| Path | Used by | Content |
|------|---------|---------|
| `samplesheet_test.csv`, `taxpasta/sample*_*.tsv` | `-profile test` | Three pre-standardised taxpasta profiles (Francisellaceae) for one sample `test_sample` |
| `samplesheet_test_raw.csv`, `profiler_outputs/` | `-profile test_raw` | Raw Kraken2 / Centrifuge / MetaPhlAn outputs for `test_sample` (E. coli, S. aureus, B. pseudomallei, M. smithii) |
| `samplesheet_realistic.csv`, `taxpasta/realistic_*.tsv` | `-profile test_realistic` | Larger profiles (~50 taxa incl. strains) for sample `test1` |
| `gold_standard.bioboxes` | `test` | Truth for `test_sample` (Francisellaceae composition) |
| `gold_standard_raw.bioboxes` | `test_raw` | Truth for `test_sample` matching the raw profiler outputs |
| `gold_standard_realistic.bioboxes` | `test_realistic` | Truth for `test1` |
| `truth/*.tsv` | fixture generation | Species/strain level compositions the gold standards are derived from |
| `taxonomy/taxdump.tar.gz` | all profiles | Reduced NCBI taxonomy, see `taxonomy/README.md` |

## Regenerating the gold standards

The gold standards are proper CAMI profiles: every rank sums to 100 % and `TAXPATH`
holds one taxonomy ID per rank of `@Ranks`. They are derived from the species/strain
level truth tables with the pipeline's own helper script and the reduced taxonomy:

```bash
python3 bin/fix_gold_standard.py -i assets/test_data/truth/truth_test1.tsv \
    -o assets/test_data/gold_standard_realistic.bioboxes \
    --taxdump assets/test_data/taxonomy/taxdump.tar.gz --fill-higher-ranks
```

`bin/regenerate_test_fixtures.sh` runs this for all three gold standards and also
rebuilds the module test fixtures under `modules/local/*/testdata/` (converted
profiles and OPAL results).
