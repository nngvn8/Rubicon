"""Protect the matching rules used for the exploratory batch generation."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from generate_bootstrap import discover_pairs


class PairDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)

    def write(self, directory, merged, **changes):
        metadata = {"scale_factor": 2, "execution_mode": "concurrent",
                    "workers_per_cu": 48, "created_at": directory,
                    "compilation": {"optimization_level": "-O3"},
                    "variant": {"materialize_into_join": merged},
                    "optimization": {"materialize_into_join": merged, "gco": False},
                    "experiment": {"reason": directory}, **changes}
        path = self.root / directory
        path.mkdir(parents=True)
        (path / "results.json").write_text(json.dumps({"metadata": metadata}))
        return str(path)

    def test_direction_and_all_repeated_directory_pairs(self):
        a = self.write("a", False)
        b = self.write("b", False)
        c = self.write("c", True)
        result = discover_pairs(self.root)
        self.assertEqual([(p["baseline"], p["comparison"]) for p in result["pairs"]], [(a, c), (b, c)])
        self.assertEqual(result["unmatched_directories"], [])

    def test_configuration_mismatches_do_not_pair(self):
        self.write("baseline", False)
        for name, change in (("sf", {"scale_factor": 50}),
                             ("mode", {"execution_mode": "sequential"}),
                             ("workers", {"workers_per_cu": 24}),
                             ("future", {"future_concurrency_option": 8})):
            self.write(name, True, **change)
        result = discover_pairs(self.root)
        self.assertEqual(result["pairs"], [])
        self.assertEqual(len(result["unmatched_directories"]), 5)

    def test_archive_and_O0_excluded_by_path_or_metadata(self):
        self.write("baseline", False)
        self.write("archive/merged", True)
        self.write("-O0/merged", True)
        self.write("metadata_O0", True, compilation={"optimization_level": "-O0"})
        result = discover_pairs(self.root)
        self.assertEqual(result["pairs"], [])
        self.assertEqual(len(result["excluded"]), 3)
        self.assertEqual(len(result["eligible_directories"]), 1)

    def test_derived_bootstrap_subtree_is_never_ingested(self):
        self.write("baseline", False)
        self.write("bootstrap/derived", True)
        result = discover_pairs(self.root)
        self.assertEqual(result["pairs"], [])
        self.assertEqual(len(result["eligible_directories"]), 1)

    def test_conflicting_merge_metadata_rejected(self):
        self.write("bad", True, variant={"materialize_into_join": False})
        with self.assertRaisesRegex(ValueError, "inconsistent merge"):
            discover_pairs(self.root)


if __name__ == "__main__":
    unittest.main()
