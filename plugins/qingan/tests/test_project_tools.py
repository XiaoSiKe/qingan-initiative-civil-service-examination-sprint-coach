import hashlib
import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProjectToolTests(unittest.TestCase):
    def test_offline_upstream_registry_validation(self):
        module = load_module("check_upstreams", PLUGIN_ROOT / "scripts" / "check_upstreams.py")
        registry = module.load_registry(PLUGIN_ROOT / "sources" / "upstreams.json")
        self.assertEqual(len(registry["sources"]), 12)

    def test_huasheng13_remains_concept_only_and_routes_through_qingan(self):
        registry = json.loads((PLUGIN_ROOT / "sources" / "upstreams.json").read_text(encoding="utf-8"))
        source = next(item for item in registry["sources"] if item["repo"] == "WangJunqing-coder/huasheng13-skill")
        self.assertEqual(source["pinned_sha"], "6a43d776741f69a231eb2d75f9d5d59efe870659")
        self.assertEqual((source["license"], source["mode"]), ("NONE", "concept-only"))
        skill_root = PLUGIN_ROOT / "skills" / "qingan-initiative-civil-service-examination-sprint-coach"
        skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        integration = (skill_root / "references" / "integration-map.md").read_text(encoding="utf-8")
        self.assertIn("rapid-calculation.md", skill_text)
        self.assertIn("gongkao-huasheng13", integration)
        self.assertIn("已安装", integration)

    def test_new_mit_zero_source_is_pinned_and_scope_limited(self):
        registry = json.loads((PLUGIN_ROOT / "sources" / "upstreams.json").read_text(encoding="utf-8"))
        source = next(item for item in registry["sources"] if item["repo"] == "Zhaojixu/shangan-gongkao")
        self.assertEqual(source["pinned_sha"], "5f2c6f0d6b29a5b86a9e29f9569a2de102779e96")
        self.assertEqual(source["license"], "MIT-0")
        self.assertEqual(source["used_for"], ["multi-window-planning", "material-role-classification"])

    def test_focus_source_remains_concept_only_without_a_license_file(self):
        registry = json.loads((PLUGIN_ROOT / "sources" / "upstreams.json").read_text(encoding="utf-8"))
        source = next(item for item in registry["sources"] if item["repo"] == "cxs885187-create/--skill")
        self.assertEqual(source["pinned_sha"], "aa0467bd848ce40000e0bdd80667d4f24d946bc3")
        self.assertEqual(source["license"], "NONE")
        self.assertEqual(source["mode"], "concept-only")
        self.assertIn("frustration-fuse", source["used_for"])

    def test_release_build_is_reproducible_and_clean(self):
        module = load_module("build_release", PLUGIN_ROOT / "scripts" / "build_release.py")
        with tempfile.TemporaryDirectory() as temp:
            first = Path(temp) / "first.zip"
            second = Path(temp) / "second.zip"
            module.build(first)
            module.build(second)
            self.assertEqual(hashlib.sha256(first.read_bytes()).hexdigest(), hashlib.sha256(second.read_bytes()).hexdigest())
            with zipfile.ZipFile(str(first)) as archive:
                names = archive.namelist()
            prefix = "qingan-initiative-civil-service-examination-sprint-coach"
            self.assertIn(prefix + "/plugin.json", names)
            skill_files = [name for name in names if name.endswith("/SKILL.md")]
            self.assertEqual(skill_files, [prefix + "/skills/" + prefix + "/SKILL.md"])
            self.assertIn(prefix + "/skills/" + prefix + "/references/resilience-protocol.md", names)
            self.assertIn(prefix + "/skills/" + prefix + "/references/life-adapters.md", names)
            self.assertIn(prefix + "/skills/" + prefix + "/references/learning-and-strategy.md", names)
            self.assertIn(prefix + "/skills/" + prefix + "/references/communication.md", names)
            self.assertIn(prefix + "/skills/" + prefix + "/references/efficiency.md", names)
            self.assertIn(prefix + "/skills/" + prefix + "/references/application.md", names)
            self.assertIn(prefix + "/skills/" + prefix + "/references/interview.md", names)
            self.assertIn(prefix + "/skills/" + prefix + "/references/rapid-calculation.md", names)
            self.assertFalse(any("/tests/" in name or "__pycache__" in name or name.endswith(".pyc") for name in names))
            self.assertFalse(any(".qingan-data" in name for name in names))

    def test_manifest_versions_match_changelog(self):
        portable = json.loads((PLUGIN_ROOT / "plugin.json").read_text(encoding="utf-8"))
        fallback = json.loads((PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        changelog = (PLUGIN_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertEqual(portable, fallback)
        self.assertIn("## %s" % portable["version"], changelog)


if __name__ == "__main__":
    unittest.main()
