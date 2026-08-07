#!/usr/bin/env python3
"""Ultimate Edition ESM Fixes Remastered — Linux port (replaces Installer.exe).

Reads the `Ultimate Edition ESM Fixes Remastered.mpi` container, extracts the
6 xdelta3 patches (wrapped in LZ4 Frames), applies them with native xdelta3 to
the vanilla ESMs in the game's Data/ folder and writes the fixed ESMs to the
destination folder (MO2 "Fixed ESMs" mod).

Reproduces exactly the flow of the original Installer.exe:
  source  = %FNVDATA%\\<esm> (unvalidated, unprocessed)
  output  = %DESTINATION%\\<esm>

Requirements:
  - native xdelta3 (see build_xdelta3.sh if missing)
  - python-lz4 (pip install lz4)
"""
from __future__ import annotations

import argparse
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

LZ4_MAGIC = b"\x04\x22\x4d\x18"
VCDIFF_MAGIC = b"\xd6\xc3\xc4\x00"
VCD_SOURCE, VCD_TARGET, VCD_ADLER32 = 0x01, 0x02, 0x04
SRCORTGT = VCD_SOURCE | VCD_TARGET

HERE = Path(__file__).resolve().parent
MPI = HERE / "Ultimate Edition ESM Fixes Remastered.mpi"
CACHE = Path.home() / ".cache" / "vnv-uefix"
APPID = "22380"
GAME_DIR_NAME = "Fallout New Vegas"
STEAM_LIBRARIES = [
    Path.home() / ".steam/steam/steamapps",
    Path.home() / ".local/share/Steam/steamapps",
]
EXTRA_LIBRARY = os.environ.get("VNV_STEAM_LIBRARY")
if EXTRA_LIBRARY:
    STEAM_LIBRARIES.append(Path(EXTRA_LIBRARY))


def info(msg):
    print(f"  i {msg}", flush=True)


def ok(msg):
    print(f"  + {msg}", flush=True)


def fail(msg, code=1):
    print(f"  ! {msg}", flush=True)
    return code


def varint(data, i):
    v = 0
    while True:
        b = data[i]
        i += 1
        v = (v << 7) | (b & 0x7F)
        if not (b & 0x80):
            return v, i


def first_cpylen(stream: bytes):
    """cpylen of the first window == size of the vanilla source ESM."""
    i = 4
    hdr = stream[i]; i += 1
    if hdr & 0x01:          # VCD_SECONDARY
        i += 1
    if hdr & 0x04:          # VCD_APPHEADER
        n, i = varint(stream, i)
        i += n
    win = stream[i]; i += 1
    if not (win & SRCORTGT):
        return None
    cl, _ = varint(stream, i)
    return cl


def find_frames(data: bytes):
    magics = []
    pos = 0
    while True:
        pos = data.find(LZ4_MAGIC, pos)
        if pos < 0:
            break
        magics.append(pos)
        pos += 4
    return magics


def find_game():
    for lib in STEAM_LIBRARIES:
        cand = lib / "common" / GAME_DIR_NAME
        if (cand / "FalloutNV.exe").exists():
            return cand
    return None


def find_xdelta3():
    for cand in (shutil.which("xdelta3"),
                 Path.home() / ".local/bin/xdelta3"):
        if cand and Path(cand).exists():
            return str(cand)
    return None


def find_mpi(explicit: Path | None):
    """Locate the source .mpi (or the Nexus archive containing it).

    Order: explicit --mpi, legacy repo-local .mpi, then the downloaded
    Nexus archive under downloads/ (this repo's parent parent). The Nexus
    file is a .7z that contains the .mpi (see ensure_mpi).
    """
    if explicit is not None:
        return explicit if explicit.exists() else None
    if MPI.exists():
        return MPI
    dl = HERE.parent.parent / "downloads"
    for pat in ("*Ultimate Edition ESM Fixes*.7z",
                "*Ultimate Edition ESM Fixes*.rar",
                "*Ultimate Edition ESM Fixes*.zip"):
        hits = sorted(dl.glob(pat))
        if hits:
            return hits[0]
    return None


