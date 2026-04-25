from pathlib import Path


def test_backend_structure_exists() -> None:
    root = Path(__file__).resolve().parents[2] / "backend"
    for sub in ("sdk", "services", "api", "schemas", "docs", "tests"):
        assert (root / sub).exists()
