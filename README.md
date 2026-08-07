# Ultimate Edition ESM Fixes Remastered — Linux Port

Native Linux port of the installer of [Ultimate Edition ESM Fixes Remastered](https://www.nexusmods.com/newvegas/mods/92289) (Kazopert/RoyBatty). No Wine, no Proton: extracts the patches from the `.mpi` and applies them with `xdelta3` built for Linux.

## What it does

Reproduces exactly the flow of the original `Installer.exe` (verified against its internal manifest `_package/index.json`):

1. Reads the `Ultimate Edition ESM Fixes Remastered.mpi` container (custom BSA-like).
2. The 6 `.xd3` patches are **compressed with LZ4 Frames** inside the container (magic `04 22 4D 18`); decompressed with `python-lz4`.
3. Each VCDIFF stream (xdelta3, lzma secondary compressor) declares in its first window the `cpylen` = size of the vanilla source ESM → matched against the game's `Data/*.esm`.
4. `xdelta3 -d -s <vanilla> <patch> <fixed>` → fixed ESMs written to the destination folder.

Verified outputs (v1.03, Steam-validated game):

| ESM | vanilla | fixed |
|---|---|---|
| FalloutNV.esm | 245,650,747 | 330,921,877 |
| DeadMoney.esm | 6,274,851 | 7,303,362 |
| HonestHearts.esm | 17,308,500 | 35,736,867 |
| OldWorldBlues.esm | 16,202,800 | 32,923,146 |
| LonesomeRoad.esm | 25,676,818 | 40,265,999 |
| GunRunnersArsenal.esm | 252,445 | 252,293 |

Note: the patches do NOT validate the ESMs (only `FalloutNV.exe`, and our exe matches the supported hash `0021023E...`). The ESMs must be the unmodified English vanilla ones from Steam/GOG/EGS.

## ⚠️ CRITICAL: the ESMs must match the CURRENT Steam depot (learned the hard way)

xdelta3 patches are **position-dependent**: a source that differs from the patch's
vanilla by even a few bytes (e.g. ESMs copied from another machine/install) produces
an output that LOOKS valid (TES4 header ok, correct size) but is **silently corrupt** —
records missing (FalloutNV: 233k records instead of 465k, ALL dialogue records gone)
→ the game crashes at startup in the dialogue/quest init (`ACCESS_VIOLATION` at
`0x00AA991C`, "Last modified by YUP" contexts).

**Symptoms of a bad build**: count the records of the output:

```bash
# FalloutNV fixed must have ~465k records incl. ~18k DIALOG; a corrupt build has
# ~233k records and 0 DIALOG records.
python3 - <<'EOF'
import struct
d = open('Fixed ESMs/FalloutNV.esm','rb').read()
off = n = dial = 0
while off + 24 <= len(d):
    t = d[off:off+4]; s = struct.unpack_from('<I', d, off+4)[0]
    if t == b'TES4': off += 24+s; continue
    if t == b'GRUP': off += 24; continue
    if s > 100_000_000: break
    n += 1; dial += (t == b'DIAL'); off += 24+s
print(n, 'records,', dial, 'DIALOG')
EOF
```

**Fix**: run `steam steam://validate/22380` (Steam rewrites the ESMs to the exact
depot content) and re-run `port.py --force`. Note: the validate also reverts the
4GB patch and the decompressed BSAs → re-run those steps afterwards.

## Requirements

- Native `xdelta3` → `./build_xdelta3.sh` (builds 3.1.0 to `~/.local/bin`, no sudo)
- `python-lz4` → `pip install lz4`
- `7z` (`p7zip`/`7-zip`) — only if the source is the Nexus `.7z` (it is unpacked automatically)
- The game with vanilla ESMs (Steam: `steamapps/common/Fallout New Vegas/Data`)
- The mod payload: the `.mpi` (or the Nexus `.7z` that contains it) — see below

The `.mpi` (220 MB) is **not** tracked in this repo: download `Ultimate Edition ESM
Fixes Remastered` from Nexus (mod 92289) and either keep the downloaded `.7z` under
`downloads/` next to the vnv workspace or pass it with `--mpi`. It is unpacked to
`~/.cache/vnv-uefix/` automatically (7z must be installed).

## Usage

```bash
python3 port.py --dest "$HOME/.local/share/modorganizer2/mods/Fixed ESMs"
```

Options:

- `--game-dir DIR` — if the game is not in the default Steam paths
- `--mpi FILE` — the `.mpi` (or the Nexus `.7z`/`.rar`/`.zip` containing it); auto-detected in `downloads/`
- `--force` — re-apply even if the output ESMs already exist

Then in MO2: press F5 to refresh and enable the **Fixed ESMs** mod.

## Repository files

| File | Description |
|---|---|
| `port.py` | The port (LZ4 extraction + xdelta3 apply) |
| `build_xdelta3.sh` | Builds native xdelta3 from source |
| `Installer.exe` | Original (reference/diagnostics, never executed) |
| `xdelta3.dll` | Required by the original Installer.exe (reference) |

## How it was figured out

- The `.mpi` is NOT a standard BSA v105: unreadable records + "fake" VCDIFF magics inside the data → they were **LZ4 blocks** (the `ERROR_blockMode_invalid` errors from the .exe are `lz4frame` codes, not zstd).
- The real manifest (`_package/index.json`, LZ4-compressed): `Assets` maps 1:1 `%FNVDATA%\<esm>` against `./<esm>`; `Checks` only validates `FalloutNV.exe` (8 SHA1s: Steam/GOG/EGS patched or not); the ESMs go raw into `xd3_decode_memory`.
- No patch chain, no pre-generated ESMs: every patch is flat against the vanilla file.
- Validation: the output of this port is **SHA1-identical** to the output of the official `Installer.exe` run under Proton (all 6 ESMs).
