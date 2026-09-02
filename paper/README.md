# The paper

Springer LNCS (`llncs`), 12 pages. arXiv imposes no format of its own; LNCS is
used because the natural venue for this work is **MLSA @ ECML/PKDD**, which is
where Robberechts and Davis published the paper this one builds on, and because
it renders correctly on arXiv as-is.

## Build

```sh
latexmk -pdf paper.tex
```

Needs `llncs.cls` and `splncs04.bst` (both in TeX Live). Overleaf has them
built in if you would rather not build locally.

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
- [ ] Confirm the affiliation line
- [ ] arXiv needs an endorsement for a first submission in `cs.LG` — a
      `northeastern.edu` address may clear it automatically; you find out on
      registration
- [ ] Suggested categories: `stat.AP` primary, `cs.LG` cross-list
