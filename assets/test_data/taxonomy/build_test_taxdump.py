#!/usr/bin/env python3
"""Build a reduced NCBI-style taxdump (nodes.dmp/names.dmp/merged.dmp) for taxbencher tests.

Sources:
  * lineages recorded in existing bioboxes fixtures (TAXPATH + TAXPATHSN + RANK)
  * a small hand-curated table for taxa that appear in test inputs but not in fixtures
Only taxa reachable from the test inputs (plus their ancestors) are kept.
"""
import sys, tarfile, io, pathlib

S = pathlib.Path(sys.argv[1])          # scratch dir containing realistic_nodes.tsv and needed.txt
OUT = pathlib.Path(sys.argv[2])        # output directory for taxdump files

nodes = {}   # taxid -> dict(parent, name, rank)
for line in (S / "realistic_nodes.tsv").read_text().splitlines():
    tid, parent, name, rank = line.split("\t")
    tid = int(tid)
    parent = int(parent) if parent else 1
    d = nodes.setdefault(tid, {"parent": parent, "name": name, "rank": ""})
    if rank and not d["rank"]:
        d["rank"] = rank

# Hand-curated additions / rank fixes (taxid: (parent, name, rank))
curated = {
    1: (1, "root", "no rank"),
    131567: (1, "cellular organisms", "no rank"),
    2: (131567, "Bacteria", "superkingdom"),
    2157: (131567, "Archaea", "superkingdom"),
    3379134: (2, "Pseudomonadati", "kingdom"),
    1783272: (2, "Bacillati", "kingdom"),
    3366610: (2157, "Methanobacteriati", "kingdom"),
    28890: (3366610, "Methanobacteriota", "phylum"),
    2283794: (28890, "Methanomada group", "clade"),
    183925: (2283794, "Methanobacteria", "class"),
    2158: (183925, "Methanobacteriales", "order"),
    2159: (2158, "Methanobacteriaceae", "family"),
    2172: (2159, "Methanobrevibacter", "genus"),
    2173: (2172, "Methanobrevibacter smithii", "species"),
    561: (543, "Escherichia", "genus"),
    90964: (1385, "Staphylococcaceae", "family"),
    135617: (72273, "Thiotrichaceae", "family"),
    954: (262, "Francisella persica", "species"),
    2610885: (262, "unclassified Francisella", "no rank"),
    # Enterococcus faecalis lineage
    186826: (91061, "Lactobacillales", "order"),
    81852: (186826, "Enterococcaceae", "family"),
    1350: (81852, "Enterococcus", "genus"),
    1351: (1350, "Enterococcus faecalis", "species"),
    # Burkholderia pseudomallei K96243 lineage
    28216: (1224, "Betaproteobacteria", "class"),
    80840: (28216, "Burkholderiales", "order"),
    119060: (80840, "Burkholderiaceae", "family"),
    32008: (119060, "Burkholderia", "genus"),
    111527: (32008, "pseudomallei group", "species group"),
    28450: (111527, "Burkholderia pseudomallei", "species"),
    272631: (28450, "Burkholderia pseudomallei K96243", "strain"),
}
for tid, (parent, name, rank) in curated.items():
    nodes[tid] = {"parent": parent, "name": name, "rank": rank}

needed = {int(x) for x in (S / "needed.txt").read_text().split()}
needed |= set(curated)
needed.discard(0)

keep = set()
missing = []
for tid in sorted(needed):
    if tid not in nodes:
        missing.append(tid)
        continue
    t = tid
    while True:
        keep.add(t)
        if t == 1:
            break
        p = nodes[t]["parent"]
        if p not in nodes:
            raise SystemExit(f"parent {p} of {t} unknown")
        t = p

print("intentionally unresolved taxids:", missing)
norank = [t for t in sorted(keep) if not nodes[t]["rank"]]
for t in norank:
    nodes[t]["rank"] = "no rank"
print("nodes kept:", len(keep), "| nodes defaulted to 'no rank':", [(t, nodes[t]['name']) for t in norank])

OUT.mkdir(parents=True, exist_ok=True)
with open(OUT / "nodes.dmp", "w") as fn, open(OUT / "names.dmp", "w") as fm:
    for t in sorted(keep):
        n = nodes[t]
        fn.write(f"{t}\t|\t{n['parent']}\t|\t{n['rank']}\t|\t\t|\t0\t|\t0\t|\t1\t|\t0\t|\t0\t|\t0\t|\t0\t|\t0\t|\t\t|\n")
        fm.write(f"{t}\t|\t{n['name']}\t|\t\t|\tscientific name\t|\n")
open(OUT / "merged.dmp", "w").close()
open(OUT / "delnodes.dmp", "w").close()
with tarfile.open(OUT / "taxdump.tar.gz", "w:gz") as tar:
    for f in ["nodes.dmp", "names.dmp", "merged.dmp", "delnodes.dmp"]:
        tar.add(OUT / f, arcname=f)
print("wrote", OUT / "taxdump.tar.gz")
