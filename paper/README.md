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

- [ ] Register an ORCID at <https://orcid.org> and uncomment the
      `\orcidID{}` line in `paper.tex`. It is free and open to anyone --
      Northeastern's own guide just points you at orcid.org. Register with the
      NU address as primary and **add a personal address as a second email**,
      because the NU one stops working after graduation and an ORCID is meant
      to last a career. Then link it in your arXiv account settings.
      This matters more than usual here: "Dheepak Karan Elumalai Santhakumari"
      is exactly the kind of name indexers split wrong, and an ORCID is the
      only thing that fixes that permanently
- [ ] Confirm the affiliation line
- [ ] arXiv needs an endorsement for a first submission in `cs.LG` — a
      `northeastern.edu` address may clear it automatically; you find out on
      registration
- [ ] Suggested categories: `stat.AP` primary, `cs.LG` cross-list
