# Foxhole Map Exporter

Python pipeline for exporting and processing maps from [Foxhole](https://store.steampowered.com/app/fox)

## Pipeline

```text
0_make_release.py     →  builds Exporter.exe from C# source
1_export.py           →  Exporter.exe reads .pak → export/_json/, _meshes/, _heightmap/, _layers/
2_stitch_layers.py    →  stitches per-region terrain tiles   → export/_layers_stitched/
3_blend_example.py    →  Blender scene build     → export/_blend/<MapName>.blend
```

## Requirements

### Game

- Foxhole

### Python Dependencies

- Python 3.10–3.13 (no `bpy` on 3.14)
- **numpy**
- **opencv-python** (step 2 only)
- **bpy** / Blender Python environment (step 3 only)

```bash
pip install numpy opencv-python
```

### Blender

- Blender 5

### Build Only (Step 0)

- [.NET 10 SDK](https://dotnet.microsoft.com/download)

Clone the repository with submodules (CUE4Parse is a required submodule):

```bash
git clone --recurse-submodules https://github.com/Tsekho/fh_map_exporter.git
```

## Usage

### Step 0 - Build the exporter

Compiles `Exporter/` and outputs `Exporter.exe` at the repo root. Only needed when you want to rebuild from source; a pre-built `Exporter.exe` is included.

```bash
python 0_make_release.py
```

### Exporter.exe - Standalone Usage

`Exporter.exe` is a self-contained win-x64 binary and can be run directly without the Python wrapper.

```text
Exporter.exe -i <pak_path> -o <export_path> [-t] [-a <asset_path>]
```

| Argument | Description |
|---|---|
| `-i <pak_path>` | Path to the `.pak` file **or** its containing directory |
| `-o <export_path>` | Output folder (`meshes/` subdirectory will be created) |
| `-t`, `--texture` | Terrain layers and heightmaps |
| `-a <asset_path>` | Single asset to export, e.g. `War/Content/Maps/HomeRegionC.umap` (`.umap` extension is optional). If omitted, all umaps under `War/Content/Maps` are exported in alphabetical order. |

```bash
# Export a single map
Exporter.exe -i "C:\...\War-WindowsNoEditor.pak" -o export -a War/Content/Maps/HomeRegionC

# Export a specific umap with explicit extension
Exporter.exe -i "C:\...\War-WindowsNoEditor.pak" -o export -a War/Content/Maps/Master/AcrithiaHex.umap

# Export all maps + textures from a Paks directory
Exporter.exe -i "C:\...\Paks" -o export -t
```

### Step 1 - Export Game Files

Clears `export/` and runs `Exporter.exe` against the game `.pak`. Writes:

| Directory | Contents |
|---|---|
| `export/_json/` | Per-map JSON (symbols, groups, blueprints + transforms) |
| `export/_meshes/` | Static/skeletal meshes as `.pskx` / `.psk` |
| `export/_heightmap/` | 16-bit grayscale heightmaps (2200×2200 px, 1 m/px) |
| `export/_layers/` | Per-region terrain weightmap layers (8-bit grayscale PNG) |

```bash
python 1_export.py
```

### Step 2 - Stitch Terrain Layers

Composites the per-region 2048×2048 terrain tiles onto a single world-scale canvas using hex-shaped masks and region center coordinates.

```bash
python 2_stitch_layers.py
```

Output goes to `export/_layers_stitched/`, compatible with [map mod generator](https://github.com/Tsekho/fh_map_mod_generator).

### Step 3 - Generate Blender Scenes

Reads JSON and meshes from `export/` and builds `.blend` files.

```bash
# Single map (interactive selection)
python 3_blend_example.py

# Specific map
python 3_blend_example.py SomeMapName

# All maps
python 3_blend_example.py -a

# Exclude terrain
python 3_blend_example.py -nt SomeMapName
```

Output goes to `export/_blend/`.

## Project Structure

```text
.
├── 0_make_release.py           # Builds Exporter.exe from C# source
├── 1_export.py                 # Runs Exporter.exe against game .pak
├── 2_stitch_layers.py          # Stitches per-region terrain tiles
├── 3_blend_example.py          # Generates Blender scenes
├── Exporter/                   # C# exporter source (.NET 10, win-x64 self-contained)
│   ├── Program.cs              # CLI entry point; sets up CUE4Parse provider
│   ├── MapExporter.cs          # Reads .umap, resolves transforms, writes JSON + meshes
│   ├── LandscapeStitcher.cs    # Exports heightmaps and weightmap layers as PNGs
│   ├── TransformMath.cs        # UE4 Euler/quaternion ↔ rotation matrix conversions
│   ├── JsonOutput.cs           # Custom compact JSON serializer
│   └── Constants.cs            # Mesh filters, blueprint patches, name normalizations
├── utils/
│   ├── converter.py            # PSK/PSKX parser, Blender helpers, Map class
│   ├── region_centers.json     # World-space pixel coordinates of all ~55 map regions
│   ├── mask.png                # Hex-shaped mask applied per region tile during stitching
│   └── catalogue.json          # Partially categorized asset names
└── CUE4Parse/                  # Git submodule - Unreal Engine asset reader
```

## Transform Format

Every placed object in the exported JSON is stored as a 9-element array:

```text
[x, y, z, sx, sy, sz, pitch, yaw, roll]
```

Coordinates are in Unreal Engine world-space centimetres. `utils/converter.py` converts these to Blender metres/radians using the standard UE → Blender coordinate mapping. Rotations are in degrees.
