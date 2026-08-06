# Ultimate Edition ESM Fixes Remastered — Linux Port

Port nativo a Linux del instalador de [Ultimate Edition ESM Fixes Remastered](https://www.nexusmods.com/newvegas/mods/92289) (Kazopert/RoyBatty). Sin Wine, sin Proton: extrae los parches del `.mpi` y los aplica con `xdelta3` compilado para Linux.

## Qué hace

Reproduce exactamente el flujo del `Installer.exe` original (verificado contra su manifiesto interno `_package/index.json`):

1. Lee el contenedor `Ultimate Edition ESM Fixes Remastered.mpi` (BSA-like custom).
2. Los 6 parches `.xd3` están **comprimidos con LZ4 Frame** dentro del contenedor (magic `04 22 4D 18`); se descomprimen con `python-lz4`.
3. Cada stream VCDIFF (xdelta3, compresor secundario lzma) declara en su primer window el `cpylen` = tamaño del esm vanilla fuente → se matchea contra el `Data/*.esm` del juego.
4. `xdelta3 -d -s <vanilla> <patch> <corregido>` → esm corregidos en la carpeta destino.

Outputs verificados (v1.03, juego Steam validado):

| esm | vanilla | corregido |
|---|---|---|
| FalloutNV.esm | 245,650,747 | 330,921,877 |
| DeadMoney.esm | 6,274,851 | 7,303,362 |
| HonestHearts.esm | 17,308,500 | 35,736,867 |
| OldWorldBlues.esm | 16,202,800 | 32,923,146 |
| LonesomeRoad.esm | 25,676,818 | 40,265,999 |
| GunRunnersArsenal.esm | 252,445 | 252,293 |

Nota: los parches NO validan los esm (solo el `FalloutNV.exe`, y nuestro exe matchea el hash soportado `0021023E...`). Los esm deben ser los vanilla de Steam/GOG/EGS en inglés, sin modificar.

## Requisitos

- `xdelta3` nativo → `./build_xdelta3.sh` (compila 3.1.0 a `~/.local/bin`, sin sudo)
- `python-lz4` → `pip install lz4`
- El juego con los esm vanilla (Steam: `steamapps/common/Fallout New Vegas/Data`)

## Uso

```bash
python3 port.py --dest "$HOME/.local/share/modorganizer2/mods/Fixed ESMs"
```

Opciones:

- `--game-dir DIR` — si el juego no está en las rutas Steam por defecto
- `--mpi FILE` — si el `.mpi` no está junto al script
- `--force` — re-aplicar aunque los esm de salida ya existan

Luego en MO2: F5 para refrescar y activar el mod **Fixed ESMs**.

## Archivos del repo

| Archivo | Descripción |
|---|---|
| `port.py` | El port (extracción LZ4 + aplicación xdelta3) |
| `build_xdelta3.sh` | Compila xdelta3 nativo desde fuente |
| `Installer.exe` | Original (referencia/diagnóstico, no se ejecuta) |
| `Ultimate Edition ESM Fixes Remastered.mpi` | Payload del mod (parches) |

## Cómo se descubrió

- El `.mpi` NO es un BSA v105 estándar: records ilegibles + magics VCDIFF "falsos" dentro de los datos → eran **bloques LZ4** (los errores `ERROR_blockMode_invalid` del .exe son códigos de `lz4frame`, no de zstd).
- El manifiesto real (`_package/index.json`, comprimido con LZ4): `Assets` mapea 1:1 `%FNVDATA%\<esm>` contra `./<esm>`; `Checks` solo valida `FalloutNV.exe` (8 SHA1: Steam/GOG/EGS parcheados o no); los esm van crudos a `xd3_decode_memory`.
- Sin cadena de parches, sin esm pre-generados: cada parche es plano contra el vanilla.
