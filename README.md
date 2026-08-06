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

## Requirements

- Native `xdelta3` → `./build_xdelta3.sh` (builds 3.1.0 to `~/.local/bin`, no sudo)
- `python-lz4` → `pip install lz4`
- The game with vanilla ESMs (Steam: `steamapps/common/Fallout New Vegas/Data`)

## Usage

```bash
python3 port.py --dest "$HOME/.local/share/modorganizer2/mods/Fixed ESMs"
```

Options:

- `--game-dir DIR` — if the game is not in the default Steam paths
- `--mpi FILE` — if the `.mpi` is not next to the script
- `--force` — re-apply even if the output ESMs already exist

Then in MO2: press F5 to refresh and enable the **Fixed ESMs** mod.

## Repository files

| File | Description |
|---|---|
| `port.py` | The port (LZ4 extraction + xdelta3 apply) |
| `build_xdelta3.sh` | Builds native xdelta3 from source |
| `Installer.exe` | Original (reference/diagnostics, never executed) |
| `Ultimate Edition ESM Fixes Remastered.mpi` | Mod payload (patches) |
| `xdelta3.dll` | Required by the original Installer.exe (reference) |

## How it was figured out

- The `.mpi` is NOT a standard BSA v105: unreadable records + "fake" VCDIFF magics inside the data → they were **LZ4 blocks** (the `ERROR_blockMode_invalid` errors from the .exe are `lz4frame` codes, not zstd).
- The real manifest (`_package/index.json`, LZ4-compressed): `Assets` maps 1:1 `%FNVDATA%\<esm>` against `./<esm>`; `Checks` only validates `FalloutNV.exe` (8 SHA1s: Steam/GOG/EGS patched or not); the ESMs go raw into `xd3_decode_memory`.
- No patch chain, no pre-generated ESMs: every patch is flat against the vanilla file.
- Validation: the output of this port is **SHA1-identical** to the output of the official `Installer.exe` run under Proton (all 6 ESMs).
