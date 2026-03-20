from __future__ import annotations

import os
import unittest
from unittest.mock import Mock

from openai import APITimeoutError

from eqn2sim_gui.llm_draft import (
    DraftEquationSpec,
    DraftModelSpec,
    DraftSymbol,
    draft_model_spec_from_raw_text,
    draft_model_spec_from_raw_text_with_diagnostics,
    draft_spec_to_form_defaults,
)
from latex_frontend.symbols import DeterministicCompileError


class LlmDraftTests(unittest.TestCase):
    def test_draft_model_spec_uses_structured_output(self) -> None:
        client = Mock()
        request_client = Mock()
        request_client.responses.parse.return_value.output_parsed = DraftEquationSpec(
            equations=[r"m\ddot{x}+b\dot{x}+kx=F"],
        )
        client.with_options.return_value = request_client
        spec = draft_model_spec_from_raw_text(
            "mass spring damper with force input",
            client=client,
            model="test-model",
        )
        self.assertEqual(spec.equations, [r"m\ddot{x}+b\dot{x}+kx=F"])
        self.assertEqual(spec.symbols, [])
        client.with_options.assert_called_once_with(timeout=21.0, max_retries=0)
        request_client.responses.parse.assert_called_once()

    def test_draft_model_spec_raises_fast_timeout_error(self) -> None:
        client = Mock()
        request_client = Mock()
        request_client.responses.parse.side_effect = APITimeoutError(request=Mock())
        client.with_options.return_value = request_client
        prior_timeout = os.environ.get("EQN2SIM_OPENAI_TIMEOUT_SECONDS")
        os.environ["EQN2SIM_OPENAI_TIMEOUT_SECONDS"] = "7"
        try:
            with self.assertRaises(DeterministicCompileError) as context:
                draft_model_spec_from_raw_text("simple system", client=client, model="test-model")
        finally:
            if prior_timeout is None:
                os.environ.pop("EQN2SIM_OPENAI_TIMEOUT_SECONDS", None)
            else:
                os.environ["EQN2SIM_OPENAI_TIMEOUT_SECONDS"] = prior_timeout
        self.assertIn("timed out after 7 seconds", str(context.exception))

    def test_structured_markdown_is_compacted_before_llm_call(self) -> None:
        client = Mock()
        request_client = Mock()
        request_client.responses.parse.return_value.output_parsed = DraftEquationSpec(
            equations=[r"m\ddot{x}+c\dot{x}+kx=u"],
        )
        client.with_options.return_value = request_client
        result = draft_model_spec_from_raw_text_with_diagnostics(
            r"""
            ## Governing Equation
            \[
            m\ddot{x}+c\dot{x}+kx=u
            \]

            ## Definitions
            \[
            \phi=\pi R^2
            \]

            ## Optional
            \[
            f_N=\sqrt{k/m}
            \]

            - \(m\): mass (kg)
            - \(u\): forcing input (N)
            """,
            client=client,
            model="test-model",
        )
        self.assertEqual(result.diagnostics.mode, "llm")
        self.assertEqual(result.spec.equations, [r"m\ddot{x}+c\dot{x}+kx=u"])
        client.with_options.assert_called_once_with(timeout=21.0, max_retries=0)
        request_client.responses.parse.assert_called_once()
        prepared_prompt = request_client.responses.parse.call_args.kwargs["input"][1]["content"]
        self.assertIn("Display equations:", prepared_prompt)
        self.assertIn(r"- m\ddot{x}+c\dot{x}+kx=u", prepared_prompt)
        self.assertIn("Variable and parameter notes:", prepared_prompt)
        self.assertIn("mass (kg)", prepared_prompt)
        self.assertNotIn("## Governing Equation", prepared_prompt)
        self.assertNotIn(r"f_N=\sqrt{k/m}", prepared_prompt)
        self.assertEqual(result.diagnostics.prepared_input_chars, len(prepared_prompt))

    def test_raw_equation_lines_get_direct_cleanup_prompt(self) -> None:
        client = Mock()
        request_client = Mock()
        request_client.responses.parse.return_value.output_parsed = DraftEquationSpec(
            equations=[r"m\ddot{x}+k x=0"],
        )
        client.with_options.return_value = request_client
        draft_model_spec_from_raw_text_with_diagnostics(
            "m\\ddot{x}+k x=0\nc\\dot{x}+k_2 x=0",
            client=client,
            model="test-model",
        )
        prepared_prompt = request_client.responses.parse.call_args.kwargs["input"][1]["content"]
        self.assertIn("Candidate equations provided directly:", prepared_prompt)
        self.assertIn(r"- m\ddot{x}+k x=0", prepared_prompt)
        self.assertIn(r"- c\dot{x}+k_2 x=0", prepared_prompt)
        self.assertIn("Do not infer extra equations", prepared_prompt)

    def test_filters_approximate_value_notes_from_llm_equations(self) -> None:
        client = Mock()
        request_client = Mock()
        request_client.responses.parse.return_value.output_parsed = DraftEquationSpec(
            equations=[
                r"m\ddot{x}+c\dot{x}+kx=u",
                r"\phi \approx 1.23",
                r"\cos\theta \approx 0.707",
            ],
        )
        client.with_options.return_value = request_client
        result = draft_model_spec_from_raw_text_with_diagnostics(
            "single governing equation with a few numeric notes",
            client=client,
            model="test-model",
        )
        self.assertEqual(result.spec.equations, [r"m\ddot{x}+c\dot{x}+kx=u"])
        self.assertEqual(result.diagnostics.discarded_equation_count, 2)

    def test_draft_spec_converts_to_form_defaults(self) -> None:
        spec = DraftModelSpec(
            equations=[r"\ddot{\theta}+\frac{g}{L}\sin(\theta)=0"],
            symbols=[
                DraftSymbol(name="theta", role="state"),
                DraftSymbol(name="g", role="known_constant", value=9.81),
                DraftSymbol(name="L", role="parameter"),
            ],
        )
        latex_text, symbol_values = draft_spec_to_form_defaults(spec)
        self.assertEqual(latex_text, r"\ddot{\theta}+\frac{g}{L}\sin(\theta)=0")
        self.assertEqual(symbol_values["theta"]["role"], "state")
        self.assertEqual(symbol_values["g"]["value"], 9.81)


if __name__ == "__main__":
    unittest.main()
