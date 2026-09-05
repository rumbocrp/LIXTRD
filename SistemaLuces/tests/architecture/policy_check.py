"""Comprobador ejecutable de security-policy-v1 para RNF-L001, RNF-L002, RNF-L011."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import sys
import tomllib
import zipfile


_EXPECTED_CAPABILITIES = {
    "account_metadata.read",
    "historical_executions.read",
    "market_data.read",
}
_FORBIDDEN_ORDER_SYMBOLS = {
    # Operaciones directas de órdenes
    "amendorder",
    "cancelorder",
    "closeallpositions",
    "closeposition",
    "createorder",
    "deleteorder",
    "executeorder",
    "modifyorder",
    "modifyposition",
    "neworder",
    "openposition",
    "placeorder",
    "replaceorder",
    "sendorder",
    "submitorder",
    # Clientes, gateways, routers y servicios de órdenes
    "brokerclient",
    "brokergateway",
    "executionclient",
    "executiongateway",
    "orderclient",
    "orderdto",
    "ordergateway",
    "ordermanager",
    "orderrequest",
    "orderresponse",
    "orderrouter",
    "orderservice",
    "orderticket",
    "positionclient",
    "positiongateway",
    "tradeclient",
    "tradeexecution",
    "tradegateway",
}

_LIVE_PATTERN = re.compile(r"(?i)(?<![a-z0-9_])live(?![a-z0-9_])")
_WRITE_SCOPE_PATTERN = re.compile(r"(?i)(?<![a-z0-9_])(?:[a-z][a-z0-9_-]*\.)+write(?![a-z0-9_])")
_JOURNAL_DATABASE_PATTERN = re.compile(r"(?i)(?<![a-z0-9_])tj\.db(?![a-z0-9_])")
_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Patrones de Red, Secretos y Rutas Absolutas (RNF-L001, RNF-L011)
_NON_LOOPBACK_PATTERN = re.compile(
    r"""(?i)(?:host|bind|listen|address)\s*[:=]\s*["'](?!(?:127\.0\.0\.1|localhost))(?:\d{1,3}\.){3}\d{1,3}["']|["']0\.0\.0\.0["']|["']::["']"""
)
_PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN (?:[A-Z0-9_-]+ )?PRIVATE KEY-----")
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"""(?i)["']?(?:api_key|secret_key|auth_token|bearer_token|password|client_secret)["']?\s*[:=]\s*["'][A-Za-z0-9_\-\.]{16,}["']"""
)
_ABSOLUTE_LOCAL_PATH_PATTERN = re.compile(
    r"""(?<![a-zA-Z0-9_])(?:/Users/|/home/|[A-Za-z]:\\Users\\)[A-Za-z0-9_.-]+"""
)


def _dependency_name(requirement: str) -> str:
    name = re.split(r"[<>=!~;@\[\s]", requirement, maxsplit=1)[0]
    return name.lower().replace("_", "-")


def _violation(code: str, location: str) -> str:
    return f"{code}: {location}"


def _scan_text(text: str, location: str) -> list[str]:
    violations: list[str] = []
    if _NON_LOOPBACK_PATTERN.search(text):
        violations.append(_violation("FORBIDDEN_NON_LOOPBACK", location))
    if _PRIVATE_KEY_PATTERN.search(text) or _SECRET_ASSIGNMENT_PATTERN.search(text):
        violations.append(_violation("SECRET_LEAK_DETECTED", location))
    if _ABSOLUTE_LOCAL_PATH_PATTERN.search(text):
        violations.append(_violation("FORBIDDEN_LOCAL_PATH", location))
    if _LIVE_PATTERN.search(text):
        violations.append(_violation("FORBIDDEN_LIVE", location))
    if _WRITE_SCOPE_PATTERN.search(text):
        violations.append(_violation("FORBIDDEN_WRITE_SCOPE", location))
    if _JOURNAL_DATABASE_PATTERN.search(text):
        violations.append(_violation("FORBIDDEN_JOURNAL_DATABASE", location))

    normalized_identifiers = {
        identifier.replace("_", "").lower()
        for identifier in _IDENTIFIER_PATTERN.findall(text)
    }
    if normalized_identifiers & _FORBIDDEN_ORDER_SYMBOLS:
        violations.append(_violation("FORBIDDEN_ORDER_CAPABILITY", location))
    return violations


