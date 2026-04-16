"""
converter.py
========
Shared helpers for Foxhole map → Blender pipeline.

    • Map class  (with include / exclude / palette filtering)
    • PSK / PSKX parsing
    • 16-bit grayscale PNG reader
    • Blender mesh / collection / transform utilities
    • Heightmap terrain builder

Filtering / palette parameters (all on Map):
    include  – optional list of fnmatch patterns; only mesh names that match
               at least one pattern are placed.
    exclude  – optional list of fnmatch patterns; mesh names matching any
               pattern are skipped (applied after include).
    palette  – optional dict mapping an fnmatch pattern to a '#RRGGBB' hex
               string.  After all meshes are loaded the first matching pattern
               wins and a Principled-BSDF material is assigned to the mesh
               data-block (shared by all instances).  Unmatched meshes keep
               the Blender default material.
"""

import ctypes
import fnmatch
import json
import os
import struct
import zlib
from math import radians
from typing import Dict, List, Optional, Tuple

import numpy as np
import bpy


# ------------------------------------------------------------------------------
#  PSK data structures
# ------------------------------------------------------------------------------


class _Section(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_char * 20),
        ("type_flags", ctypes.c_int32),
        ("data_size", ctypes.c_int32),
        ("data_count", ctypes.c_int32),
    ]


class _Vec3(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_float),
        ("y", ctypes.c_float),
        ("z", ctypes.c_float),
    ]


class _Wedge16(ctypes.Structure):
    _fields_ = [
        ("point_index", ctypes.c_uint16),
        ("_pad1", ctypes.c_int16),
        ("u", ctypes.c_float),
        ("v", ctypes.c_float),
        ("material_index", ctypes.c_uint8),
        ("_reserved", ctypes.c_int8),
        ("_pad2", ctypes.c_int16),
    ]


class _Wedge32(ctypes.Structure):
    _fields_ = [
        ("point_index", ctypes.c_uint32),
        ("u", ctypes.c_float),
        ("v", ctypes.c_float),
        ("material_index", ctypes.c_uint32),
    ]


class _Face16(ctypes.Structure):
    _fields_ = [
        ("wedge_indices", ctypes.c_uint16 * 3),
        ("material_index", ctypes.c_uint8),
        ("aux_material_index", ctypes.c_uint8),
        ("smoothing_groups", ctypes.c_int32),
    ]


class _Face32(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("wedge_indices", ctypes.c_uint32 * 3),
        ("material_index", ctypes.c_uint8),
        ("aux_material_index", ctypes.c_uint8),
        ("smoothing_groups", ctypes.c_int32),
    ]


class _Material(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_char * 64),
        ("texture_index", ctypes.c_int32),
        ("poly_flags", ctypes.c_int32),
        ("aux_material", ctypes.c_int32),
        ("aux_flags", ctypes.c_int32),
        ("lod_bias", ctypes.c_int32),
        ("lod_style", ctypes.c_int32),
    ]


def _read_chunk(fp, cls, section: _Section):
    nb = section.data_size * section.data_count
    buf = bytearray(fp.read(nb))
    return tuple((cls * section.data_count).from_buffer(buf))


def read_psk(path: str):
    """
    Parse a .psk / .pskx file.
    Returns (points, wedges, faces) tuples or raises on error.
    """
    points = ()
    wedges = ()
    faces = ()

    with open(path, "rb") as fp:
        sec_size = ctypes.sizeof(_Section)
        while True:
            raw = fp.read(sec_size)
            if len(raw) < sec_size:
                break
            sec = _Section.from_buffer_copy(raw)

            if sec.name == b"ACTRHEAD":
                pass
            elif sec.name == b"PNTS0000":
                points = _read_chunk(fp, _Vec3, sec)
            elif sec.name == b"VTXW0000":
                cls = _Wedge32 if len(points) > 0xFFFF else _Wedge16
                wedges = _read_chunk(fp, cls, sec)
            elif sec.name == b"FACE0000":
                faces = _read_chunk(fp, _Face16, sec)
            elif sec.name == b"FACE3200":
                faces = _read_chunk(fp, _Face32, sec)
            elif sec.name == b"MATT0000":
                _read_chunk(fp, _Material, sec)
            else:
                fp.read(sec.data_size * sec.data_count)

    return points, wedges, faces


