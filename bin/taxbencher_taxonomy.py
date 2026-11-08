#!/usr/bin/env python3
"""
NCBI-format taxonomy lookups shared by taxbencher's scripts.

Lineages are resolved with taxopy (the library taxpasta itself uses) from the
``nodes.dmp``/``names.dmp``/``merged.dmp`` files of an NCBI taxdump. A taxdump can be
given as an extracted directory or as an archive (``taxdump.tar.gz``, ``.tgz``, ``.tar``
or a dated ``taxdmp_YYYY-MM-DD.zip``); archives are extracted once.

Merged taxonomy IDs (``merged.dmp``) are translated to their current ID before the
lineage is built, so an outdated ID in a profile ends up on the same node as the
current ID in the gold standard. taxopy itself keeps the old ID as the leaf of the
lineage, which would make OPAL count the taxon as a false positive.

Command line (used by the PREPARE_TAXDUMP module)::

    taxbencher_taxonomy.py extract taxdump.tar.gz taxdump/
"""

import argparse
import logging
import shutil
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

__version__ = "1.0.0"

REQUIRED_DMP = ("nodes.dmp", "names.dmp")
OPTIONAL_DMP = ("merged.dmp",)

PathLike = Union[str, Path]


class Lineage:
    """Ordered lineage from the root to the taxon itself: lists of taxids, ranks, names."""

    __slots__ = ("taxids", "ranks", "names")

    def __init__(self, taxids: Sequence[int], ranks: Sequence[str], names: Sequence[str]):
        self.taxids = list(taxids)
        self.ranks = list(ranks)
        self.names = list(names)


def extract_taxdump(archive: PathLike, dest: PathLike) -> Path:
    """Extract nodes.dmp, names.dmp and (if present) merged.dmp from a taxdump archive.

    Members are matched by file name, so archives with a top-level directory work too.
    A missing merged.dmp is written as an empty file. Returns the destination directory.
    """
    archive, dest = Path(archive), Path(dest)
    if not archive.is_file():
        raise FileNotFoundError(f"taxdump archive not found: {archive}")
    dest.mkdir(parents=True, exist_ok=True)
    wanted = set(REQUIRED_DMP + OPTIONAL_DMP)
    found = set()
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            for member in zf.infolist():
                name = Path(member.filename).name
                if member.is_dir() or name not in wanted or name in found:
                    continue
                with zf.open(member) as src, open(dest / name, "wb") as out:
                    shutil.copyfileobj(src, out)
                found.add(name)
    elif tarfile.is_tarfile(archive):
        with tarfile.open(archive) as tf:
            for member in tf:
                name = Path(member.name).name
                if not member.isfile() or name not in wanted or name in found:
                    continue
                src = tf.extractfile(member)
                with src, open(dest / name, "wb") as out:
                    shutil.copyfileobj(src, out)
                found.add(name)
    else:
        raise ValueError(f"{archive} is neither a tar nor a zip archive")
    missing = [name for name in REQUIRED_DMP if name not in found]
    if missing:
        raise ValueError(f"{archive} does not contain {', '.join(missing)}")
    for name in OPTIONAL_DMP:
        if name not in found:
            (dest / name).touch()
    return dest


def taxdump_dir(taxdump: PathLike, workdir: Optional[PathLike] = None) -> Path:
    """Return a directory holding the .dmp files: the path itself or an extracted archive."""
    taxdump = Path(taxdump)
    if taxdump.is_dir():
        missing = [name for name in REQUIRED_DMP if not (taxdump / name).is_file()]
        if missing:
            raise FileNotFoundError(f"taxdump directory {taxdump} lacks {', '.join(missing)}")
        return taxdump
    dest = Path(workdir or Path.cwd()) / "taxdump_extracted"
    logging.info(f"Extracting {taxdump} to {dest}")
    return extract_taxdump(taxdump, dest)


class TaxonomyResolver:
    """Resolve taxonomy IDs to root-first lineages with taxopy."""

    def __init__(self, taxdump: Optional[PathLike] = None, workdir: Optional[PathLike] = None):
        try:
            import taxopy  # noqa: WPS433
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise RuntimeError(
                "taxopy is required for taxonomy lookups (conda install -c bioconda taxopy)"
            ) from exc
        self._taxopy = taxopy
        if taxdump is None:
            target = Path(workdir or Path.cwd()) / "taxdump_download"
            logging.warning(
                "No taxdump given: downloading the current NCBI taxonomy to %s. "
                "Results then depend on the download date; pass --taxdump for reproducible runs.",
                target,
            )
            self._db = taxopy.TaxDb(taxdb_dir=str(target), keep_files=True)
        else:
            directory = taxdump_dir(taxdump, workdir)
            merged = directory / "merged.dmp"
            logging.info(f"Loading NCBI taxonomy from {directory}")
            self._db = taxopy.TaxDb(
                nodes_dmp=str(directory / "nodes.dmp"),
                names_dmp=str(directory / "names.dmp"),
                merged_dmp=str(merged) if merged.is_file() and merged.stat().st_size else None,
                keep_files=True,
            )
        self._merged: Dict[int, int] = dict(getattr(self._db, "oldtaxid2newtaxid", None) or {})
        self._cache: Dict[int, Optional[Lineage]] = {}

    def current_taxid(self, taxid: int) -> int:
        """Translate a merged (outdated) taxonomy ID to its current ID."""
        return self._merged.get(taxid, taxid)

    def resolve(self, taxid: int) -> Optional[Lineage]:
        """Lineage of ``taxid`` (root first), or None for unknown or deleted IDs."""
        if taxid in self._cache:
            return self._cache[taxid]
        current = self.current_taxid(taxid)
        if current != taxid:
            logging.info(f"taxid {taxid} was merged into {current}; using {current}")
        try:
            taxon = self._taxopy.Taxon(current, self._db)
        except self._taxopy.exceptions.TaxidError as exc:
            logging.debug(f"taxid {taxid} not found in taxonomy: {exc}")
            self._cache[taxid] = None
            return None
        # taxopy lineages run from the taxon to the root
        lineage = Lineage(
            list(reversed(taxon.taxid_lineage)),
            list(reversed(taxon.rank_lineage)),
            list(reversed(taxon.name_lineage)),
        )
        self._cache[taxid] = lineage
        return lineage


def _format_lineage(lineage: Lineage) -> List[str]:
    return [f"{t}:{r}:{n}" for t, r, n in zip(lineage.taxids, lineage.ranks, lineage.names)]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="taxbencher taxonomy helpers")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    extract = sub.add_parser("extract", help="Extract nodes/names/merged.dmp from a taxdump archive")
    extract.add_argument("archive", type=Path, help="taxdump.tar.gz, .tgz, .tar or taxdmp_*.zip")
    extract.add_argument("outdir", type=Path, help="Directory to write the .dmp files to")
    lookup = sub.add_parser("lineage", help="Print the lineage of taxonomy IDs")
    lookup.add_argument("taxdump", type=Path, help="Extracted taxdump directory or archive")
    lookup.add_argument("taxids", type=int, nargs="+")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

    try:
        if args.command == "extract":
            directory = extract_taxdump(args.archive, args.outdir)
            print(f"Extracted {', '.join(sorted(p.name for p in directory.glob('*.dmp')))} to {directory}")
        else:
            resolver = TaxonomyResolver(args.taxdump)
            for taxid in args.taxids:
                lineage = resolver.resolve(taxid)
                print(f"{taxid}\t" + ("NA" if lineage is None else " > ".join(_format_lineage(lineage))))
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
