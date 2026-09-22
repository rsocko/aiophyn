"""Build/check wheel and sdist, then probe each in a clean external environment."""

import argparse
import ast
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import venv

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]


def run(*args, cwd):
    subprocess.run([str(arg) for arg in args], cwd=cwd, check=True)


def source_version():
    with (ROOT / "pyproject.toml").open("rb") as stream:
        version = tomllib.load(stream)["project"]["version"]
    module = ast.parse((ROOT / "aiophyn" / "__init__.py").read_text())
    versions = [
        ast.literal_eval(statement.value)
        for statement in module.body
        if isinstance(statement, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in statement.targets
        )
    ]
    if versions != [version]:
        raise ValueError("pyproject.toml and aiophyn.__version__ must match")
    return version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, help="Copy verified release artifacts here"
    )
    args = parser.parse_args()
    version = source_version()
    with tempfile.TemporaryDirectory(prefix="aiophyn-dist-") as directory:
        work = Path(directory).resolve()
        if work.is_relative_to(ROOT):
            raise ValueError("Temporary directory must be outside the source checkout")
        artifacts = work / "dist"
        run(sys.executable, "-m", "build", ROOT, "--outdir", artifacts, cwd=work)
        wheels = list(artifacts.glob("*.whl"))
        sdists = list(artifacts.glob("*.tar.gz"))
        if len(wheels) != 1 or len(sdists) != 1:
            raise ValueError("Expected exactly one wheel and one sdist")
        run(
            sys.executable,
            "-m",
            "twine",
            "check",
            "--strict",
            *wheels,
            *sdists,
            cwd=work,
        )

        # Rebuild an extracted source archive without any enclosing Git metadata.
        archive = work / "archive"
        archive.mkdir()
        with tarfile.open(sdists[0]) as source:
            for member in source.getmembers():
                target = (archive / member.name).resolve()
                if not target.is_relative_to(archive) or not (
                    member.isfile() or member.isdir()
                ):
                    raise ValueError(f"Unsafe source archive member: {member.name}")
            source.extractall(archive)
        source_roots = list(archive.iterdir())
        if len(source_roots) != 1 or list(archive.rglob(".git")):
            raise ValueError("Expected one source tree without Git metadata")
        rebuilt = work / "rebuilt"
        run(
            sys.executable,
            "-m",
            "build",
            source_roots[0],
            "--outdir",
            rebuilt,
            cwd=work,
        )
        run(
            sys.executable,
            "-m",
            "twine",
            "check",
            "--strict",
            *sorted(rebuilt.iterdir()),
            cwd=work,
        )

        probe = work / "check_installed.py"
        shutil.copyfile(ROOT / "scripts" / "check_installed.py", probe)
        for kind, artifact in (("wheel", wheels[0]), ("sdist", sdists[0])):
            environment = work / kind
            venv.EnvBuilder(with_pip=True).create(environment)
            python = environment / (
                "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
            )
            run(
                python,
                "-I",
                "-m",
                "pip",
                "install",
                "--quiet",
                "--upgrade",
                "pip",
                cwd=work,
            )
            run(
                python,
                "-I",
                "-m",
                "pip",
                "install",
                "--quiet",
                artifact,
                cwd=work,
            )
            run(python, "-I", "-m", "pip", "check", cwd=work)
            run(python, "-I", probe, version, cwd=work)

        if args.output_dir:
            output = args.output_dir.resolve()
            output.mkdir(parents=True, exist_ok=True)
            if any(output.iterdir()):
                raise ValueError("Output directory must be empty")
            for artifact in (*wheels, *sdists):
                shutil.copy2(artifact, output / artifact.name)
    print("Wheel, sdist, source-archive rebuild, and version checks passed")


if __name__ == "__main__":
    main()
