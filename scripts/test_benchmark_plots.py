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


class BatchOutputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_compact_names_and_overrides(self):
        from benchmark_output import compact_variant, comparison_parent, comparison_name
        from types import SimpleNamespace
        directory = self.root / "legacy-variant" / "execution"
        self.assertEqual(compact_variant({"variant": {"materialize_into_join": False}}, directory), "baseline")
        self.assertEqual(compact_variant({"variant": {"materialize_into_group": True, "materialize_into_join": True}}, directory), "mat-join-group")
        self.assertEqual(compact_variant({}, directory), "legacy-variant")
        self.assertNotEqual(compact_variant({"variant": {"other": False}}, directory), compact_variant({"variant": {"other": True}}, directory))
        config = {"output_dir": self.root, "baseline": {"directory": directory}, "comparison": {"directory": directory}}
        experiments = [SimpleNamespace(metadata={"variant": {"materialize_into_join": value}, "workers_per_cu": 48, "scale_factor": 2}) for value in (False, True)]
        self.assertEqual(comparison_parent(config, experiments), self.root / "batches")
        self.assertEqual(comparison_name(config, experiments), "baseline__vs__mat-join")
        config["baseline"]["id"] = "custom"
        config["name"] = "trial"
        self.assertEqual(comparison_name(config, experiments), "trial")

    def test_collision_and_concurrent_reservations_preserve_batches(self):
        from benchmark_output import output_batch
        with output_batch(self.root, "2026-10-30T12-00-00Z") as (staging, first):
            self.assertFalse(first.exists())
            (staging / "figure.png").write_bytes(b"first")
            with output_batch(self.root, "2026-10-30T12-00-00Z") as (other, second):
                (other / "figure.png").write_bytes(b"second")
        self.assertNotEqual(first, second)
        self.assertEqual((first / "figure.png").read_bytes(), b"first")
        self.assertEqual((second / "figure.png").read_bytes(), b"second")
        with output_batch(self.root, "2026-10-30T12-00-00Z") as (staging, third):
            (staging / "figure.png").write_bytes(b"third")
        self.assertEqual(third.name, "2026-10-30T12-00-00Z_02")

    def test_published_batch_inherits_parent_permissions(self):
        from benchmark_output import output_batch
        import stat
        self.root.chmod(0o775)
        with output_batch(self.root, "2026-10-30T12-00-00Z") as (staging, final):
            (staging / "figure.png").write_bytes(b"test")
        self.assertEqual(stat.S_IMODE(final.stat().st_mode), 0o775)

    def test_failed_batch_is_not_published(self):
        from benchmark_output import output_batch
        with self.assertRaisesRegex(RuntimeError, "render failure"):
            with output_batch(self.root, "2026-10-30T12-00-00Z") as (staging, final):
                (staging / "partial.png").write_bytes(b"partial")
                raise RuntimeError("render failure")
        self.assertFalse(final.exists())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_manifest_fingerprints_and_input_changes(self):
        from benchmark_output import input_fingerprints, write_manifest
        from types import SimpleNamespace
        config = {"output_dir": self.root}
        experiments = []
        for role in ("baseline", "comparison"):
            directory = self.root / role
            directory.mkdir()
            (directory / "results.json").write_text("{}")
            config[role] = {"directory": directory, "label": role}
            experiments.append(SimpleNamespace(metadata={"variant": {"role": role}}))
        fingerprints = input_fingerprints(config)
        output = self.root / "batch"
        (output / "change").mkdir(parents=True)
        (output / "change" / "test.png").write_bytes(b"test")
        write_manifest(output, config, experiments, fingerprints, ["q1.pb"], [])
        manifest = json.loads((output / "manifest.json").read_text())
        self.assertEqual(manifest["figures"], ["change/test.png"])
        self.assertFalse(list(output.rglob("metadata.md")))
        self.assertEqual(manifest["inputs"]["baseline"]["sha256"], fingerprints["baseline"]["sha256"])
        (config["baseline"]["directory"] / "results.json").write_text('{"changed":true}')
        with self.assertRaisesRegex(ValueError, "changed during plotting"):
            write_manifest(output, config, experiments, fingerprints, ["q1.pb"], [])

    def test_configuration_caption_preserves_recorded_settings(self):
        from benchmark_output import configuration_caption, add_configuration_caption
        from types import SimpleNamespace
        import matplotlib.pyplot as plt
        metadata = {"variant": {"materialize_into_join": True}, "optimization": {"gco": False},
                    "execution_mode": "sequential", "experiment": {"setting": 42, "notes": "prose"}}
        experiment = SimpleNamespace(metadata=metadata, label="Example")
        config = {role: {"directory": self.root / role} for role in ("baseline", "comparison")}
        lines = configuration_caption(config, [experiment, experiment], "batch-id")
        caption = "\n".join(lines)
        self.assertIn('optimization={"gco":false}', caption)
        self.assertIn('execution_mode="sequential"', caption)
        self.assertIn('experiment={"setting":42}', caption)
        self.assertNotIn("prose", caption)
        figure, axis = plt.subplots()
        self.addCleanup(plt.close, figure)
        figure.text(.5, .02, "existing footer")
        previous_height = figure.get_figheight()
        add_configuration_caption(figure, lines)
        self.assertGreater(figure.get_figheight(), previous_height)
        self.assertIn("batch-id", figure.texts[-1].get_text())
        self.assertGreater(axis.get_position().y0, .11)

    def test_name_overrides_cannot_escape_output(self):
        from benchmark_output import validate_name
        for name in ("../escape", "/absolute", "..", "a/b", "a__vs__b"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_name(name, "name")


class IndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def make_batch(self, directory, marker="original"):
        directory.mkdir(parents=True)
        manifest = {
            "generated_at": "2026-10-30T12:00:00+00:00", "batch_id": "stable-id",
            "config": {role: {"label": role} for role in ("baseline", "comparison")},
            "inputs": {role: {"metadata": {"variant": {"materialize_into_join": role == "comparison"},
                       "optimization": {"gco": False}, "scale_factor": 2}}
                       for role in ("baseline", "comparison")},
            "figures": ["chart.png"], "queries": ["q1.pb"], "notices": [],
        }
        (directory / "manifest.json").write_text(json.dumps(manifest))
        (directory / "chart.png").write_text(marker)
        return manifest

    def test_index_uses_metadata_and_embeds_json_safely(self):
        from benchmark_index import write_index, batch_records
        directory = self.root / "batches" / "batch"
        manifest = self.make_batch(directory)
        manifest["config"]["baseline"]["label"] = "</script><script>alert(1)</script>"
        (directory / "manifest.json").write_text(json.dumps(manifest))
        records = batch_records(self.root)
        self.assertIs(records[0]["fields"]["baseline"]["optimization.gco"], False)
        self.assertNotIn("execution_mode", records[0]["fields"]["baseline"])
        html = write_index(self.root).read_text()
        self.assertNotIn("</script><script>alert(1)", html)
        self.assertIn("antigravity-ide", html)
        self.assertIn(" -n ", html)
        self.assertIn("stable-id", html)
        self.assertNotIn("__BATCH_DATA__", html)

    def test_migration_preserves_images_manifests_and_handles_collisions(self):
        from benchmark_index import migrate_batches, batch_records
        first = self.root / "old-comparison" / "w48_sf2" / "2026-10-30T12-00-00Z"
        manifest = self.make_batch(first)
        second = self.root / "another-comparison" / "w48_sf2" / first.name
        self.make_batch(second, "second")
        moved = migrate_batches(self.root)
        self.assertEqual(len(moved), 2)
        self.assertEqual(len({path.name for path in moved}), 2)
        self.assertEqual({(path / "chart.png").read_text() for path in moved}, {"original", "second"})
        self.assertTrue(all(path.parent == self.root / "batches" for path in moved))
        self.assertTrue(all(json.loads((path / "manifest.json").read_text()) == manifest for path in moved))
        self.assertEqual(len(batch_records(self.root)), 2)
        self.assertEqual(migrate_batches(self.root), [])

    def test_staging_directories_are_not_indexed(self):
        from benchmark_index import batch_records, write_index
        self.make_batch(self.root / "batches" / ".plotting-partial")
        self.assertEqual(batch_records(self.root), [])
        self.assertTrue(write_index(self.root).is_file())


class RenderingFingerprintTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "baseline": {"label": "Unmerged", "directory": "/data/a"},
            "comparison": {"label": "Merged", "directory": "/data/b"},
            "metrics": ["total_response_time", "operator_work"],
            "plots": ["rounds", "change"], "queries_per_page": 6, "change_queries_per_page": 13,
            "output_dir": "/output", "name": "display-name",
        }
        self.inputs = {"baseline": {"sha256": "a" * 64}, "comparison": {"sha256": "b" * 64}}
        self.environment = {"python": "test", "matplotlib": "test", "backend": "Agg"}
        self.code = {"benchmark_figures.py": "c" * 64}

    def fingerprint(self, config=None, inputs=None, queries=None, **kwargs):
        from benchmark_output import rendering_fingerprint
        return rendering_fingerprint(config or self.config, inputs or self.inputs,
                                     ["q1.pb", "q2.pb"] if queries is None else queries,
                                     environment=kwargs.get("environment", self.environment),
                                     code_hashes=kwargs.get("code_hashes", self.code))

    def test_storage_names_and_plot_generation_order_are_excluded(self):
        import copy
        changed = copy.deepcopy(self.config)
        changed["output_dir"] = "/elsewhere"
        changed["name"] = "another-name"
        changed["baseline"]["directory"] = "/copied/a"
        changed["baseline"]["id"] = "alias"
        changed["plots"].reverse()
        self.assertEqual(self.fingerprint(), self.fingerprint(changed))

    def test_rendering_changes_are_distinguished(self):
        import copy
        original = self.fingerprint()
        variants = []
        for key, value in (("metrics", ["operator_work", "total_response_time"]),
                           ("plots", ["change"]), ("queries_per_page", 3), ("change_queries_per_page", 12)):
            config = copy.deepcopy(self.config)
            config[key] = value
            variants.append(self.fingerprint(config))
        config = copy.deepcopy(self.config)
        config["baseline"]["label"] = "Different label"
        variants.extend([self.fingerprint(config), self.fingerprint(queries=["q2.pb", "q1.pb"]),
                         self.fingerprint(queries=["q1.pb"]),
                         self.fingerprint(environment={"python": "different"}),
                         self.fingerprint(code_hashes={"benchmark_figures.py": "changed"}),
                         self.fingerprint(inputs={"baseline": self.inputs["comparison"], "comparison": self.inputs["baseline"]})])
        for result in variants:
            self.assertNotEqual(original["sha256"], result["sha256"])

    def test_schema_and_payload_are_verifiable(self):
        import hashlib
        from benchmark_output import canonical_json
        result = self.fingerprint()
        self.assertEqual(result["payload"]["schema_version"], 1)
        self.assertEqual(result["sha256"], hashlib.sha256(canonical_json(result["payload"]).encode()).hexdigest())

    def test_newest_duplicate_is_retained_and_legacy_is_unverified(self):
        import tempfile
        from pathlib import Path
        from benchmark_index import batch_records
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index in range(3):
                directory = root / str(index)
                directory.mkdir()
                manifest = {"generated_at": f"2026-10-30T12:00:0{index}+00:00", "batch_id": str(index),
                            "config": self.config, "inputs": {role: {**self.inputs[role], "metadata": {
                                "scale_factor": 2, "created_at": str(index), "config_file": str(index),
                                "experiment": {"notes": str(index)}}} for role in self.inputs},
                            "queries": ["q1.pb", "q2.pb"], "figures": []}
                if index:
                    manifest["rendering"] = self.fingerprint()
                (directory / "manifest.json").write_text(json.dumps(manifest))
            records = batch_records(root)
            self.assertEqual([record["id"] for record in records], ["2", "1", "0"])
            self.assertEqual(len({record["group_id"] for record in records}), 1)
            self.assertIsNone(records[0]["redundant_of"])
            self.assertEqual(records[1]["redundant_of"], records[0]["uid"])
            self.assertIsNone(records[2]["rendering"])
            self.assertIsNone(records[2]["redundant_of"])
            self.assertEqual(len(records[0]["related"]), 2)
            # A changed manifest config must not retain a valid rendering fingerprint.
            path = root / "1" / "manifest.json"
            manifest = json.loads(path.read_text())
            manifest["config"]["metrics"] = ["operator_work"]
            path.write_text(json.dumps(manifest))
            self.assertIsNone(batch_records(root)[1]["rendering"])

    def test_grouping_keeps_execution_differences_and_unknown_settings(self):
        from benchmark_index import configuration_metadata
        from benchmark_output import canonical_json
        original = {"query_order": ["q1", "q2"], "host": "a", "execution_mode": "sequential",
                    "experiment": {"setting": 1, "reason": "ignored"}}
        grouped = configuration_metadata(original)
        self.assertEqual(grouped["experiment"], {"setting": 1})
        for key, value in (("host", "b"), ("query_order", ["q2", "q1"]),
                           ("execution_mode", "parallel"), ("new_setting", False)):
            self.assertNotEqual(canonical_json(grouped), canonical_json(configuration_metadata({**original, key: value})))


if __name__ == "__main__":
    unittest.main()
