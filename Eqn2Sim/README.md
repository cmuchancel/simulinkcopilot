# Eqn2Sim Paper

This folder contains an ASME conference-style manuscript for the Eqn2Sim project.

Files:
- `Eqn2Sim.tex`: main manuscript source
- `references.bib`: bibliography database
- `asmeconf.cls`, `asmeconf.bst`: local ASME class/style files copied from a template installed elsewhere on this machine
- `figures/`: regenerated figures and artifact images used in the paper

Build:

```bash
cd Eqn2Sim
latexmk -pdf Eqn2Sim.tex
```

Output:
- `Eqn2Sim.pdf`
