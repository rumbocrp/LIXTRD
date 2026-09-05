"""Guardas estructurales exigidas por SPEC-001 y SRS para Gate G-R1 (RNF-L001, RNF-L002, RNF-L011)."""

import importlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import tomllib
import types
import unittest
import zipfile

from tests.architecture.policy_check import scan_repository
from tests.conftest import REPO_ROOT


EXPECTED_ROOT_EXPORTS = {
    "consultar_vista",
    "ejecutar_replay",
    "ejecutar_shadow",
    "importar_demo_observada",
}
EXPECTED_CAPABILITIES = {
    "account_metadata.read",
    "historical_executions.read",
    "market_data.read",
}
EXPECTED_RUNTIME_DEPENDENCIES = {
    "beautifulsoup4",
    "certifi",
    "cffi",
    "charset-normalizer",
    "curl-cffi",
    "idna",
    "lxml",
    "multitasking",
    "numpy",
    "pandas",
    "peewee",
    "platformdirs",
    "protobuf",
    "pycparser",
    "python-dateutil",
    "pytz",
    "requests",
    "six",
    "soupsieve",
    "typing-extensions",
    "tzdata",
    "urllib3",
    "websockets",
    "yfinance",
}
EXPECTED_IMPORT_ROOTS = {"yfinance"}


class RootApiTests(unittest.TestCase):
    def test_root_api_exports_exactly_four_use_cases(self) -> None:
        package = importlib.import_module("sistema_luces")
        public_names = {
            name
            for name, value in vars(package).items()
            if not name.startswith("_") and not isinstance(value, types.ModuleType)
        }

        self.assertEqual(EXPECTED_ROOT_EXPORTS, public_names)
        self.assertEqual(EXPECTED_ROOT_EXPORTS, set(package.__all__))
        self.assertTrue(all(callable(getattr(package, name)) for name in package.__all__))


class SecurityPolicyTests(unittest.TestCase):
    def test_security_policy_has_exact_read_only_allowlists(self) -> None:
        policy_path = REPO_ROOT / "config" / "security-policy-v1.json"
        policy = json.loads(policy_path.read_text(encoding="utf-8"))

        self.assertEqual("sistema-luces/security-policy-v1", policy["schema_id"])
        self.assertEqual(1, policy["version"])
        self.assertEqual(EXPECTED_ROOT_EXPORTS, set(policy["allowed_root_exports"]))
        self.assertEqual(EXPECTED_CAPABILITIES, set(policy["allowed_capabilities"]))
        self.assertEqual(EXPECTED_RUNTIME_DEPENDENCIES, set(policy["allowed_runtime_dependencies"]))
        self.assertEqual(EXPECTED_IMPORT_ROOTS, set(policy["allowed_import_roots"]))
        self.assertEqual([], policy["allowed_cli_commands"])
        self.assertEqual([], policy["allowed_http_methods"])


