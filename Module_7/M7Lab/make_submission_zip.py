"""
Create the M7Lab submission zip: the Python code + the .exe, WITHOUT the
virtual environment (as the assignment requires).

Run from the project folder after build_exe.bat has made the .exe:
    python make_submission_zip.py

The zip is written next to the project folder:
    ..\\M7Lab_beckhamwilliam.zip
"""

import sys
import zipfile
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
EXE_PATH = PROJECT_DIR / "dist" / "M7Lab_Launcher.exe"
ZIP_NAME = "M7Lab_beckhamwilliam.zip"

# Folders/files that must NOT go in the zip.
EXCLUDED_DIRS = {"venv", ".venv", "env", "build", "__pycache__", "saves", "logs", "output", ".git", ".vscode"}
EXCLUDED_SUFFIXES = {".pyc", ".spec"}


def should_include(relative_path):
    """Return True if a file (path relative to the project folder) belongs in the zip."""
    parts = Path(relative_path).parts
    if any(part in EXCLUDED_DIRS for part in parts[:-1]):
        return False
    if Path(relative_path).suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if parts and parts[0] == "dist":
        return Path(relative_path).name == EXE_PATH.name  # only the .exe from dist/
    return True


def collect_files(project_dir=PROJECT_DIR):
    """Return the sorted list of project files (relative paths) that go in the zip."""
    files = []
    for path in project_dir.rglob("*"):
        if path.is_file():
            relative = path.relative_to(project_dir)
            if should_include(relative):
                files.append(relative)
    return sorted(files)


def make_zip(project_dir=PROJECT_DIR, zip_path=None):
    """Write the submission zip and return its path.

    Raises FileNotFoundError if the .exe hasn't been built yet.
    """
    exe_path = project_dir / "dist" / EXE_PATH.name
    if not exe_path.is_file():
        raise FileNotFoundError(f"{exe_path} not found - run build_exe.bat first.")
    zip_path = Path(zip_path or project_dir.parent / ZIP_NAME)
    files = collect_files(project_dir)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in files:
            archive.write(project_dir / relative, Path(project_dir.name) / relative)
    return zip_path, files


def main():
    """Build the zip and report what went in, handling errors without a traceback."""
    try:
        zip_path, files = make_zip()
    except (FileNotFoundError, OSError) as error:
        print(f"Could not create the zip: {error}")
        return 1
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"Created {zip_path} ({size_mb:.1f} MB, {len(files)} files)")
    print("Includes the .exe:", any(f.name == EXE_PATH.name for f in files))
    print("Includes a venv:  ", any(part in {"venv", ".venv"} for f in files for part in f.parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
