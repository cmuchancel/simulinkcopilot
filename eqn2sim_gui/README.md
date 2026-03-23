# Eqn2Sim Local GUI

Launch the local metadata-first GUI with:

```bash
python3 run_eqn2sim_gui.py
```

Then open:

```text
http://127.0.0.1:5001
```

Workflow:

1. Paste raw system text and click `Draft Structured Equations`.
2. Review the generated equations in the LaTeX box and confirm the rendered preview directly below it.
3. Let the GUI deterministically extract symbols and states from the equation box.
4. Fill in or edit the symbol values, roles, units, and state initial conditions.
5. Click `Validate Representation`.
6. Use the saved validated spec for downstream build/simulation steps.

Outputs:

- the GUI saves the raw LaTeX input
- it writes `gui_metadata.json`
- it writes `validated_model_spec.json`
- it confirms the normalized equations, canonical equation strings, detected state chain, and user-approved symbol metadata

Notes:

- the GUI is metadata-first: explicit user roles override heuristic symbol inference
- derivative-bearing symbols must be marked as `state`
- symbol names are preserved as user-facing identifiers
- the validated spec remains on disk in the GUI run artifact directory
- LLM drafting uses `OPENAI_API_KEY` from your environment or `.env`
