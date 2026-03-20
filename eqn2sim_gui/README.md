# Eqn2Sim Local GUI

Launch the local metadata-first GUI with:

```bash
python3 -m scripts.run_eqn2sim_gui
```

Then open:

```text
http://127.0.0.1:5001
```

Workflow:

1. Paste raw system text and click `Generate Structured Output`.
2. Inspect the returned structured JSON, then review the generated LaTeX and rendered equation preview.
3. Let the GUI deterministically extract symbols and states from the LaTeX box.
4. Fill in every required symbol value and every state initial condition.
5. Once the readiness check passes, click `Generate Simulink Model`.
6. Click `Download .slx`.

Outputs:

- the GUI saves the raw LaTeX input
- it writes `gui_metadata.json`
- it writes `validated_model_spec.json`
- it writes `simulink_model_dict.json`
- it builds a downloadable `.slx` file in the run artifact directory
- it confirms the normalized equations, canonical equation strings, detected state chain, and user-approved symbol metadata

Notes:

- the GUI is metadata-first: explicit user roles override heuristic symbol inference
- derivative-bearing symbols must be marked as `state`
- the Simulink build button stays disabled until the current form is complete enough to build
- symbol names are preserved as user-facing identifiers
- the validated spec and model dictionary remain on disk alongside the generated `.slx`
- LLM drafting uses `OPENAI_API_KEY` from your environment or `.env`
