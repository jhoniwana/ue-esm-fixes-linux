#!/usr/bin/env python3
"""UE ESM Fixes Remastered — Linux port (reemplaza Installer.exe).

Lee el contenedor `Ultimate Edition ESM Fixes Remastered.mpi`, extrae los
6 parches xdelta3 (envueltos en LZ4 Frame), los aplica con xdelta3 nativo
a los esm vanilla del Data/ del juego y escribe los esm corregidos en la
carpeta destino (mod "Fixed ESMs" de MO2).

El port reproduce exactamente el flujo del Installer.exe original:
  source  = %FNVDATA%\\<esm> (sin validar, sin preprocesar)
  output  = %DESTINATION%\\<esm>

Requisitos:
  - xdelta3 nativo (ver build_xdelta3.sh si falta)
  - python-lz4 (pip install lz4)
"""
from __future__ import annotations

import argparse
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
APPID = "22380"
GAME_DIR_NAME = "Fallout New Vegas"
STEAM_LIBRARIES = [
    Path.home() / ".steam/steam/steamapps",
    Path.home() / ".local/share/Steam/steamapps",
    Path("/mnt/games/steamapps"),
]


def info(msg):
    print(f"  ℹ {msg}", flush=True)


def ok(msg):
    print(f"  ✔ {msg}", flush=True)


def fail(msg, code=1):
    print(f"  ✘ {msg}", flush=True)
    return code


def varint(data, i):
    v = 0
    while True:
        b = data[i]
        i += 1
        v = (v << 7) | (b & 0x7F)
        if not (b & 0x80):
            return v, i


def primer_cpylen(stream: bytes):
    """cpylen del primer window = tamaño del esm source (vanilla)."""
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


def encontrar_frames(data: bytes):
    magics = []
    pos = 0
    while True:
        pos = data.find(LZ4_MAGIC, pos)
        if pos < 0:
            break
        magics.append(pos)
        pos += 4
    return magics


def buscar_juego():
    for lib in STEAM_LIBRARIES:
        cand = lib / "common" / GAME_DIR_NAME
        if (cand / "FalloutNV.exe").exists():
            return cand
    return None


def buscar_xdelta3():
    for cand in (shutil.which("xdelta3"),
                 Path.home() / ".local/bin/xdelta3"):
        if cand and Path(cand).exists():
            return str(cand)
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mpi", default=str(MPI))
    ap.add_argument("--game-dir")
    ap.add_argument("--dest", required=True,
                    help="carpeta del mod (esm corregidos), p.ej. mods/Fixed ESMs")
    ap.add_argument("--force", action="store_true",
                    help="re-aplicar aunque el esm de salida ya exista")
    args = ap.parse_args()

    mpi_path = Path(args.mpi)
    if not mpi_path.exists():
        return fail(f"no encuentro el .mpi: {mpi_path}")
    game_dir = Path(args.game_dir) if args.game_dir else buscar_juego()
    if game_dir is None:
        return fail("no encontré el juego — usá --game-dir")
    xd3 = buscar_xdelta3()
    if xd3 is None:
        return fail("falta xdelta3 nativo — corré build_xdelta3.sh (o instalalo)")
    try:
        import lz4.frame
    except ImportError:
        return fail("falta python-lz4 — pip install lz4")

    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)

    print(f"Juego: {game_dir}")
    print(f"Dest:  {dest}")

    data = mpi_path.read_bytes()
    esms = {p.stat().st_size: p for p in (game_dir / "Data").glob("*.esm")}
    frames = encontrar_frames(data)
    aplicados = 0
    for idx, off in enumerate(frames):
        fin = frames[idx + 1] if idx + 1 < len(frames) else len(data)
        try:
            stream = lz4.frame.decompress(data[off:fin])
        except Exception:
            continue
        if not stream.startswith(VCDIFF_MAGIC):
            continue
        cl = primer_cpylen(stream)
        if cl is None:
            continue
        esm = None
        for tam in sorted(esms):
            if tam >= cl:
                esm = esms[tam]
                break
        if esm is None or (esm.stat().st_size - cl) > 100_000:
            info(f"parche @{off}: cpylen={cl} no matchea ningún esm vanilla — omito")
            continue
        out = dest / esm.name
        if out.exists() and not args.force:
            ok(f"{esm.name}: ya existe ({out.name}) — omito (--force para re-aplicar)")
            continue
        tmp = dest / f".patch_{idx}.xd3"
        tmp.write_bytes(stream)
        r = subprocess.run([xd3, "-d", "-s", str(esm), str(tmp), str(out)],
                           capture_output=True, text=True)
        tmp.unlink(missing_ok=True)
        if r.returncode != 0 or not out.exists():
            fail(f"{esm.name}: xdelta3 falló ({r.stderr.strip()[:120]})")
            continue
        head = out.read_bytes()[:4]
        if head != b"TES4":
            fail(f"{esm.name}: salida inválida (no es TES4) — source incorrecto")
            continue
        ok(f"{esm.name} -> {out.name} ({out.stat().st_size:,} bytes)")
        aplicados += 1

    if aplicados == 0:
        return fail("no se aplicó ningún parche")
    ok(f"Listo: {aplicados} esm corregidos en {dest}")
    info("Activá el mod 'Fixed ESMs' en MO2 (F5 para refrescar).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
