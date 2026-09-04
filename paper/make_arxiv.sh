#!/bin/sh
# Build the arXiv upload and prove it compiles the way arXiv will compile it.
#
# The one that catches people: arXiv does not run bibtex. It compiles your
# .tex against the .bbl you upload, so a submission carrying refs.bib but no
# paper.bbl produces a paper with [?] in place of every citation. The .bbl is
# in the package for that reason and refs.bib deliberately is not.
#
# IEEEtran.cls and IEEEtran.bst are both on arXiv already, so neither is
# shipped. Figures go as PDF, which arXiv accepts.
set -e
cd "$(dirname "$0")"

echo "== building locally =="
pdflatex -interaction=nonstopmode paper.tex >/dev/null
bibtex paper >/dev/null
pdflatex -interaction=nonstopmode paper.tex >/dev/null
pdflatex -interaction=nonstopmode paper.tex >/dev/null

echo "== assembling =="
rm -rf arxiv arxiv.tar.gz
mkdir arxiv
cp paper.tex paper.bbl fig1_schematic.pdf fig2_reliability.pdf \
   fig3_drift.pdf arxiv/
# COPYFILE_DISABLE stops macOS tar writing an AppleDouble ._file beside every
# entry that carries extended attributes; arXiv would list those as extraneous
# files. Naming the files rather than "." also drops the ./ directory entry.
COPYFILE_DISABLE=1 tar -czf arxiv.tar.gz -C arxiv \
  paper.tex paper.bbl fig1_schematic.pdf fig2_reliability.pdf fig3_drift.pdf

echo "== verifying in an empty directory, with no bibtex =="
T=$(mktemp -d)
tar -xzf arxiv.tar.gz -C "$T"
( cd "$T" && pdflatex -interaction=nonstopmode paper.tex >/dev/null \
          && pdflatex -interaction=nonstopmode paper.tex >/dev/null )
BAD=$(grep -cE "undefined" "$T/paper.log" || true)
PAGES=$(grep -o "paper.pdf ([0-9]* pages" "$T/paper.log" | grep -o "[0-9]*")
rm -rf "$T"

echo
echo "  pages                : $PAGES"
echo "  undefined references : $BAD"
if [ "$BAD" != "0" ]; then
  echo "  FAILED -- the package would upload with broken citations" >&2
  exit 1
fi
echo
echo "== the upload, as arXiv will see it =="
tar -tzf arxiv.tar.gz | sed "s/^/  /"
JUNK=$(tar -tzf arxiv.tar.gz | grep -cE "(^|/)[._]|DS_Store" || true)
echo "  macOS metadata entries: $JUNK"
if [ "$JUNK" != "0" ]; then
  echo "  FAILED -- extraneous files in the upload" >&2
  exit 1
fi

echo
echo "  arxiv.tar.gz is ready to upload"
ls -la arxiv.tar.gz