def ensure_mpi(src: Path):
    """If src is an archive, extract its .mpi member (cached) and return it."""
    if src.suffix.lower() not in (".7z", ".rar", ".zip"):
        return src
    seven = shutil.which("7z") or shutil.which("7zz") or shutil.which("7za")
    if seven is None:
        fail("7z not found - needed to unpack the .mpi from the Nexus archive")
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / "Ultimate Edition ESM Fixes Remastered.mpi"
    if not target.exists():
        info(f"extracting {src.name} -> {target}")
        r = subprocess.run([seven, "e", "-y", f"-o{CACHE}", str(src), "*.mpi"],
                           capture_output=True, text=True)
        if r.returncode != 0 or not target.exists():
            msg = (r.stderr or r.stdout).strip()[:200]
            fail(f"7z extract failed: {msg}")
            return None
    return target


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mpi", default="")
    ap.add_argument("--game-dir")
    ap.add_argument("--dest", required=True,
                    help="mod folder (fixed ESMs), e.g. mods/Fixed ESMs")
    ap.add_argument("--force", action="store_true",
                    help="re-apply even if the output ESM already exists")
    args = ap.parse_args()

    src = find_mpi(Path(args.mpi) if args.mpi else None)
    if src is None:
        return fail("mpi not found: pass --mpi, keep it next to port.py, or "
                    "have the Nexus archive in downloads/")
    mpi_path = ensure_mpi(src)
    if mpi_path is None:
        return 1
    game_dir = Path(args.game_dir) if args.game_dir else find_game()
    if game_dir is None:
        return fail("game not found - use --game-dir")
    xd3 = find_xdelta3()
    if xd3 is None:
        return fail("native xdelta3 missing - run build_xdelta3.sh (or install it)")
    try:
        import lz4.frame
    except ImportError:
        return fail("python-lz4 missing - pip install lz4")

    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)

    print(f"Game: {game_dir}")
    print(f"Dest: {dest}")

    data = mpi_path.read_bytes()
    esms = {p.stat().st_size: p for p in (game_dir / "Data").glob("*.esm")}
    frames = find_frames(data)
    applied = 0
    for idx, off in enumerate(frames):
        end = frames[idx + 1] if idx + 1 < len(frames) else len(data)
        try:
            stream = lz4.frame.decompress(data[off:end])
        except Exception:
            continue
        if not stream.startswith(VCDIFF_MAGIC):
            continue
        cl = first_cpylen(stream)
        if cl is None:
            continue
        esm = None
        for size in sorted(esms):
            if size >= cl:
                esm = esms[size]
                break
        if esm is None or (esm.stat().st_size - cl) > 100_000:
            info(f"patch @{off}: cpylen={cl} does not match any vanilla ESM - skipping")
            continue
        out = dest / esm.name
        if out.exists() and not args.force:
            ok(f"{esm.name}: already exists ({out.name}) - skipping (--force to re-apply)")
            continue
        tmp = dest / f".patch_{idx}.xd3"
        tmp.write_bytes(stream)
        r = subprocess.run([xd3, "-d", "-s", str(esm), str(tmp), str(out)],
                           capture_output=True, text=True)
        tmp.unlink(missing_ok=True)
        if r.returncode != 0 or not out.exists():
            fail(f"{esm.name}: xdelta3 failed ({r.stderr.strip()[:120]})")
            continue
        head = out.read_bytes()[:4]
        if head != b"TES4":
            fail(f"{esm.name}: invalid output (not TES4) - wrong source")
            continue
        ok(f"{esm.name} -> {out.name} ({out.stat().st_size:,} bytes)")
        applied += 1

    if applied == 0:
        if (dest / "FalloutNV.esm").exists():
            ok("fixed ESMs already present - nothing to do")
            return 0
        return fail("no patches applied")
    ok(f"Done: {applied} fixed ESMs written to {dest}")
    info("Enable the 'Fixed ESMs' mod in MO2 (press F5 to refresh).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