# ------------------------------------------------------------------------------
#  16-bit grayscale PNG reader
# ------------------------------------------------------------------------------


def read_png16_gray(path: str) -> Tuple[int, int, np.ndarray]:
    """
    Read a 16-bit grayscale PNG without Pillow/cv2.
    Returns (width, height, array[uint16, shape=(height, width)]).

    Height encoding in Foxhole heightmaps:
        height_m = (pixel_value - 32768) / 100.0
    Canvas: 2200×2200, center pixel (1100, 1100) = world origin (0, 0).
    """
    with open(path, "rb") as f:
        sig = f.read(8)
    assert sig == b"\x89PNG\r\n\x1a\n", "Not a valid PNG file"

    width = height = 0
    bit_depth = color_type = 0
    idat_chunks: list[bytes] = []

    with open(path, "rb") as f:
        f.read(8)  # signature
        while True:
            hdr = f.read(8)
            if len(hdr) < 8:
                break
            length = struct.unpack(">I", hdr[:4])[0]
            tag = hdr[4:8]
            data = f.read(length)
            f.read(4)  # CRC

            if tag == b"IHDR":
                width, height = struct.unpack(">II", data[:8])
                bit_depth = data[8]
                color_type = data[9]
                assert bit_depth == 16 and color_type == 0, (
                    f"Expected 16-bit grayscale, got depth={bit_depth} "
                    f"ctype={color_type}"
                )
            elif tag == b"IDAT":
                idat_chunks.append(data)
            elif tag == b"IEND":
                break

    raw = zlib.decompress(b"".join(idat_chunks))

    bpp = 2
    row_len = width * bpp
    out = np.zeros((height, width), dtype=np.uint16)
    prev = np.zeros(row_len, dtype=np.uint8)

    pos = 0
    for y in range(height):
        filt = raw[pos]
        pos += 1
        row = np.frombuffer(
            raw, dtype=np.uint8, count=row_len, offset=pos
        ).copy()
        pos += row_len

        if filt == 0:
            pass
        elif filt == 1:
            for i in range(bpp, row_len):
                row[i] = (row[i] + row[i - bpp]) & 0xFF
        elif filt == 2:
            row = (row.astype(np.int16) + prev).astype(np.uint8)
        elif filt == 3:
            row = row.astype(np.int16)
            for i in range(row_len):
                a = row[i - bpp] if i >= bpp else 0
                b = int(prev[i])
                row[i] = (row[i] + (a + b) // 2) & 0xFF
            row = row.astype(np.uint8)
        elif filt == 4:
            row = row.astype(np.int16)
            for i in range(row_len):
                a = int(row[i - bpp]) if i >= bpp else 0
                b = int(prev[i])
                c = int(prev[i - bpp]) if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                row[i] = (row[i] + pr) & 0xFF
            row = row.astype(np.uint8)

        prev = row.astype(np.uint8)
        out[y] = (
            row.reshape(width, 2).astype(np.uint16)[:, 0] * 256
            + row.reshape(width, 2).astype(np.uint16)[:, 1]
        )

    return width, height, out


# ------------------------------------------------------------------------------
#  Blender helpers
# ------------------------------------------------------------------------------

# Module-level mesh cache; callers can clear() between maps.
mesh_cache: Dict[str, Optional[bpy.types.Material]] = {}


def _hex_to_rgb(hex_color: str) -> Tuple[float, float, float]:
    """
    Convert a '#RRGGBB' or 'RRGGBB' string to an (r, g, b) tuple in [0, 1].
    """
    h = hex_color.lstrip("#")
    return (
        int(h[0:2], 16) / 255.0,
        int(h[2:4], 16) / 255.0,
        int(h[4:6], 16) / 255.0,
    )


def _make_color_material(hex_color: str) -> bpy.types.Material:
    """
    Return a Principled-BSDF material whose Base Color matches *hex_color*.

    Materials are named ``Color_RRGGBB`` and reused if they already exist in
    the current blend file, so repeated calls with the same color are cheap.
    """
    name = f"Color_{hex_color.lstrip('#').upper()}"
    if name in bpy.data.materials:
        return bpy.data.materials[name]

    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        r, g, b = _hex_to_rgb(hex_color)
        bsdf.inputs["Base Color"].default_value = (r, g, b, 1.0)
    return mat


def psk_to_blender_mesh(points, wedges, faces, name: str) -> bpy.types.Mesh:
    """Convert parsed PSK data into a bpy.data.Mesh (UE cm → Blender m)."""
    mesh = bpy.data.meshes.new(name)
    verts = [(p.x * 0.01, p.y * 0.01, p.z * 0.01) for p in points]
    tris = [
        [
            wedges[face.wedge_indices[2]].point_index,
            wedges[face.wedge_indices[1]].point_index,
            wedges[face.wedge_indices[0]].point_index,
        ]
        for face in faces
    ]
    mesh.from_pydata(verts, [], tris)
    mesh.update()
    return mesh


def get_mesh(mesh_name: str, meshes_dir: str) -> Optional[bpy.types.Mesh]:
    """Load (and cache) a .pskx/.psk mesh by its key name."""
    if mesh_name in mesh_cache:
        return mesh_cache[mesh_name]

    for ext in (".pskx", ".psk"):
        path = os.path.join(meshes_dir, mesh_name + ext)
        if os.path.exists(path):
            try:
                pts, wdgs, fcs = read_psk(path)
                if pts and fcs:
                    mesh = psk_to_blender_mesh(pts, wdgs, fcs, mesh_name)
                    mesh_cache[mesh_name] = mesh
                    return mesh
                print(f"  [WARN] Empty PSK: {path}")
            except Exception as exc:
                print(f"  [WARN] PSK read error ({mesh_name}): {exc}")
            break

    mesh_cache[mesh_name] = None
    return None


def apply_ue_transform(obj: bpy.types.Object, t: list) -> None:
    """
    Apply a UE transform [x,y,z, sx,sy,sz, pitch,yaw,roll] to a Blender object.

    Coordinate mapping (matches BlenderUmap2):
        Blender X =  UE X / 100
        Blender Y = -UE Y / 100
        Blender Z =  UE Z / 100
        Euler XYZ = (roll, -pitch, -yaw)
    """
    x, y, z = t[0], t[1], t[2]
    sx, sy, sz = t[3], t[4], t[5]
    pitch, yaw, roll = t[6], t[7], t[8]

    obj.location = (x * 0.01, y * -0.01, z * 0.01)
    obj.scale = (sx, sy, sz)
    obj.rotation_mode = "XYZ"
    obj.rotation_euler = (radians(roll), radians(-pitch), radians(-yaw))


def place_mesh(
    mesh_name: str,
    transform: list,
    collection: bpy.types.Collection,
    meshes_dir: str,
    obj_name: Optional[str] = None,
) -> None:
    """Instantiate *mesh_name* into *collection* with *transform* applied."""
    mesh = get_mesh(mesh_name, meshes_dir)
    if mesh is None:
        return
    obj = bpy.data.objects.new(obj_name or mesh_name, mesh)
    collection.objects.link(obj)
    apply_ue_transform(obj, transform)


def ensure_collection(
    segments: List[str],
    parent: bpy.types.Collection,
    cache: Dict[Tuple[str, ...], bpy.types.Collection],
    root_key: Tuple[str, ...],
) -> bpy.types.Collection:
    """
    Walk *segments*, creating sub-collections as needed under *parent*.
    *root_key* is prepended to each cache key so sibling trees with identical
    segment names (e.g. Symbols vs Groups) remain distinct.
    """
    current = parent
    for i, seg in enumerate(segments):
        key = root_key + tuple(segments[: i + 1])
        if key not in cache:
            coll = bpy.data.collections.new(seg)
            current.children.link(coll)
            cache[key] = coll
        current = cache[key]
    return current


def create_terrain(
    heightmap_path: str,
    collection: bpy.types.Collection,
    stride: int = 1,
) -> bpy.types.Object:
    """Build a grid mesh from a 16-bit PNG heightmap and add it to *collection*."""
    print(f"  Loading heightmap: {heightmap_path}")
    w, h, pixels = read_png16_gray(heightmap_path)
    print(f"  Heightmap size: {w}x{h}")

    cx, cy = w // 2, h // 2
    sub = pixels[::stride, ::stride]
    rows, cols = sub.shape

    valid = sub != 0
    hm = sub.astype(np.float32)
    hm[~valid] = 32768.0
    hm = (hm - 32768.0) / 100.0

    px_coords = np.arange(0, w, stride, dtype=np.float32)[:cols]
    py_coords = np.arange(0, h, stride, dtype=np.float32)[:rows]
    VX, VY = np.meshgrid(px_coords - cx, -(py_coords - cy))
    verts_np = np.stack([VX.ravel(), VY.ravel(), hm.ravel()], axis=1)

    gy_idx, gx_idx = np.arange(rows - 1), np.arange(cols - 1)
    GY, GX = np.meshgrid(gy_idx, gx_idx, indexing="ij")
    GY, GX = GY.ravel(), GX.ravel()

    keep = (
        valid[GY, GX]
        & valid[GY, GX + 1]
        & valid[GY + 1, GX]
        & valid[GY + 1, GX + 1]
    )
    GY, GX = GY[keep], GX[keep]

    faces_np = np.empty((keep.sum(), 4), dtype=np.int32)
    faces_np[:, 0] = GY * cols + GX
    faces_np[:, 1] = GY * cols + GX + 1
    faces_np[:, 2] = (GY + 1) * cols + GX + 1
    faces_np[:, 3] = (GY + 1) * cols + GX

    mesh = bpy.data.meshes.new("Terrain")
    mesh.from_pydata(
        [tuple(v) for v in verts_np.tolist()],
        [],
        [tuple(f) for f in faces_np.tolist()],
    )
    mesh.update()

    obj = bpy.data.objects.new("Terrain", mesh)
    collection.objects.link(obj)

    print(
        f"  Terrain: {cols}x{rows} grid, "
        f"{len(verts_np):,} verts, {keep.sum():,} faces, "
        f"stride={stride} (1 vert = {stride} m)"
    )
    return obj


# ------------------------------------------------------------------------------
#  Map
# ------------------------------------------------------------------------------


class Map:
    """
    Represents one Foxhole map and drives the full Blender build.

    Parameters
    ----------
    json_path : str
        Path to the map JSON file produced by the extraction pipeline.
        Expected top-level keys: ``symbols``, ``groups``, ``blueprints``.
    export_dir : str
        Root export directory.  Sub-directories ``_heightmap``, ``_meshes``,
        and ``_blend`` are resolved relative to this path.
    include : list[str] | None
        Optional allowlist of fnmatch patterns matched against mesh names.
        When provided, only mesh names matching **at least one** pattern are
        placed.  Blueprint ``_self`` keys are never affected by filtering.
    exclude : list[str] | None
        Optional denylist of fnmatch patterns matched against mesh names.
        Mesh names matching **any** pattern are skipped.  Applied *after*
        ``include``, so a name must pass both to be placed.
    palette : dict[str, str] | None
        Optional mapping of ``{fnmatch_pattern: '#RRGGBB'}`` hex color
        strings.  After all meshes have been loaded the first pattern (in
        dict insertion order) that matches a mesh name wins, and a
        Principled-BSDF material of that color is assigned to the shared
        mesh data-block.  Unmatched meshes keep the Blender default material.

    Examples
    --------
    ::

        m = Map(
            "exports/KalkStop.json",
            "exports",
            include=["*Building*", "*Wall*"],
            exclude=["*LOD*"],
            palette={
                "*Building*": "#C8A87A",
                "*Wall*":     "#8B8B8B",
            },
        )
        m.blend()
    """

    def __init__(
        self,
        json_path: str,
        export_dir: str,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        palette: Optional[Dict[str, str]] = None,
    ) -> None:
        self.json_path = json_path
        self.export_dir = export_dir
        self.name = os.path.splitext(os.path.basename(json_path))[0]
        self.include = include or []
        self.exclude = exclude or []
        self.palette = palette or {}

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if self.include or self.exclude:
            print(
                f"  Filters — include: {self.include or 'none'}, "
                f"exclude: {self.exclude or 'none'}"
            )

        raw_symbols: Dict[str, list] = data.get("symbols", {})
        raw_groups: Dict[str, list] = data.get("groups", {})
        raw_blueprints: Dict[str, list] = data.get("blueprints", {})

        self.symbols: Dict[str, list] = {
            k: v for k, v in raw_symbols.items() if self._should_place(k)
        }
        self.groups: Dict[str, list] = {
            k: v for k, v in raw_groups.items() if self._should_place(k)
        }

        filtered_bps: Dict[str, list] = {}
        for bp_class, instances in raw_blueprints.items():
            kept: list = []
            for inst in instances:
                filtered = {
                    k: v
                    for k, v in inst.items()
                    if k == "_self" or self._should_place(k)
                }
                if any(k != "_self" for k in filtered):
                    kept.append(filtered)
            if kept:
                filtered_bps[bp_class] = kept
        self.blueprints: Dict[str, list] = filtered_bps

    # -- Derived paths --------------------------------------------------------

    @property
    def heightmap_path(self) -> str:
        return os.path.join(self.export_dir, "_heightmap", f"{self.name}.png")

    @property
    def meshes_dir(self) -> str:
        return os.path.join(self.export_dir, "_meshes")

    @property
    def blend_path(self) -> str:
        return os.path.abspath(
            os.path.join(self.export_dir, "_blend", f"{self.name}.blend")
        )

    # -- Filtering ------------------------------------------------------------

    def _should_place(self, mesh_name: str) -> bool:
        """
        Return ``True`` when *mesh_name* passes the include / exclude filters.

        Logic:
          1. If ``include`` patterns are set, the name must match at least one.
          2. If ``exclude`` patterns are set, the name must not match any.
        Both conditions must hold simultaneously.
        """
        if self.include and not any(
            fnmatch.fnmatch(mesh_name, p) for p in self.include
        ):
            return False
        if self.exclude and any(
            fnmatch.fnmatch(mesh_name, p) for p in self.exclude
        ):
            return False
        return True

    # -- Palette application --------------------------------------------------

    def _apply_palette(self) -> None:
        """
        Assign Principled-BSDF materials to loaded meshes based on
        ``self.palette``.

        Iterates ``mesh_cache`` after all geometry has been placed.  For each
        cached mesh the palette patterns are tested in insertion order; the
        first match wins.  The material is written directly to the mesh
        data-block so every object instance sharing that mesh inherits the
        color automatically.  Meshes with no matching pattern are left
        untouched (Blender default material).
        """
        if not self.palette:
            return

        mat_cache: Dict[str, bpy.types.Material] = {}
        colored = 0

        for mesh_name, mesh in mesh_cache.items():
            if mesh is None:
                continue
            for pattern, hex_color in self.palette.items():
                if fnmatch.fnmatch(mesh_name, pattern):
                    if hex_color not in mat_cache:
                        mat_cache[hex_color] = _make_color_material(hex_color)
                    mat = mat_cache[hex_color]
                    if mesh.materials:
                        mesh.materials[0] = mat
                    else:
                        mesh.materials.append(mat)
                    colored += 1
                    break  # first matching pattern wins

        print(f"  Palette applied: {colored} mesh(es) colored")

    # -- Main build -----------------------------------------------------------

    def blend(self, terrain: bool = True) -> None:
        """
        Build a complete Blender scene from this map and save it as a
        compressed ``.blend`` file under ``<export_dir>/_blend/``.

        Steps
        -----
        1. Reset Blender to an empty state.
        2. Optionally build the heightmap terrain mesh.
        3. Place all symbols, groups, and blueprint mesh instances that pass
           the ``include`` / ``exclude`` filters.
        4. Apply ``palette`` colors to loaded meshes.
        5. Save the ``.blend`` file.

        Parameters
        ----------
        terrain : bool
            When ``True`` (default) the heightmap PNG is loaded and a terrain
            mesh is created.  Pass ``False`` to skip terrain (useful when
            iterating quickly on props only).
        """
        mesh_cache.clear()
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene
        scene.name = self.name

        root = bpy.data.collections.new(self.name)
        scene.collection.children.link(root)

        # Shared collection cache; keyed by (root_name, *path_segments).
        coll_cache: Dict[Tuple[str, ...], bpy.types.Collection] = {}
        total = 0

        # -- Terrain ----------------------------------------------------------
        if terrain:
            if os.path.exists(self.heightmap_path):
                print("[terrain] Building terrain ...")
                t_coll = bpy.data.collections.new("Terrain")
                root.children.link(t_coll)
                create_terrain(self.heightmap_path, t_coll)
            else:
                print(
                    f"[terrain] Heightmap not found, skipping: "
                    f"{self.heightmap_path}"
                )

        # -- Symbols ----------------------------------------------------------
        if self.symbols:
            s_inst = sum(len(v) for v in self.symbols.values())
            print(
                f"[symbols] {len(self.symbols):,} unique meshes, "
                f"{s_inst:,} instances ..."
            )
            s_root = bpy.data.collections.new("Symbols")
            root.children.link(s_root)
            for mesh_name, instances in self.symbols.items():
                sp = mesh_name.split("__")
                leaf = ensure_collection(sp, s_root, coll_cache, ("Symbols",))
                for i, t in enumerate(instances, 1):
                    place_mesh(mesh_name, t, leaf, self.meshes_dir, f"{sp[-1]}.{i}")
                    total += 1

        # -- Groups -----------------------------------------------------------
        if self.groups:
            g_inst = sum(len(v) for v in self.groups.values())
            print(
                f"[groups]  {len(self.groups):,} unique meshes, "
                f"{g_inst:,} instances ..."
            )
            g_root = bpy.data.collections.new("Groups")
            root.children.link(g_root)
            for mesh_name, instances in self.groups.items():
                sp = mesh_name.split("__")
                leaf = ensure_collection(sp, g_root, coll_cache, ("Groups",))
                for i, t in enumerate(instances, 1):
                    place_mesh(mesh_name, t, leaf, self.meshes_dir, f"{sp[-1]}.{i}")
                    total += 1

        # -- Blueprints -------------------------------------------------------
        if self.blueprints:
            bp_inst = sum(
                sum(len(v) for k, v in inst.items() if k != "_self")
                for lst in self.blueprints.values()
                for inst in lst
            )
            print(
                f"[blueprints] {len(self.blueprints):,} classes, "
                f"{bp_inst:,} mesh instances ..."
            )
            b_root = bpy.data.collections.new("Blueprints")
            root.children.link(b_root)

            for bp_class, instances in self.blueprints.items():
                bp_coll = bpy.data.collections.new(bp_class)
                b_root.children.link(bp_coll)

                for i, instance in enumerate(instances, 1):
                    inst_coll = bpy.data.collections.new(f"{bp_class}.{i}")
                    bp_coll.children.link(inst_coll)

                    for mesh_name, transforms in instance.items():
                        if mesh_name == "_self":
                            continue
                        mesh_coll = bpy.data.collections.new(mesh_name)
                        inst_coll.children.link(mesh_coll)
                        for j, t in enumerate(transforms, 1):
                            place_mesh(
                                mesh_name,
                                t,
                                mesh_coll,
                                self.meshes_dir,
                                f"{mesh_name}.{j}",
                            )
                            total += 1

        # -- Palette ----------------------------------------------------------
        self._apply_palette()

        loaded_ok = sum(1 for v in mesh_cache.values() if v is not None)
        loaded_err = sum(1 for v in mesh_cache.values() if v is None)
        print(
            f"\n  Objects placed : {total:,}\n"
            f"  Unique meshes  : {loaded_ok} loaded, "
            f"{loaded_err} missing/errored"
        )

        # -- Save -------------------------------------------------------------
        os.makedirs(os.path.dirname(self.blend_path), exist_ok=True)
        if os.path.exists(self.blend_path):
            os.remove(self.blend_path)
        print(f"\nSaving -> {self.blend_path} ...")
        bpy.ops.wm.save_as_mainfile(filepath=self.blend_path, compress=True)
        print("Done.\n")
