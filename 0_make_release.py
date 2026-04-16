"""
0_make_release.py
========
Build Exporter.exe as a self-contained win-x64 single-file release binary.

Runs `dotnet publish` on Exporter/Exporter.csproj and copies the result to
the repo root as Exporter.exe.

Usage:
    python 0_make_release.py
"""

import subprocess
import sys
import shutil
from pathlib import Path

REPO_ROOT   = Path(__file__).parent.resolve()
PROJECT_DIR = REPO_ROOT / "Exporter"
PROJECT     = PROJECT_DIR / "Exporter.csproj"
OUTPUT_DIR  = PROJECT_DIR / "bin" / "Release" / "net10.0" / "win-x64" / "publish"
DEST        = REPO_ROOT / "Exporter.exe"


def run(cmd: list[str], **kwargs) -> int:
    print(f"  >> {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, **kwargs)
    return result.returncode


def main() -> int:
    if not PROJECT.exists():
        print(f"ERROR: project file not found: {PROJECT}")
        return 1

    print("=== Building Exporter (Release / win-x64 / single-file) ===")

    rc = run([
        "dotnet", "publish",
        str(PROJECT),
        "-c", "Release",
        "-r", "win-x64",
        "--self-contained", "true",
        "-p:PublishSingleFile=true",
        "-p:EnableCompressionInSingleFile=true",
        "-p:IncludeNativeLibrariesForSelfExtract=true",
        "-p:DebugType=None",
        "-p:DebugSymbols=false",
    ])

    if rc != 0:
        print(f"\nERROR: dotnet publish failed (exit code {rc})")
        return rc

    published = OUTPUT_DIR / "Exporter.exe"
    if not published.exists():
        print(f"ERROR: expected output not found: {published}")
        return 1

    shutil.copy2(published, DEST)
    size_mb = DEST.stat().st_size / (1024 * 1024)
    print(f"\n=== SUCCESS ===")
    print(f"  {DEST}  ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
