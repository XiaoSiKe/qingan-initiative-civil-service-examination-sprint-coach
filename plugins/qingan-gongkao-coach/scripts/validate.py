#!/usr/bin/env python3
"""Repository-local validation for the Qingan plugin."""

import json
import re
import sys
from pathlib import Path


EXPECTED_SKILLS = {
    "qingan-gongkao-coach",
    "qingan-sprint-manager",
    "qingan-materials",
    "qingan-mistake-review",
    "qingan-verbal",
    "qingan-figure",
    "qingan-logic",
    "qingan-data-quant",
    "qingan-politics",
    "qingan-shenlun",
}


def require(condition, message, errors):
    if not condition:
        errors.append(message)


def frontmatter(text):
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        return {}
    values = {}
    for line in match.group(1).splitlines():
        if ":" not in line or line.startswith(" "):
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"')
    return values


def validate():
    plugin_root = Path(__file__).resolve().parents[1]
    repo_root = Path(__file__).resolve().parents[3]
    errors = []

    manifest = json.loads((plugin_root / "plugin.json").read_text(encoding="utf-8"))
    fallback = json.loads((plugin_root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    require(manifest == fallback, "portable and Codex manifests differ", errors)
    require(manifest.get("name") == "qingan-gongkao-coach", "wrong plugin name", errors)
    require(re.fullmatch(r"\d+\.\d+\.\d+", manifest.get("version", "")), "plugin version is not semver", errors)
    require(manifest.get("skills") == "./skills/", "manifest skills path must be ./skills/", errors)

    marketplace = json.loads((repo_root / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
    require(marketplace.get("name") == "qingan", "wrong marketplace name", errors)
    entries = marketplace.get("plugins", [])
    require(len(entries) == 1, "marketplace must have one plugin", errors)
    if entries:
        require(entries[0].get("name") == manifest.get("name"), "marketplace plugin name mismatch", errors)
        require(entries[0].get("source", {}).get("path") == "./plugins/qingan-gongkao-coach", "marketplace path mismatch", errors)

    skills_root = plugin_root / "skills"
    actual_skills = {path.name for path in skills_root.iterdir() if path.is_dir()}
    require(actual_skills == EXPECTED_SKILLS, "skill set mismatch: %r" % sorted(actual_skills), errors)
    descriptions = set()
    for skill_name in sorted(EXPECTED_SKILLS):
        skill_root = skills_root / skill_name
        skill_file = skill_root / "SKILL.md"
        require(skill_file.is_file(), "%s missing SKILL.md" % skill_name, errors)
        if not skill_file.is_file():
            continue
        text = skill_file.read_text(encoding="utf-8")
        meta = frontmatter(text)
        require(meta.get("name") == skill_name, "%s frontmatter name mismatch" % skill_name, errors)
        description = meta.get("description", "")
        require(len(description) >= 20, "%s description is too short" % skill_name, errors)
        require(description not in descriptions, "%s has duplicate description" % skill_name, errors)
        descriptions.add(description)
        require("[TODO:" not in text, "%s contains unfinished TODO" % skill_name, errors)
        agent_file = skill_root / "agents" / "openai.yaml"
        require(agent_file.is_file(), "%s missing agents/openai.yaml" % skill_name, errors)
        if agent_file.is_file():
            agent_text = agent_file.read_text(encoding="utf-8")
            require("$" + skill_name in agent_text, "%s default prompt must mention the skill" % skill_name, errors)
            require("allow_implicit_invocation: true" in agent_text, "%s must allow implicit invocation" % skill_name, errors)
        for link in re.findall(r"\]\(([^)#]+\.md)(?:#[^)]+)?\)", text):
            require((skill_root / link).resolve().is_file(), "%s has broken local link %s" % (skill_name, link), errors)

    registry = json.loads((plugin_root / "sources" / "upstreams.json").read_text(encoding="utf-8"))
    require(registry.get("schema_version") == 1, "unsupported source registry schema", errors)
    for source in registry.get("sources", []):
        require(re.fullmatch(r"[0-9a-f]{40}", source.get("pinned_sha", "")), "bad source SHA for %s" % source.get("repo"), errors)
        if source.get("license") in {"NONE", "GPL-3.0", "AGPL-3.0"}:
            require(source.get("mode") in {"concept-only", "external-optional"}, "restricted source mode for %s" % source.get("repo"), errors)

    scenarios = json.loads((plugin_root / "evals" / "scenarios.json").read_text(encoding="utf-8"))
    require(len(scenarios) == 40, "eval suite must contain exactly 40 scenarios", errors)
    scenario_ids = {item.get("id") for item in scenarios}
    require(len(scenario_ids) == len(scenarios), "scenario ids must be unique", errors)
    for item in scenarios:
        expected = item.get("expected_skill")
        require(expected is None or expected in EXPECTED_SKILLS, "unknown expected skill in %s" % item.get("id"), errors)
        require(bool(item.get("prompt")), "empty prompt in %s" % item.get("id"), errors)

    forbidden_suffixes = {".pdf", ".docx", ".pptx", ".mp4"}
    for path in plugin_root.rglob("*"):
        if path.is_file() and path.suffix.lower() in forbidden_suffixes:
            errors.append("binary/course artifact is not allowed: %s" % path.relative_to(plugin_root))

    if errors:
        for error in errors:
            print("ERROR: " + error, file=sys.stderr)
        return 1
    print("Validated plugin manifests, 10 skills, sources, links, and 40 eval scenarios.")
    return 0


if __name__ == "__main__":
    sys.exit(validate())