def _import_root(node: ast.Import | ast.ImportFrom) -> tuple[str, ...]:
    if isinstance(node, ast.Import):
        return tuple(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
    if node.module is None:
        return ()
    return (node.module.split(".", maxsplit=1)[0],)


def _is_foreign_repository(root: str) -> bool:
    normalized = root.lower().replace("-", "_")
    return normalized == "trading_bot" or "journal" in normalized


def _is_allowed_import(root: str, allowed_import_roots: set[str]) -> bool:
    if root in {"sistema_luces", "tests"}:
        return True
    if root in getattr(sys, "stdlib_module_names", set()):
        return True
    return root in allowed_import_roots


def _scan_python(text: str, location: str, allowed_import_roots: set[str]) -> list[str]:
    violations = _scan_text(text, location)
    try:
        tree = ast.parse(text, filename=location)
    except SyntaxError:
        return violations + [_violation("INVALID_PYTHON_SOURCE", location)]

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            norm = node.name.replace("_", "").lower()
            if norm in _FORBIDDEN_ORDER_SYMBOLS:
                violations.append(_violation("FORBIDDEN_ORDER_CAPABILITY", location))

        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for root in _import_root(node):
                if _is_foreign_repository(root):
                    violations.append(_violation("FORBIDDEN_REPOSITORY_IMPORT", location))
                elif not _is_allowed_import(root, allowed_import_roots):
                    violations.append(_violation("FORBIDDEN_IMPORT", location))

        if not isinstance(node, ast.Call) or not node.args:
            continue
        is_dynamic_import = isinstance(node.func, ast.Name) and node.func.id == "__import__"
        is_dynamic_import = is_dynamic_import or (
            isinstance(node.func, ast.Attribute) and node.func.attr == "import_module"
        )
        if is_dynamic_import and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            root = node.args[0].value.split(".", maxsplit=1)[0]
            if _is_foreign_repository(root):
                violations.append(_violation("FORBIDDEN_REPOSITORY_IMPORT", location))
            elif not _is_allowed_import(root, allowed_import_roots):
                violations.append(_violation("FORBIDDEN_IMPORT", location))
    return violations


def _project_dependencies(project_config: dict[str, object]) -> set[str]:
    project = project_config.get("project", {})
    if not isinstance(project, dict):
        return set()
    dependencies = list(project.get("dependencies", []))
    optional = project.get("optional-dependencies", {})
    if isinstance(optional, dict):
        for group in optional.values():
            dependencies.extend(group)
    build_system = project_config.get("build-system", {})
    if isinstance(build_system, dict):
        dependencies.extend(build_system.get("requires", []))
    groups = project_config.get("dependency-groups", {})
    if isinstance(groups, dict):
        for group in groups.values():
            dependencies.extend(group)
    return {_dependency_name(str(requirement)) for requirement in dependencies}


def _scan_dependencies(repo_root: Path, allowed_dependencies: set[str]) -> list[str]:
    violations: list[str] = []
    try:
        with (repo_root / "pyproject.toml").open("rb") as stream:
            project_config = tomllib.load(stream)
        with (repo_root / "uv.lock").open("rb") as stream:
            lock = tomllib.load(stream)
    except (FileNotFoundError, tomllib.TOMLDecodeError):
        return [_violation("INVALID_DISTRIBUTION_METADATA", "pyproject.toml|uv.lock")]

    declared = _project_dependencies(project_config)
    for dependency in sorted(declared - allowed_dependencies):
        violations.append(_violation("FORBIDDEN_DEPENDENCY", f"pyproject.toml:{dependency}"))

    project_name = str(project_config.get("project", {}).get("name", "")).lower()
    for package in lock.get("package", []):
        package_name = str(package.get("name", "")).lower()
        if package_name != project_name and package_name not in allowed_dependencies:
            violations.append(_violation("FORBIDDEN_DEPENDENCY", f"uv.lock:{package_name}"))
    return violations


def _scan_distribution(repo_root: Path, allowed_import_roots: set[str]) -> list[str]:
    violations: list[str] = []
    distribution_root = repo_root / "dist"
    if not distribution_root.exists():
        return violations
    for path in sorted(distribution_root.rglob("*")):
        if not path.is_file():
            continue
        location = path.relative_to(repo_root).as_posix()
        if path.suffix in {".whl", ".zip"} and zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                for member in sorted(archive.namelist()):
                    member_text = archive.read(member).decode("utf-8", errors="ignore")
                    member_location = f"{location}!{member}"
                    if member.endswith(".py"):
                        violations.extend(_scan_python(member_text, member_location, allowed_import_roots))
                    else:
                        violations.extend(_scan_text(member_text, member_location))
        else:
            violations.extend(_scan_text(path.read_text(encoding="utf-8", errors="ignore"), location))
    return violations


def scan_repository(repo_root: Path) -> tuple[str, ...]:
    """Devuelve violaciones deterministas para todo el código, scripts, configs, esquemas y distribución."""
    policy_path = repo_root / "config" / "security-policy-v1.json"
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return (_violation("INVALID_SECURITY_POLICY", "config/security-policy-v1.json"),)

    violations: list[str] = []
    capabilities = set(policy.get("allowed_capabilities", []))
    if capabilities != _EXPECTED_CAPABILITIES:
        violations.append(_violation("CAPABILITY_ALLOWLIST_MISMATCH", "config/security-policy-v1.json"))
    if any(not capability.endswith(".read") for capability in capabilities):
        violations.append(_violation("FORBIDDEN_WRITE_SCOPE", "config/security-policy-v1.json"))

    allowed_dependencies = {
        str(name).lower().replace("_", "-")
        for name in policy.get("allowed_runtime_dependencies", [])
    }
    allowed_import_roots = {str(name) for name in policy.get("allowed_import_roots", [])}
    violations.extend(_scan_dependencies(repo_root, allowed_dependencies))

    target_dirs = ["src", "scripts", "config", "contracts", "schemas", "ui", "panel"]
    for dir_name in target_dirs:
        dir_path = repo_root / dir_name
        if not dir_path.exists():
            continue
        for path in sorted(dir_path.rglob("*")):
            if not path.is_file() or path.suffix == ".pyc" or "__pycache__" in path.parts:
                continue
            location = path.relative_to(repo_root).as_posix()
            text = path.read_text(encoding="utf-8", errors="ignore")
            if path.suffix == ".py":
                violations.extend(_scan_python(text, location, allowed_import_roots))
            else:
                violations.extend(_scan_text(text, location))

    for root_file in ["Makefile", "pyproject.toml"]:
        file_path = repo_root / root_file
        if file_path.is_file():
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            violations.extend(_scan_text(text, root_file))

    violations.extend(_scan_distribution(repo_root, allowed_import_roots))
    return tuple(sorted(set(violations)))
