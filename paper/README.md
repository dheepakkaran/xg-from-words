# The paper

IEEE conference format (`IEEEtran`, `[conference]`), two columns, 10 pages
including the appendix. arXiv imposes no format of its own, so this is a free
choice; IEEE is the more widely recognised of the two and does not look out of
place beside anything.

The previous draft was Springer LNCS, single-column, and the conversion was
not only a class change. Six tables that fit a 122mm LNCS measure overflow a
3.5in IEEE column, and the figures had to be redrawn at IEEE dimensions -- the
schematic at 7.00in for `figure*`, the other two at 3.42in for a single
column -- because rescaling a figure takes its label sizes with it. That
history is in the git log if the LNCS version is ever wanted back.

## Build

```sh
latexmk -pdf paper.tex
```

Needs `IEEEtran.cls` and `IEEEtran.bst`, both in TeX Live. Overleaf has them
built in if you would rather not build locally.

## Figures

`figures.py` builds all three. They read their values from
`data/proc/xg_validation.parquet` at render time rather than carrying numbers
as literals -- the first draft of Figure 1 had invented coordinates and an
invented commentary line in it, which is not a thing a paper may contain. It
now shows a real shot, Ramsey for Arsenal against Manchester United, found by
its StatsBomb location.

Colour is decoration in these figures and never identity. The palette was
checked against the data-viz validator and passes, but grayscale is a stricter
constraint than any check it runs: two of the three hues are 0.045 apart in
relative luminance, which prints as gray 142 against gray 152. Every series
therefore carries a marker shape, a line style and a label as well. Remove the
colour and the figures still read, which is the only test that matters for a
printed proceedings.

## Submitting to arXiv

```sh
./paper/make_arxiv.sh
```

Builds `arxiv.tar.gz` and then proves it by extracting it into an empty
directory and compiling there **without running bibtex**, which is what arXiv
does. If the citations would come out as `[?]` the script fails instead of
letting you find out after submitting.

The package is `paper.tex`, `paper.bbl` and the three figure PDFs. `refs.bib`
is deliberately not in it: arXiv compiles against the `.bbl` you upload and
never runs bibtex, so shipping the `.bib` without the `.bbl` is the standard
way to publish a paper full of `[?]`. `IEEEtran.cls` and `IEEEtran.bst` are
already on arXiv and are not shipped either.

Both outputs are gitignored -- run the script, do not commit the tarball.

## Provenance

`numbers.txt` is every figure in the paper, dumped from the artefacts it came
from, with the command that produced it. Nothing in `paper.tex` was typed from
memory. Regenerate with the snippets recorded in that file, or rebuild the
whole pipeline with `../rebuild.sh`.

## Before submitting

- [x] ORCID registered: **0009-0007-2152-8401**, in `paper.tex`. Checksum
      validated (ISO/IEC 7064 MOD 11-2) and resolved against the public API,
      which returns given `DHEEPAK KARAN`, family `ELUMALAI SANTHAKUMARI` --
      the split the bib entry declares
- [ ] On orcid.org: set the name to title case (it is stored in capitals, and
      that is what citation exports will carry), and add Northeastern under
      Education
- [ ] Link the ORCID in arXiv account settings once the account exists, so the
      preprint carries a verified identifier
- [x] Affiliation: Dept. of Electrical and Computer Engineering,
      College of Engineering, Northeastern University
- [ ] arXiv needs an endorsement for a first submission in `cs.LG` — a
      `northeastern.edu` address may clear it automatically; you find out on
      registration
- [ ] Suggested categories: `stat.AP` primary, `cs.LG` cross-list
