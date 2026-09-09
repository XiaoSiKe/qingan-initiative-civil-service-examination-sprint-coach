#!/usr/bin/env python3
"""Build a deterministic plugin ZIP and checksum."""

import hashlib
import json
import sys
import zipfile
from pathlib import Path


EXCLUDED_PARTS = {"__pycache__", "tests", "evals", ".pytest_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def included(path, root):
    relative = path.relative_to(root)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    if path.suffix in EXCLUDED_SUFFIXES:
        return False
    return path.is_file()


def build(output=None):
    plugin_root = Path(__file__).resolve().parents[1]
    repo_root = Path(__file__).resolve().parents[3]
    with (plugin_root / "plugin.json").open("r", encoding="utf-8") as handle:
        version = json.load(handle)["version"]
    dist = repo_root / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    slug = "qingan-initiative-civil-service-examination-sprint-coach"
    archive = Path(output).resolve() if output else dist / ("%s-v%s.zip" % (slug, version))
    archive.parent.mkdir(parents=True, exist_ok=True)
    prefix = slug
    with zipfile.ZipFile(str(archive), "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(plugin_root.rglob("*")):
            if not included(path, plugin_root):
                continue
            relative = path.relative_to(plugin_root).as_posix()
            info = zipfile.ZipInfo(prefix + "/" + relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if path.suffix == ".py" else 0o644) << 16
            bundle.writestr(info, path.read_bytes())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum = archive.parent / "SHA256SUMS.txt"
    checksum.write_text("%s  %s\n" % (digest, archive.name), encoding="utf-8")
    return archive, checksum, digest


if __name__ == "__main__":
    archive_path, checksum_path, sha256 = build(sys.argv[1] if len(sys.argv) > 1 else None)
    print(json.dumps({"archive": str(archive_path), "checksum": str(checksum_path), "sha256": sha256}, indent=2))
