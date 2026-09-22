"""Regression checks for the release version-consistency gate."""

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_distribution.py"
SPEC = importlib.util.spec_from_file_location("verify_distribution", SCRIPT)
verification = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verification)


def test_checkout_versions_match():
    assert verification.source_version()


@pytest.mark.parametrize(
    "module_version",
    ['__version__ = "1.2.3"', '__version__ = "1.2.4"', "pass"],
)
def test_version_gate_without_importing_package(tmp_path, monkeypatch, module_version):
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.2.3"\n')
    package = tmp_path / "aiophyn"
    package.mkdir()
    (package / "__init__.py").write_text(
        module_version + '\nraise RuntimeError("must not import source package")\n'
    )
    monkeypatch.setattr(verification, "ROOT", tmp_path)
    if module_version == '__version__ = "1.2.3"':
        assert verification.source_version() == "1.2.3"
    else:
        with pytest.raises(ValueError, match="must match"):
            verification.source_version()
