#!/bin/sh
# Rebuild figures, data-driven tables and the SSRN PDF. Tectonic: conda create -n tectonic -c conda-forge tectonic
set -e
cd "$(dirname "$0")"
python -W ignore figs.py
tectonic note.tex
