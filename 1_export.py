"""
1_export.py
========
Export Foxhole game data from the .pak file using Exporter.exe.

Clears the export/ directory, runs Exporter.exe against the game .pak, then
prints a summary of extracted symbols, groups, blueprints, meshes, and JSON.

Usage:
    python 1_export.py
"""

import subprocess
import shutil
import json
import sys
from pathlib import Path

PAK    = r"C:\Program Files (x86)\Steam\steamapps\common\Foxhole\War\Content\Paks\War-WindowsNoEditor.pak"
EXPORT = "export"

EXE = Path(__file__).parent.resolve() / "Exporter.exe"


def main() -> int:
    if Path(EXPORT).exists():
        shutil.rmtree(EXPORT)

    subprocess.run([str(EXE), "-i", PAK, "-o", EXPORT, "-t"])

    json_path = Path(EXPORT) / "_json" / "HomeRegionW.json"
    if not json_path.exists():
        print(f"ERROR: JSON not found: {json_path}")
        return 1

    data = json.loads(json_path.read_text(encoding="utf-8"))
    mesh_dir = Path(EXPORT) / "_meshes"
    n_meshes  = len(list(mesh_dir.rglob("*.pskx"))) if mesh_dir.exists() else 0
    n_meshes_ = len(list(mesh_dir.rglob("*.psk")))  if mesh_dir.exists() else 0

    print()
    print("=== RESULTS ===")
    print(f"  symbols    : {len(data.get('symbols',    [])):>6} mesh types")
    print(f"  groups     : {len(data.get('groups',     [])):>6} mesh types")
    print(f"  blueprints : {len(data.get('blueprints', [])):>6} class types")
    print(f"  meshes     : {n_meshes:>6} .pskx files in {mesh_dir}")
    print(f"  meshes     : {n_meshes_:>6} .psk  files in {mesh_dir}")
    print(f"  JSON       : {json_path}  ({json_path.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
