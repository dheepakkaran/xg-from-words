#!/bin/sh
# xgboost's macOS wheel hard-codes an rpath to Homebrew's libomp. There is no
# Homebrew on this machine, so a copy taken from the torch wheel is put on the
# dynamic loader path here. DYLD_LIBRARY_PATH is read at process start, which
# is why this has to be a wrapper rather than something set inside Python.
DIR=$(cd "$(dirname "$0")" && pwd)
export DYLD_LIBRARY_PATH="$DIR/vendor/lib:$DYLD_LIBRARY_PATH"
exec "$DIR/venv/bin/python" "$@"
