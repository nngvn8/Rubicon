"""Cross-scale comparisons must retain statistical meaning and full provenance."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cross_scale import prepare_cross_scale, render_cross_scale, cross_scale_rendering
from index import batch_records, verified_rendering
from plot_benchmarks import read_config


class CrossScaleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config_path = self.root / "config.json"
        self.config = {"baseline": {"label": "Unmerged"}, "comparison": {"label": "Merged"},
                       "plots": ["cross_scale"], "cross_scale": {"pairs": [], "scaling_interval": [50, 100]}}
        for sf in (2, 50, 100):
            pair = {}
            for role in ("baseline", "comparison"):
                name = f"{role}-{sf}"
                directory = self.root / name
                directory.mkdir()
                multiplier = 1 if role == "baseline" else .9
                # At SF 100 use 2.5x the SF 50 duration, not the linear 2x.
                duration = (125 if sf == 100 else sf) * multiplier
                document = {"metadata": {"scale_factor": sf, "workers_per_cu": 48,
                    "measured_rounds": 2, "host": "machine", "execution_mode": "sequential",
                    "warmup_rounds": 0, "query_order": ["q1.pb"], "compilation": {"optimization_level": "-O3"},
                    "optimization": {"materialize_into_join": role == "comparison"},
                    "variant": {"materialize_into_join": role == "comparison"},
                    "created_at": str(sf), "experiment": {"reason": name}},
                    "queries": {"q1.pb": {"samples": [
                        {"round": 1, "total_response_time": duration, "plan_duration": duration / 2},
                        {"round": 2, "total_response_time": duration, "plan_duration": duration / 2}],
                        "failures": []}}}
                (directory / "results.json").write_text(json.dumps(document))
                pair[role] = name
            self.config["cross_scale"]["pairs"].append(pair)

    def load(self):
        self.config_path.write_text(json.dumps(self.config))
        return read_config(self.config_path)

    def mutate(self, role, sf, change):
        path = self.root / f"{role}-{sf}" / "results.json"
        document = json.loads(path.read_text())
        change(document)
        path.write_text(json.dumps(document))

    def test_config_only_and_interval_default(self):
        del self.config["cross_scale"]["scaling_interval"]
        config = self.load()
        self.assertEqual(config["cross_scale"]["metric"], "total_response_time")
        self.assertEqual(config["cross_scale"]["pairs"][0]["baseline"], self.root / "baseline-2")
        pairs, queries, interval, notices, inputs = prepare_cross_scale(config)
        self.assertEqual(list(pairs), [2, 50, 100])
        self.assertEqual(queries, ["q1.pb"])
        self.assertEqual(interval, [50, 100])
        self.assertEqual(len(inputs), 3)

    def test_config_rejects_malformed_options(self):
        for section in ({"metric": "cpu"}, {"scaling_interval": [100, 50]},
                        {"scaling_interval": [False, 100]}, {"scaling_interval": [50, float('inf')]},
                        {"pairs": []}, {"unknown": True}):
            with self.subTest(section=section), self.assertRaises(ValueError):
                changed = copy.deepcopy(self.config)
                self.config["cross_scale"].update(section)
                try:
                    self.load()
                finally:
                    self.config = changed
        self.config["cross_scale"]["pairs"][1]["baseline"] = "baseline-2"
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.load()

    def test_missing_section_and_unknown_interval(self):
        section = self.config.pop("cross_scale")
        with self.assertRaisesRegex(ValueError, "requires"):
            self.load()
        self.config["cross_scale"] = section
        section["scaling_interval"] = [2, 75]
        with self.assertRaisesRegex(ValueError, "present"):
            prepare_cross_scale(self.load())

    def test_rejects_cross_variant_execution_mismatch(self):
        self.mutate("comparison", 50, lambda d: d["metadata"].update(execution_mode="concurrent"))
        with self.assertRaisesRegex(ValueError, "execution_mode"):
            prepare_cross_scale(self.load())

    def test_rejects_across_scale_settings_drift(self):
        for role in ("baseline", "comparison"):
            self.mutate(role, 100, lambda d: d["metadata"].update(host="another-machine"))
        with self.assertRaisesRegex(ValueError, "across scale factors.*host"):
            prepare_cross_scale(self.load())

    def test_missing_metadata_and_optimization_drift_are_detected(self):
        self.mutate("baseline", 100, lambda d: d["metadata"].pop("host"))
        self.mutate("comparison", 100, lambda d: d["metadata"].pop("host"))
        with self.assertRaisesRegex(ValueError, "host"):
            prepare_cross_scale(self.load())

    def test_rejects_optimization_drift_within_a_variant(self):
        self.mutate("baseline", 100, lambda d: d["metadata"]["optimization"].update(gco=True))
        with self.assertRaisesRegex(ValueError, "across scale factors.*optimization"):
            prepare_cross_scale(self.load())

    def test_rejects_duplicate_scale_factors_and_different_query_sets(self):
        for role in ("baseline", "comparison"):
            self.mutate(role, 100, lambda d: d["metadata"].update(scale_factor=50))
        with self.assertRaisesRegex(ValueError, "Duplicate.*scale factor"):
            prepare_cross_scale(self.load())
        for role in ("baseline", "comparison"):
            self.mutate(role, 100, lambda d: d["metadata"].update(scale_factor=100))
            self.mutate(role, 100, lambda d: d["queries"].update({"q2.pb": d["queries"]["q1.pb"]}))
        with self.assertRaisesRegex(ValueError, "query sets differ"):
            prepare_cross_scale(self.load())

    def test_failures_and_missing_metrics_generate_notices(self):
        self.config["cross_scale"]["metric"] = "operator_work"
        self.mutate("baseline", 50, lambda d: d["queries"]["q1.pb"].update(
            samples=[], failures=[{"round": 1, "error": "failed"}]))
        prepared = prepare_cross_scale(self.load())
        self.assertTrue(any("failed query-rounds" in notice for notice in prepared[3]))
        self.assertTrue(any("0/2 observations" in notice for notice in prepared[3]))
        from plots import plot_cross_scale
        import matplotlib.pyplot as plt
        figure = plot_cross_scale(prepared[0], prepared[1], "operator_work", prepared[2])
        self.addCleanup(plt.close, figure)
        self.assertTrue(any(text.get_text() == "N/A" for text in figure.axes[0].texts))

    def test_chart_calculations_and_selectable_metric(self):
        from plots import plot_cross_scale
        import matplotlib.pyplot as plt
        import numpy as np
        # An asymmetric distribution distinguishes the ratio of medians from the former all-pairs median.
        self.mutate("baseline", 2, lambda d: d["queries"]["q1.pb"]["samples"][1].update(total_response_time=20))
        pairs, queries, interval, _, _ = prepare_cross_scale(self.load())
        figure = plot_cross_scale(pairs, queries, "total_response_time", interval)
        self.addCleanup(plt.close, figure)
        expected = 100 * (1.8 / 11 - 1)
        self.assertAlmostEqual(figure.axes[0].images[0].get_array()[0, 0], expected)
        for collection in figure.axes[1].collections:
            self.assertAlmostEqual(collection.get_offsets()[0, 0], 2.5)
        np.testing.assert_allclose(figure.axes[1].lines[0].get_xdata(), [2, 2])
        figure2 = plot_cross_scale(pairs, queries, "plan_duration", [2, 50])
        self.addCleanup(plt.close, figure2)
        self.assertIn("Plan duration", figure2._suptitle.get_text())
        np.testing.assert_allclose(figure2.axes[1].lines[0].get_xdata(), [25, 25])

    def test_fixed_colors_clip_without_changing_values_or_labels(self):
        from plots import plot_cross_scale
        import matplotlib.pyplot as plt
        self.mutate("comparison", 100, lambda d: [sample.update(total_response_time=625)
                    for sample in d["queries"]["q1.pb"]["samples"]])
        pairs, queries, interval, _, _ = prepare_cross_scale(self.load())
        figure = plot_cross_scale(pairs, queries, "total_response_time", interval)
        self.addCleanup(plt.close, figure)
        image = figure.axes[0].images[0]
        self.assertEqual(image.get_clim(), (-20, 20))
        self.assertAlmostEqual(image.get_array()[0, 2], 400)
        self.assertTrue(any(text.get_text() == "+400.0%" for text in figure.axes[0].texts))
        self.assertEqual(image.cmap(image.norm(400)), image.cmap(1.0))
        other = plot_cross_scale(pairs, queries, "total_response_time", interval, [-10, 30])
        self.addCleanup(plt.close, other)
        self.assertEqual(other.axes[0].images[0].get_clim(), (-10, 30))

    def test_color_limits_validation(self):
        for limits in ([0, 20], [-20, 0], [20, -20], [-20, float("inf")], [False, 20], [-20]):
            with self.subTest(limits=limits), self.assertRaisesRegex(ValueError, "color_limits"):
                self.config["cross_scale"]["color_limits"] = limits
                self.load()

    def test_zero_denominators_are_unavailable(self):
        from plots import plot_cross_scale
        import matplotlib.pyplot as plt
        import numpy as np
        self.mutate("baseline", 50, lambda d: [x.update(total_response_time=0) for x in d["queries"]["q1.pb"]["samples"]])
        pairs, queries, interval, notices, _ = prepare_cross_scale(self.load())
        self.assertTrue(any("zero observations" in notice for notice in notices))
        figure = plot_cross_scale(pairs, queries, "total_response_time", interval)
        self.addCleanup(plt.close, figure)
        self.assertTrue(np.ma.is_masked(figure.axes[0].images[0].get_array()[0, 1]))
        self.assertTrue(any("Unmerged: N/A" == t.get_text() for t in figure.axes[1].texts))

    def test_manifest_and_index_retain_all_inputs_and_detect_tampering(self):
        config = self.load()
        config["output_dir"] = self.root / "output"
        final = render_cross_scale(config, prepare_cross_scale(config))
        manifest = json.loads((final / "manifest.json").read_text())
        self.assertEqual(len(manifest["scale_pairs"]), 3)
        self.assertEqual(manifest["inputs"]["baseline"]["metadata"]["scale_factor"], [2, 50, 100])
        self.assertEqual(len(manifest["scale_pairs"][0]["baseline"]["sha256"]), 64)
        self.assertIsNotNone(verified_rendering(manifest))
        records = batch_records(config["output_dir"])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["kind"], "cross_scale")
        self.assertEqual(len(records[0]["source_directories"]["baseline"]), 3)
        render_cross_scale(config, prepare_cross_scale(config))
        duplicates = batch_records(config["output_dir"])
        self.assertEqual(len(duplicates), 2)
        self.assertEqual(duplicates[1]["redundant_of"], duplicates[0]["uid"])
        self.assertEqual(duplicates[0]["group_id"], duplicates[1]["group_id"])
        manifest["scale_pairs"][0]["baseline"]["sha256"] = "changed"
        self.assertIsNone(verified_rendering(manifest))

    def test_input_changes_prevent_publication(self):
        config = self.load()
        config["output_dir"] = self.root / "output"
        prepared = prepare_cross_scale(config)
        self.mutate("comparison", 100, lambda d: d["metadata"].update(created_at="changed"))
        with self.assertRaisesRegex(ValueError, "changed during plotting"):
            render_cross_scale(config, prepared)
        self.assertEqual(list((config["output_dir"] / "batches").iterdir()), [])

    def test_fingerprint_covers_metric_interval_and_all_inputs(self):
        config = self.load()
        _, queries, interval, _, inputs = prepare_cross_scale(config)
        def fingerprint(c=config, inp=inputs, selected=interval):
            return cross_scale_rendering(c, inp, queries, selected, environment={"test": 1}, code_hashes={"test": "a"})
        original = fingerprint()
        changed = copy.deepcopy(config)
        changed["cross_scale"]["metric"] = "plan_duration"
        self.assertNotEqual(original, fingerprint(changed))
        self.assertNotEqual(original, fingerprint(selected=[2, 50]))
        changed = copy.deepcopy(config)
        changed["cross_scale"]["color_limits"] = [-10, 10]
        self.assertNotEqual(original, fingerprint(changed))
        changed_inputs = copy.deepcopy(inputs)
        changed_inputs[0]["comparison"]["sha256"] = "changed"
        self.assertNotEqual(original, fingerprint(inp=changed_inputs))
        self.assertEqual(original, fingerprint(inp=list(reversed(inputs))))


if __name__ == "__main__":
    unittest.main()
