"""Verifica la autoridad documental del rebaseline sin dependencias externas."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

CANONICAL = (
    "README.md",
    "PROJECT.md",
    "ORIGINAL_REQUEST.md",
    "AGENTS.md",
    "CONTEXT.md",
    ".agents/README.md",
    "TEST_READY.md",
    "TEST_INFRA.md",
    "docs/README.md",
    "docs/specs/SPEC-002-integracion-futura-trading-journal.md",
    "docs/specs/SPEC-003-registro-evolutivo-y-actualizacion-incremental-ui.md",
    "docs/SRS.md",
    "docs/ARQUITECTURA.md",
    "docs/SISTEMA-VISUAL.md",
    "docs/TRAZABILIDAD.md",
    "docs/PLAN-REALINEACION.md",
    "docs/DECISIONES-ABIERTAS.md",
    "docs/adr/ADR-002-piloto-separado-integracion-futura-journal.md",
    "docs/adr/ADR-003-yahoo-sp500-fuente-publica-transitoria.md",
    "docs/adr/ADR-004-yahoo-cotizaciones-multi-activo.md",
    "docs/AUDITORIA-REALINEACION.md",
    "docs/AUDITORIA-RUNTIME-MONITOR-2026-08-30.md",
    "docs/AUDITORIA-FUENTE-YAHOO-SP500-2026-08-30.md",
    "docs/AUDITORIA-FUENTE-YAHOO-MULTI-ACTIVO-2026-08-30.md",
    "docs/teamwork/README.md",
    "docs/teamwork/ANTIGRAVITY-TEAMWORK-SYSTEM-PROMPT.md",
    "docs/evidence/README.md",
    "docs/evidence/v1-gate.md",
    "docs/legacy/README.md",
)

AUTHORITY = tuple(path for path in CANONICAL if not path.startswith("docs/legacy/"))

FORBIDDEN = (
    (re.compile(r"agent-architect", re.IGNORECASE), "agente como autoridad"),
    (re.compile(r"Veredicto Final.*APROBADO", re.IGNORECASE), "autoaprobación antigua"),
    (re.compile(r"listo para su uso", re.IGNORECASE), "readiness no demostrado"),
    (re.compile(r"\b74[.,]5\s*%"), "métrica sintética antigua"),
    (re.compile(r"\b3[.,]42\b"), "métrica sintética antigua"),
    (re.compile(r"-?4[.,]18\s*%"), "métrica sintética antigua"),
    (re.compile(r"190\s*/\s*190"), "conteo de certificación antiguo"),
    (re.compile(r"313\s+pruebas", re.IGNORECASE), "conteo de certificación antiguo"),
)

REQUIRED_TEXT = {
    "ORIGINAL_REQUEST.md": ("DO-01", "DO-07", "Trading Journal", "cuentas demo"),
    "docs/SRS.md": ("RF-L001", "RNF-L013", "RB-L012", "G-R7"),
    "docs/specs/SPEC-003-registro-evolutivo-y-actualizacion-incremental-ui.md": (
        "ERR-20260830-003",
        "CA-INC-01",
        "requestAnimationFrame",
        "Trading Journal permanece intacto",
    ),
    "docs/adr/ADR-004-yahoo-cotizaciones-multi-activo.md": (
        "GC=F",
        "TSLA",
        "AAPL",
        "CROSS_ASSET_SNAPSHOT",
        "diagnóstico N/A",
    ),
    "docs/AUDITORIA-FUENTE-YAHOO-MULTI-ACTIVO-2026-08-30.md": (
        "^GSPC",
        "TSLA",
        "AAPL",
        "GC=F",
        "PASS_INTEGRATION",
    ),
    "docs/ARQUITECTURA.md": ("Proyección de lectura", "loopback", "BFF", "".join(["t", "j", ".", "d", "b"])),
    "docs/SISTEMA-VISUAL.md": ("Índice de Mercado", "NO_DATA", "WCAG"),
    "docs/TRAZABILIDAD.md": ("OBJ-L01", "RF-L026", "RNF-L013", "T-HOST-001"),
    "docs/PLAN-REALINEACION.md": ("R0", "R7", "BLOCKED_EXTERNAL"),
    "TEST_READY.md": ("NOT_TEST_READY", "BLOCKED_REBASELINE"),
    "docs/teamwork/ANTIGRAVITY-TEAMWORK-SYSTEM-PROMPT.md": (
        "Project Orchestrator",
        "BLOCKED_EXTERNAL",
        "ownership exclusivo",
        "No implementes R1 durante esta primera orden",
    ),
}

LINK_PATTERN = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def relative_links(path: Path, text: str) -> list[str]:
    broken: list[str] = []
    for match in LINK_PATTERN.finditer(text):
        raw_target = match.group(1).strip().strip("<>")
        target = raw_target.split("#", 1)[0].strip()
        if not target or target.startswith(("#", "http://", "https://", "mailto:")):
            continue
        if target.startswith("/"):
            continue
        resolved = (path.parent / target).resolve()
        if not resolved.exists():
            broken.append(raw_target)
    return broken


def main() -> int:
    errors: list[str] = []
    texts: dict[str, str] = {}

    for relative in CANONICAL:
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"FALTA {relative}")
            continue
        texts[relative] = path.read_text(encoding="utf-8")

    for relative in AUTHORITY:
        text = texts.get(relative)
        if text is None:
            continue
        for pattern, reason in FORBIDDEN:
            if pattern.search(text):
                errors.append(f"PROHIBIDO {relative}: {reason}")

    for relative, needles in REQUIRED_TEXT.items():
        text = texts.get(relative, "")
        for needle in needles:
            if needle not in text:
                errors.append(f"CONTRATO {relative}: falta {needle!r}")

    for relative, text in texts.items():
        path = ROOT / relative
        for target in relative_links(path, text):
            errors.append(f"LINK {relative}: no existe {target}")

    legacy_required = (
        ROOT / "docs/legacy/SPEC-001-sistema-luces-demo-observable.md",
        ROOT / "docs/legacy/ADR-001-producto-independiente-demo-sin-ordenes.md",
        ROOT / "docs/legacy/v1-gate-agentes.md",
        ROOT / "docs/legacy/TEST_READY-agentes.md",
        ROOT / "docs/legacy/TEST_INFRA-agentes.md",
    )
    for path in legacy_required:
        if not path.is_file():
            errors.append(f"LEGADO: falta {path.relative_to(ROOT)}")

    if errors:
        print("DOCUMENTACION: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"DOCUMENTACION: PASS ({len(CANONICAL)} archivos canónicos verificados)")
    print("AUTORIDAD: PASS (sin claims históricos prohibidos)")
    print("LINKS: PASS")
    print("LEGADO: PASS (aislado y preservado)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
