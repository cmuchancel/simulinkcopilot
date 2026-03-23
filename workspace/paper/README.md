# Eqn2Sim Paper

This folder contains an ASME conference-style manuscript for the Eqn2Sim project.

Files:
- `Eqn2Sim.tex`: main manuscript source
- `references.bib`: bibliography database
- `asmeconf.cls`, `asmeconf.bst`: local ASME class/style files copied from a template installed elsewhere on this machine
- `figures/`: regenerated figures and artifact images used in the paper
- `related_work/`: downloaded PDFs and indexing notes for the literature pass

Build:

```bash
cd workspace/paper
latexmk -pdf Eqn2Sim.tex
```

Output:
- `Eqn2Sim.pdf`
