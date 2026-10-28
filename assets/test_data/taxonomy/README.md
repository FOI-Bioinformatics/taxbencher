# Reduced NCBI taxonomy for tests

`taxdump.tar.gz` is a **reduced** NCBI-style taxonomy dump (`nodes.dmp`, `names.dmp`,
empty `merged.dmp`/`delnodes.dmp`) containing only the ~80 taxa that occur in the
bundled test data (Francisellaceae, a few Enterobacterales/Bacillales/Burkholderiales
species, Methanobacteriaceae) and their ancestors.

It exists so that the test profiles and the module tests can be run **offline and
reproducibly**: `ete3` otherwise downloads the live NCBI taxonomy (~60 MB, changing
weekly) on first use, which makes snapshot tests non-deterministic and fails on
machines without internet access.

Two taxonomy IDs present in the realistic Kraken2 test profile (`1001542`, `1341656`)
are intentionally **absent** so that the "taxid not found in taxonomy" code path is
exercised (they carry one read each).

Do **not** use this archive for real analyses. For production runs download the full
dump from <https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz> (or a dated
archive from `taxdump_archive/`) and pass it with `--taxdump`.

`build_test_taxdump.py` documents how the archive was assembled from the lineages
recorded in the earlier test fixtures plus a small hand curated table; it is kept for
provenance and is not used by the pipeline.
