#!/usr/bin/env python3
"""Validate and optionally check pinned GitHub upstream revisions."""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


PERMISSIVE = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "CC0-1.0", "MIT-0"}
SAFE_RESTRICTED_MODES = {"concept-only", "external-optional", "requirements-only"}


def load_registry(path):
    with path.open("r", encoding="utf-8") as handle:
        registry = json.load(handle)
    if registry.get("schema_version") != 1:
        raise ValueError("unsupported upstream registry schema")
    seen = set()
    for source in registry.get("sources", []):
        repo = source.get("repo")
        if not repo or repo in seen:
            raise ValueError("repo names must be present and unique")
        seen.add(repo)
        if not re.fullmatch(r"[0-9a-f]{40}", source.get("pinned_sha", "")):
            raise ValueError("invalid pinned_sha for %s" % repo)
        if source.get("license") not in PERMISSIVE and source.get("mode") not in SAFE_RESTRICTED_MODES:
            raise ValueError("restricted source %s cannot use mode %s" % (repo, source.get("mode")))
    return registry


def github_json(url):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "qingan-upstream-check/0.1"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def check(registry):
    changes = []
    errors = []

    def inspect(source):
        repo = source["repo"]
        try:
            commit = github_json("https://api.github.com/repos/%s/commits/HEAD" % repo)["sha"]
            metadata = github_json("https://api.github.com/repos/%s" % repo)
            remote_license = ((metadata.get("license") or {}).get("spdx_id") or "NONE")
            if commit != source["pinned_sha"] or remote_license != source["license"]:
                return "change", {
                    "repo": repo,
                    "pinned_sha": source["pinned_sha"],
                    "latest_sha": commit,
                    "recorded_license": source["license"],
                    "latest_license": remote_license,
                }
            return "ok", None
        except (KeyError, OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            return "error", {"repo": repo, "error": str(exc)}

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(inspect, source) for source in registry["sources"]]
        for future in as_completed(futures):
            kind, payload = future.result()
            if kind == "change":
                changes.append(payload)
            elif kind == "error":
                errors.append(payload)
    changes.sort(key=lambda item: item["repo"])
    errors.sort(key=lambda item: item["repo"])
    return {"changes": changes, "errors": errors}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--offline", action="store_true", help="validate only; do not access GitHub")
    parser.add_argument("--fail-on-change", action="store_true")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    registry_path = args.registry or root / "sources" / "upstreams.json"
    try:
        registry = load_registry(registry_path)
        result = {"valid": True, "source_count": len(registry["sources"]), "changes": [], "errors": []}
        if not args.offline:
            result.update(check(registry))
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        if result["errors"]:
            return 2
        if args.fail_on_change and result["changes"]:
            return 3
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
