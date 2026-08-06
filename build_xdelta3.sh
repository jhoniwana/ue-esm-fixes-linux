#!/usr/bin/env bash
# Compila xdelta3 3.1.0 desde fuente a ~/.local/bin (sin sudo).
set -euo pipefail

XD3="$HOME/.local/bin/xdelta3"
if [ -x "$XD3" ]; then
  echo "xdelta3 ya está instalado: $XD3"
  exit 0
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "Clonando xdelta3 v3.1.0..."
git clone --depth 1 --branch v3.1.0 https://github.com/jmacd/xdelta "$TMP/xdelta" 2>&1 | tail -1

cd "$TMP/xdelta/xdelta3"
echo "Configurando (autotools)..."
autoreconf -i >/dev/null 2>&1
./configure --prefix="$HOME/.local" >/dev/null 2>&1
echo "Compilando..."
make -j"$(nproc)" >/dev/null 2>&1
make install >/dev/null 2>&1

"$XD3" -V 2>&1 | head -1
echo "OK: $XD3"
