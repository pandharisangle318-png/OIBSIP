import ast
import json
import py_compile
import re
import unittest

from tests.helpers import ROOT

REQUIRED = [
    "main.py", "requirements.txt", "README.md", ".env.example", ".gitignore", "LICENSE", "config.json",
    "setup.bat", "run.bat", "test.bat", "diagnose.bat", "tools/diagnose.py",
    "gui/__init__.py", "gui/main_window.py", "gui/workers.py", "gui/styles.py",
    "core/__init__.py", "core/assistant.py", "core/listener.py", "core/text_to_speech.py", "core/nlp.py",
    "core/command_handler.py", "core/config.py", "core/voice_session.py",
    "features/__init__.py", "features/email_service.py", "features/weather_service.py", "features/search_service.py",
    "features/reminder_service.py", "features/joke_service.py", "features/custom_commands.py",
    "data/knowledge_base.json", "data/custom_commands.json",
    "docs/DEMO_VIDEO_SCRIPT.md", "docs/LINKEDIN_POST.md", "docs/SUBMISSION_CHECKLIST.md",
]


class ProjectFileTests(unittest.TestCase):
    def test_required_files_exist(self):
        """Every file the README and scripts refer to exists."""
        for rel in REQUIRED:
            with self.subTest(file=rel):
                self.assertTrue((ROOT / rel).is_file(), rel)

    def test_all_python_files_compile(self):
        """Every Python file compiles (syntax check)."""
        for path in ROOT.rglob("*.py"):
            if ".venv" in path.parts or "__pycache__" in path.parts:
                continue
            with self.subTest(file=str(path.relative_to(ROOT))):
                py_compile.compile(str(path), doraise=True, cfile=str(ROOT / "logs" / "_tmp.pyc"))
        (ROOT / "logs" / "_tmp.pyc").unlink(missing_ok=True)

    def test_internal_imports_resolve(self):
        """Every 'core.*', 'features.*', 'gui.*' import in the source points to a real module."""
        for path in ROOT.rglob("*.py"):
            if ".venv" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    names.append(node.module)
                elif isinstance(node, ast.Import):
                    names.extend(a.name for a in node.names)
                for name in names:
                    if name.split(".")[0] in ("core", "features", "gui", "tools"):
                        rel = ROOT.joinpath(*name.split("."))
                        self.assertTrue(rel.with_suffix(".py").exists() or (rel / "__init__.py").exists(),
                                        f"{path.name}: unresolved import {name}")

    def test_json_files_valid(self):
        """All shipped JSON files parse."""
        for rel in ("config.json", "data/knowledge_base.json", "data/custom_commands.json"):
            json.loads((ROOT / rel).read_text(encoding="utf-8"))

    def test_knowledge_base_entries_complete(self):
        """Every knowledge base topic has a name, aliases and a non-trivial answer."""
        for t in json.loads((ROOT / "data/knowledge_base.json").read_text(encoding="utf-8"))["topics"]:
            self.assertTrue(t["name"] and t["aliases"] and len(t["answer"]) > 80, t["name"])

    def test_env_example_has_placeholders_only(self):
        """.env.example lists the three variables with placeholder values only."""
        text = (ROOT / ".env.example").read_text()
        for var in ("EMAIL_ADDRESS", "EMAIL_APP_PASSWORD", "OPENWEATHER_API_KEY"):
            self.assertRegex(text, rf"(?m)^{var}=your_")

    def test_gitignore_protects_secrets(self):
        """.gitignore excludes .env, virtual environments, caches and logs."""
        text = (ROOT / ".gitignore").read_text()
        for entry in (".env", ".venv/", "__pycache__/", "logs/*.log"):
            self.assertIn(entry, text)

    def test_no_hardcoded_secrets_in_source(self):
        """No source file contains a hard-coded password / API key assignment."""
        pattern = re.compile(r"""(?i)(password|api_key|apikey|secret)\s*=\s*["'][^"']{6,}["']""")
        for path in ROOT.rglob("*.py"):
            if ".venv" in path.parts or path.parent.name == "tests":
                continue
            self.assertIsNone(pattern.search(path.read_text(encoding="utf-8")), path.name)
    def test_no_real_env_file_shipped(self):
        """No .env file with real credentials exists in the project."""
        env_path = ROOT / ".env"

        if env_path.exists():
            env_text = env_path.read_text(encoding="utf-8")

            for variable in ("EMAIL_ADDRESS", "EMAIL_APP_PASSWORD", "OPENWEATHER_API_KEY"):
                match = re.search(rf"(?m)^{variable}=(.*)$", env_text)

                if match:
                    value = match.group(1).strip()

                    self.assertTrue(
                        not value or value.lower().startswith("your_"),
                        f"{variable} contains a real value instead of a placeholder"
                    )
        
