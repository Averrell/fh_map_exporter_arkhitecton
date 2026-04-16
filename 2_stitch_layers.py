"""
2_stitch_layers.py
========
Stitch per-region terrain layer tiles into full-world grayscale maps.

Source tiles : export/_layers/{layer_name}/{RegionName}.png  (8-bit grayscale)
Mask         : utils/mask.png                                 (8-bit grayscale)
Region coords: utils/region_centers.json                      ({name: [cx, cy]})
Output       : export/_layers_stitched/{layer_name}.png       (8-bit grayscale)

Each tile is 2048×2048 px and is placed so that its centre sits at the (cx, cy)
pixel coordinate on the world canvas.  Overlapping tiles are merged with
np.maximum (the brightest value wins).
"""

import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

# ------------------------------------------------------------------------------
#  Paths
# ------------------------------------------------------------------------------

UTILS_DIR    = Path(__file__).parent / "utils"
CENTRES_FILE = UTILS_DIR / "region_centers.json"
MASK_FILE    = UTILS_DIR / "mask.png"

LAYERS_DIR   = Path("export") / "_layers"
OUT_DIR      = Path("export") / "_layers_stitched"

TILE_HALF    = 1024   # tiles are 2048×2048; half-size used for placement


# ------------------------------------------------------------------------------
#  Helpers
# ------------------------------------------------------------------------------


def load_centres() -> dict[str, tuple[int, int]]:
    """Load region centres from JSON and return {name: (cx, cy)}."""
    with open(CENTRES_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {k: (int(v[0]), int(v[1])) for k, v in raw.items()}


def canvas_size(centres: dict[str, tuple[int, int]]) -> tuple[int, int]:
    """Return (height, width) needed to fit all tiles."""
    max_y = max_x = 0
    for cx, cy in centres.values():
        max_y = max(max_y, cy + TILE_HALF)
        max_x = max(max_x, cx + TILE_HALF)
    return max_y, max_x


def load_mask() -> np.ndarray:
    """Load utils/mask.png as a uint8 binary mask (0 or 1)."""
    img = cv2.imread(str(MASK_FILE), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Mask not found: {MASK_FILE}")
    return (img > 0).astype(np.uint8)


def stitch_layer(
    layer_dir: Path,
    centres: dict[str, tuple[int, int]],
    mask: np.ndarray,
    height: int,
    width: int,
) -> np.ndarray:
    """
    Stitch all region tiles for one layer into a single grayscale canvas.

    Missing tiles are silently skipped.  Overlapping pixels are resolved
    by taking the maximum value (np.maximum).
    """
    # Build a case-insensitive lookup: lowercase stem -> actual Path
    tile_map: dict[str, Path] = {
        p.stem.lower(): p for p in layer_dir.glob("*.png")
    }

    canvas = np.zeros((height, width), dtype=np.uint8)
    total = len(centres)
    placed = 0

    for i, (name, (cx, cy)) in enumerate(centres.items(), 1):
        print(f"  {i}/{total}", end="\r")

        tile_path = tile_map.get(name.lower())
        if tile_path is None:
            continue

        tile = cv2.imread(str(tile_path), cv2.IMREAD_GRAYSCALE)
        if tile is None:
            print(f"\n  [WARN] Unreadable tile: {tile_path}")
            continue

        tile = tile * mask   # apply hex mask

        y1, y2 = cy - TILE_HALF, cy + TILE_HALF
        x1, x2 = cx - TILE_HALF, cx + TILE_HALF
        np.maximum(canvas[y1:y2, x1:x2], tile, out=canvas[y1:y2, x1:x2])
        placed += 1

    print(f"  {total}/{total}  ({placed} tiles placed)")
    return canvas


# ------------------------------------------------------------------------------
#  Entry point
# ------------------------------------------------------------------------------


def main() -> int:
    centres = load_centres()
    try:
        mask = load_mask()
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 1

    height, width = canvas_size(centres)
    print(f"Canvas: {width}x{height} px, {len(centres)} regions")

    layer_dirs = sorted(d for d in LAYERS_DIR.iterdir() if d.is_dir())
    if not layer_dirs:
        print(f"ERROR: No layer directories found in {LAYERS_DIR}")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    total_start = time.time()
    for layer_dir in layer_dirs:
        t0 = time.time()
        print(f"\n=== {layer_dir.name} ===")
        canvas = stitch_layer(layer_dir, centres, mask, height, width)
        out_path = OUT_DIR / f"{layer_dir.name}.png"
        cv2.imwrite(str(out_path), canvas)
        print(f"  Written: {out_path}  ({time.time() - t0:.2f}s)")

    print(f"\n=== Done in {time.time() - total_start:.2f}s ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
