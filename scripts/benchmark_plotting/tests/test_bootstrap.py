"""Checks against known results and an explicit small resampling recipe."""
import sys
from pathlib import Path
import unittest
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import bootstrap_median_change, summarize_bootstrap
from data import Experiment
import pandas as pd


class BootstrapTests(unittest.TestCase):
    def test_constant_samples_have_exact_change(self):
        result = bootstrap_median_change([100]*20, [90]*20)
        for field in ("percent", "ci_low", "ci_high"):
            self.assertAlmostEqual(result[field], -10)
        self.assertEqual(result["status"], "ok")

    def test_matches_explicit_recipe_and_uses_both_samples(self):
        a, b = np.array([2., 3., 7.]), np.array([1., 4., 6., 8.])
        rng = np.random.default_rng(23)
        med_a = np.median(rng.choice(a, (200, 3), replace=True), axis=1)
        med_b = np.median(rng.choice(b, (200, 4), replace=True), axis=1)
        expected = np.quantile(100*(med_b/med_a-1), [.025, .975])
        result = bootstrap_median_change(a, b, resamples=200, seed=23)
        np.testing.assert_allclose([result["ci_low"], result["ci_high"]], expected)
        # Even a constant comparison must reflect uncertainty in the baseline.
        varying = bootstrap_median_change(a, [3., 3., 3.], seed=23)
        self.assertLess(varying["ci_low"], varying["ci_high"])

    def test_repeatability_and_scale_invariance(self):
        a, b = np.array([2., 3., 7.]), np.array([1., 4., 6.])
        result = bootstrap_median_change(a, b, seed=9)
        self.assertEqual(result, bootstrap_median_change(a, b, seed=9))
        scaled = bootstrap_median_change(100*a, 100*b, seed=9)
        np.testing.assert_allclose([result[k] for k in ("percent", "ci_low", "ci_high")],
                                   [scaled[k] for k in ("percent", "ci_low", "ci_high")])

    def test_unavailable_intervals_are_explicit(self):
        cases = [([], [1,2], "missing_data"), ([0,0], [1,2], "zero_baseline_median"),
                 ([1], [1,2], "insufficient_samples"),
                 ([0,0,1,1,1], [1,2], "zero_resampled_baseline_median")]
        for a,b,status in cases:
            with self.subTest(status=status):
                result = bootstrap_median_change(a,b)
                self.assertEqual(result["status"], status)
                self.assertTrue(np.isnan(result["ci_low"]))

    def test_bad_options_and_values(self):
        for options in ({"resamples":0}, {"confidence":1}, {"seed":-1}):
            with self.assertRaises(ValueError):
                bootstrap_median_change([1,2],[1,2],**options)
        for invalid in ([np.nan], [-1], [[1,2]]):
            with self.assertRaises(ValueError):
                bootstrap_median_change(invalid,[1,2])

    def test_summary_is_stable_across_query_selection_and_pagination(self):
        observations = pd.DataFrame([
            {"query": q, "round": i, "metric": "total_response_time", "value_seconds": v}
            for q in ("q1.pb", "q2.pb") for i,v in enumerate([1.,2.,5.],1)])
        experiment = Experiment("sample", {}, {"q1.pb", "q2.pb"}, observations, pd.DataFrame())
        full = summarize_bootstrap(experiment, experiment, ["q1.pb", "q2.pb"], "total_response_time", resamples=200)
        selected = summarize_bootstrap(experiment, experiment, ["q2.pb"], "total_response_time", resamples=200)
        pd.testing.assert_series_equal(full.loc["q2.pb"], selected.loc["q2.pb"])

    def test_plot_draws_estimate_and_interval_separately(self):
        from plots import plot_change_ci
        import matplotlib.pyplot as plt
        experiment = Experiment("sample", {}, {"q1.pb"}, pd.DataFrame(), pd.DataFrame())
        # A percentile interval can exclude the original point estimate.
        summary = pd.DataFrame([{"query":"q1.pb", "percent":-10., "ci_low":-8., "ci_high":-3.,
                                 "baseline_n":20, "comparison_n":20, "status":"ok"}]).set_index("query")
        figure = plot_change_ci((experiment,experiment),["q1.pb"],"total_response_time",summary=summary)
        self.addCleanup(plt.close,figure)
        self.assertTrue(any("-10.00% [-8.00, -3.00]" in t.get_text() for t in figure.axes[0].texts))

    def test_config_accepts_bootstrap_and_fingerprint_tracks_options(self):
        import json
        import tempfile
        from plot_benchmarks import read_config, rendering_fingerprint
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"config.json"
            document = {"baseline":{"directory":"a","label":"A"}, "comparison":{"directory":"b","label":"B"},
                        "plots":["change_ci"], "bootstrap":{"resamples":200}}
            path.write_text(json.dumps(document))
            config = read_config(path)
            self.assertEqual(config["bootstrap"], {"resamples":200,"confidence":.95,"seed":0})
            inputs = {role:{"sha256":role} for role in ("baseline","comparison")}
            original = rendering_fingerprint(config,inputs,["q1.pb"],environment={},code_hashes={})
            changed = {**config,"bootstrap":{**config["bootstrap"],"seed":1}}
            self.assertNotEqual(original, rendering_fingerprint(changed,inputs,["q1.pb"],environment={},code_hashes={}))
            document["bootstrap"] = {"resamples":0}
            path.write_text(json.dumps(document))
            with self.assertRaises(ValueError):
                read_config(path)
