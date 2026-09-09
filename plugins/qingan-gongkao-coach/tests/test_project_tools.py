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
        self.assertEqual(len(registry["sources"]), 10)

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
            self.assertIn("qingan-gongkao-coach/plugin.json", names)
            self.assertIn("qingan-gongkao-coach/skills/qingan-gongkao-coach/SKILL.md", names)
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