class ReproducibilityTests(unittest.TestCase):
    def test_python_runtime_and_yfinance_lock_are_fixed(self) -> None:
        with (REPO_ROOT / "pyproject.toml").open("rb") as stream:
            project_config = tomllib.load(stream)
        with (REPO_ROOT / "uv.lock").open("rb") as stream:
            lock = tomllib.load(stream)

        self.assertEqual("==3.11.*", project_config["project"]["requires-python"])
        self.assertEqual(["yfinance>=1.7.0"], project_config["project"]["dependencies"])
        self.assertEqual("3.11.16", project_config["tool"]["sistema-luces"]["python-runtime"])
        self.assertEqual("3.53.1", project_config["tool"]["sistema-luces"]["sqlite-runtime"])
        self.assertEqual("3.11.16", sys.version.split()[0])
        self.assertEqual("3.53.1", sqlite3.sqlite_version)
        self.assertEqual("3.11.16", (REPO_ROOT / ".python-version").read_text().strip())
        self.assertEqual("==3.11.*", lock["requires-python"])
        locked_dependencies = {
            package["name"] for package in lock["package"] if package["name"] != "sistema-luces"
        }
        self.assertEqual(EXPECTED_RUNTIME_DEPENDENCIES, locked_dependencies)
        root_package = next(package for package in lock["package"] if package["name"] == "sistema-luces")
        self.assertEqual({"yfinance"}, {item["name"] for item in root_package.get("dependencies", [])})

    def test_single_local_verification_command_is_documented(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
        gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")

        self.assertEqual(1, readme.count("`make verify`"))
        self.assertEqual(1, sum(line == "verify:" for line in makefile.splitlines()))
        self.assertIn("uv lock", makefile)
        self.assertIn("-m unittest", makefile)
        self.assertIn("-m compileall", makefile)
        self.assertIn("-m tabnanny", makefile)
        self.assertIn("__pycache__/", gitignore.splitlines())
        self.assertIn(".venv/", gitignore.splitlines())

    def test_verify_uses_only_repository_local_cache_and_temporary_paths(self) -> None:
        environment = os.environ.copy()
        environment.pop("UV_CACHE_DIR", None)
        environment["HOME"] = "/nonexistent-wp00-home"

        rendered = subprocess.run(
            ["make", "-n", "verify"],
            cwd=REPO_ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, rendered.returncode, rendered.stderr)
        local_cache = f"UV_CACHE_DIR={REPO_ROOT / '.cache' / 'uv'}" in rendered.stdout
        cacheless_offline_check = "uv lock" not in rendered.stdout
        self.assertTrue(local_cache or cacheless_offline_check, rendered.stdout)
        self.assertNotIn("/nonexistent-wp00-home", rendered.stdout)


def _write_probe_repository(root: Path) -> None:
    package_root = root / "src" / "sistema_luces"
    config_root = root / "config"
    package_root.mkdir(parents=True)
    config_root.mkdir()
    (package_root / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    (config_root / "security-policy-v1.json").write_text(
        json.dumps(
            {
                "schema_id": "sistema-luces/security-policy-v1",
                "version": 1,
                "allowed_capabilities": sorted(EXPECTED_CAPABILITIES),
                "allowed_cli_commands": [],
                "allowed_http_methods": [],
                "allowed_import_roots": [],
                "allowed_root_exports": sorted(EXPECTED_ROOT_EXPORTS),
                "allowed_runtime_dependencies": [],
            }
        ),
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(
        '[project]\nname = "sistema-luces"\nversion = "0.0.0"\n'
        'requires-python = "==3.11.*"\ndependencies = []\n',
        encoding="utf-8",
    )
    (root / "uv.lock").write_text(
        'version = 1\nrevision = 3\nrequires-python = "==3.11.*"\n\n'
        '[[package]]\nname = "sistema-luces"\nversion = "0.0.0"\n'
        'source = { virtual = "." }\n',
        encoding="utf-8",
    )


class ArchitectureGuardTests(unittest.TestCase):
    def test_current_repository_satisfies_security_policy(self) -> None:
        self.assertEqual((), scan_repository(REPO_ROOT))

    def test_forbidden_mutations_turn_architecture_check_red(self) -> None:
        probes = (
            ("source_live", "src/sistema_luces/probe.py", 'ENVIRONMENT = "LIVE"\n', "FORBIDDEN_LIVE"),
            ("order_gateway", "src/sistema_luces/probe.py", "class OrderGateway: pass\n", "FORBIDDEN_ORDER_CAPABILITY"),
            ("order_symbol", "src/sistema_luces/probe.py", "def place_order(): pass\n", "FORBIDDEN_ORDER_CAPABILITY"),
            ("delete_order_symbol", "src/sistema_luces/probe.py", "def delete_order(): pass\n", "FORBIDDEN_ORDER_CAPABILITY"),
            ("execute_order_symbol", "src/sistema_luces/probe.py", "def execute_order(): pass\n", "FORBIDDEN_ORDER_CAPABILITY"),
            ("new_order_symbol", "src/sistema_luces/probe.py", "def new_order(): pass\n", "FORBIDDEN_ORDER_CAPABILITY"),
            ("order_router_class", "src/sistema_luces/probe.py", "class OrderRouter: pass\n", "FORBIDDEN_ORDER_CAPABILITY"),
            ("order_manager_class", "src/sistema_luces/probe.py", "class OrderManager: pass\n", "FORBIDDEN_ORDER_CAPABILITY"),
            ("trade_execution_func", "src/sistema_luces/probe.py", "def trade_execution(): pass\n", "FORBIDDEN_ORDER_CAPABILITY"),
            ("close_all_positions_func", "src/sistema_luces/probe.py", "def close_all_positions(): pass\n", "FORBIDDEN_ORDER_CAPABILITY"),
            ("non_loopback_bind_zero", "scripts/serve.py", 'host = "0.0.0.0"\n', "FORBIDDEN_NON_LOOPBACK"),
            ("non_loopback_bind_ip", "scripts/serve.py", 'address = "192.168.1.55"\n', "FORBIDDEN_NON_LOOPBACK"),
            ("private_key_leak", "config/creds.pem", "-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n", "SECRET_LEAK_DETECTED"),
            ("api_key_leak", "config/api.json", '{"api_key": "sk-secret-1234567890abcdef"}\n', "SECRET_LEAK_DETECTED"),
            ("local_users_path", "config/path.json", '{"dir": "/Users/testuser/data"}\n', "FORBIDDEN_LOCAL_PATH"),
            ("local_home_path", "config/path.json", '{"dir": "/home/testuser/data"}\n', "FORBIDDEN_LOCAL_PATH"),
            ("write_scope", "config/source.json", '{"scope":"account.write"}\n', "FORBIDDEN_WRITE_SCOPE"),
            ("journal_database", "config/source.json", '{"path":"tj.db"}\n', "FORBIDDEN_JOURNAL_DATABASE"),
            ("prototype_import", "src/sistema_luces/probe.py", "import trading_bot\n", "FORBIDDEN_REPOSITORY_IMPORT"),
            ("journal_import", "src/sistema_luces/probe.py", "import trading_journal\n", "FORBIDDEN_REPOSITORY_IMPORT"),
            ("dynamic_import", "src/sistema_luces/probe.py", '__import__("trading_bot")\n', "FORBIDDEN_REPOSITORY_IMPORT"),
            (
                "dependency",
                "pyproject.toml",
                '[project]\nname = "sistema-luces"\nversion = "0.0.0"\n'
                'requires-python = "==3.11.*"\ndependencies = ["broker-sdk==1.0"]\n',
                "FORBIDDEN_DEPENDENCY",
            ),
            (
                "transitive_dependency",
                "uv.lock",
                'version = 1\nrevision = 3\nrequires-python = "==3.11.*"\n\n'
                '[[package]]\nname = "sistema-luces"\nversion = "0.0.0"\n'
                'source = { virtual = "." }\ndependencies = [{ name = "broker-sdk" }]\n\n'
                '[[package]]\nname = "broker-sdk"\nversion = "1.0.0"\n'
                'source = { registry = "https://example.invalid/simple" }\n',
                "FORBIDDEN_DEPENDENCY",
            ),
        )

        for name, relative_path, contents, expected_code in probes:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                _write_probe_repository(root)
                target = root / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(contents, encoding="utf-8")

                violations = scan_repository(root)

                self.assertTrue(any(expected_code in violation for violation in violations), f"Probe '{name}' failed: {violations}")

    def test_legitimate_order_microstructure_terms_are_allowed(self) -> None:
        """Verifica que términos legítimos (order_imbalance, order_flow, out_of_order, ORDER BY) no causen falsos positivos."""
        legitimate_code = """
def calcular_order_imbalance(bid_vol: int, ask_vol: int) -> float:
    return (bid_vol - ask_vol) / max(1, bid_vol + ask_vol)

def registrar_order_flow(flow: dict) -> None:
    pass

class OutOfOrderHandler:
    def handle_out_of_order(self, ev: dict) -> None:
        query = "SELECT * FROM events ORDER BY event_id ASC"
"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_probe_repository(root)
            target = root / "src" / "sistema_luces" / "microstructure.py"
            target.write_text(legitimate_code, encoding="utf-8")

            violations = scan_repository(root)
            self.assertEqual((), violations, f"Falsos positivos detectados: {violations}")

    def test_distribution_symbol_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_probe_repository(root)
            distribution = root / "dist" / "probe.whl"
            distribution.parent.mkdir()
            with zipfile.ZipFile(distribution, "w") as archive:
                archive.writestr("sistema_luces/hidden.py", "class ExecutionClient: pass\n")

            violations = scan_repository(root)

            self.assertTrue(
                any("FORBIDDEN_ORDER_CAPABILITY" in violation for violation in violations),
                violations,
            )


if __name__ == "__main__":
    unittest.main()
