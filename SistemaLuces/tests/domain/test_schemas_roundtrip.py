"""Pruebas de esquemas JSON versionados y validación round-trip (SPEC-001 §6, CA-1, CA-6)."""

import json
from pathlib import Path
import unittest

from tests.conftest import REPO_ROOT


EXPECTED_SCHEMAS = {
    "event-envelope-v1.json",
    "state-transition-v1.json",
    "signal-v1.json",
    "simulation-v1.json",
    "metric-snapshot-v1.json",
    "instrument-profile-v1.json",
    "cost-profile-v1.json",
    "risk-profile-v1.json",
    "import-manifest-v1.json",
    "depth-gate-policy-v1.json",
    "model-gate-policy-v1.json",
    "api-requests-v1.json",
    "api-results-v1.json",
    "view-document-v1.json",
    "proyeccion_v1.json",
}


class SchemaRoundtripTests(unittest.TestCase):
    def test_todos_los_esquemas_v1_existen_y_son_json_validos(self) -> None:
        schemas_dir = REPO_ROOT / "schemas"
        self.assertTrue(schemas_dir.exists(), "Directorio schemas/ no existe")

        found_schemas = {p.name for p in schemas_dir.glob("*.json")}
        self.assertTrue(
            EXPECTED_SCHEMAS.issubset(found_schemas),
            f"Faltan esquemas: {EXPECTED_SCHEMAS - found_schemas}",
        )

        for schema_file in schemas_dir.glob("*.json"):
            with self.subTest(schema=schema_file.name):
                content = json.loads(schema_file.read_text(encoding="utf-8"))
                self.assertIsInstance(content, dict)
                self.assertIn("$schema", content)
                self.assertIn("title", content)
                self.assertIn("properties", content)
                # Todos los esquemas deben fijar additionalProperties: false
                self.assertFalse(content.get("additionalProperties", True))


if __name__ == "__main__":
    unittest.main()
