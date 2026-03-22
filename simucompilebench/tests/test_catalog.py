from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from simucompilebench.catalog import (
    _derivative_latex,
    _join_terms,
    _mass_spring_chain_latex,
    _scalar_higher_order_spec,
    build_simucompilebench_specs,
    write_benchmark_dataset,
)


class BenchmarkCatalogTests(unittest.TestCase):
    def test_catalog_contains_all_tiers(self) -> None:
        specs = build_simucompilebench_specs()
        tiers = {spec.tier for spec in specs}
        self.assertIn("tier1_verified", tiers)
        self.assertIn("tier2_structural", tiers)
        self.assertIn("tier3_adversarial", tiers)
        self.assertGreaterEqual(len(specs), 250)

    def test_dataset_writer_creates_metadata_files(self) -> None:
        specs = build_simucompilebench_specs(include_legacy=False)[:3]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "benchmark"
            data_path = Path(temp_dir) / "systems.json"
            stale_dir = root / "tier1_verified"
            stale_dir.mkdir(parents=True, exist_ok=True)
            (stale_dir / "stale.txt").write_text("old", encoding="utf-8")
            manifest = write_benchmark_dataset(specs, root_dir=root, data_path=data_path)
            self.assertTrue((root / "index.json").exists())
            for spec in specs:
                self.assertTrue((root / spec.tier / spec.system_id / "metadata.json").exists())
                self.assertTrue((root / spec.tier / spec.system_id / "equations.tex").exists())
            self.assertEqual(sum(manifest["tier_counts"].values()), len(specs))
            self.assertFalse((stale_dir / "stale.txt").exists())

    def test_catalog_helper_functions_cover_edge_cases(self) -> None:
        self.assertEqual(_join_terms([]), "0")
        self.assertEqual(_derivative_latex("x", 0), "x")
        self.assertEqual(_derivative_latex("x", 3), r"\frac{d^3 x}{dt^3}")

        higher_order = _scalar_higher_order_spec(4, nonlinear=False)
        self.assertIn("x_ddot", higher_order.initial_conditions)
        self.assertIn("x_d3", higher_order.initial_conditions)
        second_order = _scalar_higher_order_spec(2, nonlinear=True)
        self.assertNotIn("x_ddot", second_order.initial_conditions)

        self.assertIn("0", _mass_spring_chain_latex(1, damped=False))


if __name__ == "__main__":
    unittest.main()
