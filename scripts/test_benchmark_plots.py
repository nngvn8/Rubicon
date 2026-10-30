"""Focused checks for comparison semantics and malformed benchmark data."""
import json
from pathlib import Path
import tempfile
import unittest

from benchmark_data import check_comparison, load_experiment, summarize, summarize_changes, values
from plot_benchmarks import read_config


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def load(self, samples, failures=None, workers=48, query="q1.pb", label="example"):
        directory = self.root / label
        directory.mkdir(exist_ok=True)
        document = {
            "metadata": {"workers_per_cu": workers, "scale_factor": 2, "measured_rounds": 3},
            "queries": {query: {"samples": samples, "failures": failures or [], "summary": {"ignored": 999}}},
        }
        (directory / "results.json").write_text(json.dumps(document))
        return load_experiment(directory, label)

    def test_median_change_and_null_metric(self):
        baseline = self.load([{"round": 1, "total_response_time": 1}, {"round": 2, "total_response_time": 2}, {"round": 3, "total_response_time": 100}], label="a")
        comparison = self.load([{"round": 1, "total_response_time": 1}, {"round": 3, "total_response_time": 1}], label="b")
        row = summarize(baseline, comparison, ["q1.pb"], "total_response_time").iloc[0]
        self.assertEqual(row["percent"], -50)
        self.assertEqual(row["difference"], -1)
        self.assertEqual(row["comparison_n"], 2)
        self.assertTrue(values(comparison, "q1.pb", "plan_duration").isna().all())

    def test_unpaired_change_quantiles(self):
        baseline = self.load([{"round": 1, "total_response_time": 2}, {"round": 2, "total_response_time": 4}], label="a")
        comparison = self.load([{"round": 1, "total_response_time": 1}, {"round": 2, "total_response_time": 6}], label="b")
        row = summarize_changes(baseline, comparison, ["q1.pb"], "total_response_time").iloc[0]
        # All four changes: -75, -50, 50, 200; no round pairing.
        for key, expected in {"p05": -71.25, "q1": -56.25, "median": 0, "q3": 87.5, "p95": 177.5}.items():
            self.assertAlmostEqual(row[key], expected)
        self.assertAlmostEqual(row["p05_delta"], -2.7)
        self.assertAlmostEqual(row["p95_delta"], 3.7)
        self.assertEqual(row["baseline_n"], 2)
        missing = summarize_changes(baseline, comparison, ["q1.pb"], "plan_duration")
        self.assertTrue(missing[["p05", "median", "p95"]].isna().all().all())
        baseline = self.load([{"round": 1, "total_response_time": 0}, {"round": 2, "total_response_time": 2}], label="a")
        zero = summarize_changes(baseline, comparison, ["q1.pb"], "total_response_time")
        self.assertTrue(zero[["p05", "median", "p95"]].isna().all().all())

    def test_failure_leaves_round_gap(self):
        experiment = self.load([{"round": 1, "total_response_time": 2}, {"round": 3, "total_response_time": 4}], [{"round": 2, "error": "failed"}])
        series = values(experiment, "q1.pb", "total_response_time").reindex([1, 2, 3])
        self.assertTrue(series.isna().loc[2])
        self.assertEqual(len(experiment.failures), 1)

    def test_invalid_samples(self):
        for samples, failures in [
            ([{"round": 1}, {"round": 1}], []),
            ([{"round": 1}], [{"round": 1}]),
            ([{"round": 0}], []),
            ([{"round": True}], []),
            ([{"round": 1, "total_response_time": float("nan")}], []),
            ([{"round": 1, "total_response_time": -1}], []),
        ]:
            with self.subTest(samples=samples), self.assertRaises(ValueError):
                self.load(samples, failures)

    def test_incompatible_inputs(self):
        baseline = self.load([], label="a")
        comparison = self.load([], workers=24, label="b")
        with self.assertRaisesRegex(ValueError, "workers_per_cu"):
            check_comparison(baseline, comparison)
        comparison = self.load([], query="q2.pb", label="b")
        with self.assertRaisesRegex(ValueError, "query sets"):
            check_comparison(baseline, comparison)

    def test_zero_baseline_and_absent_observations(self):
        baseline = self.load([{"round": 1, "total_response_time": 0}], label="a")
        comparison = self.load([{"round": 1, "total_response_time": 2}], label="b")
        self.assertTrue(summarize(baseline, comparison, ["q1.pb"], "total_response_time")["percent"].isna().all())
        comparison = self.load([], label="b")
        self.assertTrue(summarize(baseline, comparison, ["q1.pb"], "total_response_time")["percent"].isna().all())

    def test_all_rounds_share_baseline_reference(self):
        from benchmark_figures import plot_panels
        from benchmark_data import METRICS
        import matplotlib.pyplot as plt
        import numpy as np
        for metric in METRICS:
            with self.subTest(metric=metric):
                baseline = self.load([{"round": 1, metric: 100}, {"round": 3, metric: 100}], label="a")
                comparison = self.load([{"round": 1, metric: 105}, {"round": 3, metric: 109}], label="b")
                figure = plot_panels((baseline, comparison), ["q1.pb"], metric, "rounds")
                self.addCleanup(plt.close, figure)
                lines = figure.axes[0].lines
                np.testing.assert_allclose(lines[1].get_ydata(), [0, float("nan"), 0], equal_nan=True)
                np.testing.assert_allclose(lines[3].get_ydata(), [5, float("nan"), 9], equal_nan=True)
                np.testing.assert_allclose(lines[2].get_ydata(), [7, 7])
                self.assertIn("median: 100.000 s", figure.axes[0].get_title())

    def test_combined_chart_uses_change_medians(self):
        from benchmark_figures import plot_metric_comparison
        from benchmark_data import METRICS
        import matplotlib.pyplot as plt
        baseline = self.load([{"round": 1, **dict.fromkeys(METRICS, 100)}], label="a")
        comparison = self.load([{"round": 1, "total_response_time": 101, "plan_duration": 99, "operator_work": 95}], label="b")
        figure = plot_metric_comparison((baseline, comparison), ["q1.pb"], list(METRICS))
        self.addCleanup(plt.close, figure)
        ax = figure.axes[0]
        self.assertEqual(len(ax.get_yticklabels()), 1)
        # The line collection comes first, then one scatter collection per metric.
        for collection, expected in zip(ax.collections[1:], [1, -1, -5]):
            self.assertAlmostEqual(collection.get_offsets()[0, 0], expected)

    def test_metric_relationships_use_each_experiments_medians(self):
        from benchmark_figures import plot_metric_relationships
        from benchmark_data import METRICS
        import matplotlib.pyplot as plt
        baseline = self.load([{"round": 1, "total_response_time": 110, "plan_duration": 100, "operator_work": 95}], label="a")
        comparison = self.load([{"round": 1, "total_response_time": 210, "plan_duration": 200, "operator_work": 220}], label="b")
        figure = plot_metric_relationships((baseline, comparison), ["q1.pb"], list(METRICS))
        self.addCleanup(plt.close, figure)
        for ax, expected in zip(figure.axes, ([10, 0, -5], [5, 0, 10])):
            for collection, value in zip(ax.collections[1:], expected):
                self.assertAlmostEqual(collection.get_offsets()[0, 0], value)
        self.assertEqual(figure.axes[0].get_xlim(), figure.axes[1].get_xlim())

    def test_relationship_duration_labels_share_units(self):
        from benchmark_figures import duration_label_scale, format_duration_label
        scale, unit = duration_label_scale([.219388, .480053, 3.258243])
        self.assertEqual((scale, unit), (1, "s"))
        self.assertEqual(format_duration_label(.480053, scale, unit), "0.480 s")
        self.assertEqual(format_duration_label(3.258243, scale, unit), "3.26 s")
        self.assertEqual(duration_label_scale([.0002, .0008]), (1e-3, "ms"))

    def test_duration_exceedance_counts_same_round_and_complete_metrics(self):
        from benchmark_data import duration_exceedance_counts
        experiment = self.load([
            {"round": 1, "plan_duration": 1.001, "operator_work": 1},
            {"round": 2, "plan_duration": 2, "operator_work": 2},
            {"round": 3, "plan_duration": 4, "operator_work": None},
        ])
        row = duration_exceedance_counts(experiment, ["q1.pb"]).iloc[0]
        self.assertEqual(row["count"], 1)
        self.assertEqual(row["total"], 2)
        self.assertEqual(row["percent"], 50)
        empty = self.load([])
        self.assertTrue(duration_exceedance_counts(empty, ["q1.pb"])["percent"].isna().all())

    def test_duration_delta_format(self):
        from benchmark_figures import format_delta
        for seconds, expected in [(0.03, "+30.0 ms"), (-.005, "-5.00 ms"),
                                  (.000123, "+123 µs"), (1.234, "+1.23 s"),
                                  (.99999, "+1.00 s"), (0, "0 s")]:
            self.assertEqual(format_delta(seconds), expected)

    def test_configuration_defaults_and_relative_paths(self):
        path = self.root / "config.json"
        config = {"baseline": {"directory": "a", "label": "A"}, "comparison": {"directory": "b", "label": "B"}}
        path.write_text(json.dumps(config))
        loaded = read_config(path)
        self.assertEqual(loaded["baseline"]["directory"], self.root / "a")
        self.assertEqual(loaded["metrics"], ["total_response_time"])
        self.assertEqual(loaded["change_queries_per_page"], 13)
        self.assertEqual(loaded["plots"], ["change", "rounds", "metric_comparison", "metric_relationships", "duration_exceedance"])
        for key, value in [("metrics", ["unknown"]), ("queries_per_page", 0), ("change_queries_per_page", 0), ("queries", [])]:
            with self.subTest(key=key):
                path.write_text(json.dumps({**config, key: value}))
                with self.assertRaises(ValueError):
                    read_config(path)


if __name__ == "__main__":
    unittest.main()
