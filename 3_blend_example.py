"""
3_blend_example.py
========
Generate a .blend file from Foxhole map exports produced by Exporter.exe.

Usage:
    python 3_blend_example.py [MapName] [-nt] [-a]

Examples:
    python 3_blend_example.py OarbreakerHex
    python 3_blend_example.py OarbreakerHex -nt
    python 3_blend_example.py -a -nt
    python 3_blend_example.py                   # interactive map/terrain selection

Options:
    MapName            Map name (e.g. OarbreakerHex); omit for interactive prompt
    -nt, --no-terrain  Exclude heightmap terrain (terrain included by default)
    -a, --all          Process every map found in export/_json

Collection hierarchy:
    <MapName>/
        Terrain/                          (unless -nt)
        Symbols/
            Meshes/Environment/Props/
                AmmoCrate/ [1, 2, ...]
        Groups/
            Meshes/Environment/Foliage/
                Tree_01/ [1, 2, ...]
        Blueprints/
            <BlueprintClass>/
                1/
                    <MeshName>/ [1, 2, ...]
                2/ ...

Output:
    export/_blend/<MapName>.blend
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from utils.converter import Map

EXPORT_DIR = Path("export")


# ------------------------------------------------------------------------------
#  Interactive helpers
# ------------------------------------------------------------------------------


def pick_map_interactive(export_dir: Path) -> Optional[List[str]]:
    """Prompt the user to select a map from those found in *export_dir*/_json."""
    json_dir = export_dir / "_json"
    if not json_dir.is_dir():
        print(f"ERROR: {json_dir} not found")
        return None

    maps = sorted(p.stem for p in json_dir.glob("*.json"))
    if not maps:
        print(f"ERROR: No JSON files found in {json_dir}")
        return None

    print("Available maps:")
    print("    0. All maps")
    for i, name in enumerate(maps, 1):
        print(f"  {i:3}. {name}")

    while True:
        raw = input("\nSelect map (0 for all, number or name): ").strip()
        if raw == "0":
            return maps
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(maps):
                return [maps[idx]]
        elif raw in maps:
            return [raw]
        print("  Invalid selection, try again.")


def ask_terrain() -> bool:
    """Prompt the user whether to include heightmap terrain."""
    while True:
        raw = input("Include terrain? [Y/n]: ").strip().lower()
        if raw in ("", "y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("  Please enter y or n.")


# ------------------------------------------------------------------------------
#  CLI entry point
# ------------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a .blend from Foxhole map exports.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "map_name",
        nargs="?",
        help="Map name (e.g. OarbreakerHex); omit for interactive selection",
    )
    parser.add_argument(
        "-nt",
        "--no-terrain",
        action="store_true",
        help="Exclude heightmap terrain (terrain included by default)",
    )
    parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Process every map found in export/_json",
    )
    args = parser.parse_args()

    json_dir = EXPORT_DIR / "_json"

    # Resolve map list and terrain flag --------------------------------------
    if args.all:
        if not json_dir.is_dir():
            print(f"ERROR: {json_dir} not found")
            return 1
        map_names = sorted(p.stem for p in json_dir.glob("*.json"))
        if not map_names:
            print(f"ERROR: No maps found in {json_dir}")
            return 1
        terrain = not args.no_terrain
    elif args.map_name:
        map_names = [args.map_name]
        terrain = not args.no_terrain
    else:
        map_names = pick_map_interactive(EXPORT_DIR)
        if map_names is None:
            return 1
        terrain = ask_terrain()

    # Process ----------------------------------------------------------------
    errors: List[str] = []
    for name in map_names:
        json_path = json_dir / f"{name}.json"
        if not json_path.exists():
            print(f"ERROR: JSON not found: {json_path}")
            errors.append(name)
            continue
        print(f"=== {name} ===")
        Map(str(json_path), str(EXPORT_DIR)).blend(terrain=terrain)

    if errors:
        print(f"\n{len(errors)} map(s) failed: {', '.join(errors)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
