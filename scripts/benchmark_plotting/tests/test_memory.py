"""Offline RAM plots must preserve raw measurements and their concurrency labels."""
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plot_memory import MIB, batch_description, export_memory, load_memory, render_memory
import matplotlib.pyplot as plt


class MemoryPlotTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.session = self.root / 'session'
        self.session.mkdir()
        self.summary_path = self.session / 'memory_summary.json'
        self.samples_path = self.session / 'memory_samples.csv'
        self.summary = {
            'metadata': {'source': 'status', 'baseline_bytes': 8 * MIB, 'max_gap_ms': 2000},
            'windows': [
                {'kind': 'round', 'round': 1, 'warmup': False, 'start_ns': 100_000_000, 'end_ns': 1_900_000_000},
                {'kind': 'plan', 'query': 'q1.pb', 'plan_id': 7, 'warmup': False,
                 'start_ns': 100_000_000, 'end_ns': 1_900_000_000},
            ],
            'operators': [{'query': 'q1.pb', 'operator_id': 3, 'start_ns': 200_000_000, 'end_ns': 1_500_000_000}],
            'interpretation': 'Whole-CU RSS; overlapping intervals are not additive.',
        }
        self.summary_path.write_text(json.dumps(self.summary))
        with self.samples_path.open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['read_start_ns', 'read_end_ns', 'timestamp_ns', 'rss_bytes'])
            for second, mib in enumerate((8, 12, 8)):
                ns = second * 10**9
                writer.writerow([ns, ns, ns, mib * MIB])
        (self.session / 'results.json').write_text(json.dumps({
            'memory': {'summary': self.summary_path.name, 'samples': self.samples_path.name}}))

    def test_export_is_offline_readonly_and_records_inputs(self):
        # Rendering must not update the collector's summary or its results.json links.
        before = {path.name: path.read_bytes() for path in self.session.iterdir()}
        output = export_memory(self.session / 'results.json', self.root / 'plots')
        self.assertTrue((output / 'memory.png').exists())
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.session.iterdir()})
        manifest = json.loads((output / 'manifest.json').read_text())
        self.assertEqual(manifest['metadata']['source'], 'status')
        self.assertEqual(manifest['inputs'][str(self.samples_path)],
                         hashlib.sha256(self.samples_path.read_bytes()).hexdigest())
        # Regeneration publishes a separate batch instead of overwriting the first plot.
        second = export_memory(self.summary_path, self.root / 'plots')
        self.assertNotEqual(output, second)
        self.assertTrue((output / 'memory.png').exists())

    def test_batch_name_identifies_mode_variant_scale_and_run(self):
        benchmark = {'execution_mode': 'sequential', 'scale_factor': 50,
                     'variant': {'materialize_into_join': True}}
        run = '2026-11-16T23-33-25Z_sf-50_runs-20_workers-48'
        self.assertEqual(batch_description({'metadata': {'benchmark': benchmark}}, run),
                         'sequential_mat-join_sf50_2026-11-16T23-33-25Z')
        self.assertEqual(batch_description({'metadata': {}}, run), '2026-11-16T23-33-25Z')
        output = export_memory(self.session, self.root / 'plots')
        self.assertEqual(output.name.split('_', 1)[1], 'session')

    def test_memory_values_and_operator_intervals_share_time_origin(self):
        samples, summary, _ = load_memory(self.session)
        fig = render_memory(samples, summary)
        self.addCleanup(plt.close, fig)
        ram, lanes = fig.axes
        self.assertEqual(list(ram.lines[0].get_ydata()), [8, 12, 8])
        self.assertEqual(list(lanes.lines[0].get_xdata()), [0.2, 1.5])
        self.assertIn('Whole-CU', ram.get_title())

    def test_gap_breaks_curve_and_partial_session_can_render(self):
        samples, summary, _ = load_memory(self.session)
        summary['metadata']['max_gap_ms'] = 500
        summary['windows'] = []
        summary['operators'] = []
        fig = render_memory(samples, summary)
        self.addCleanup(plt.close, fig)
        self.assertTrue(any(math.isnan(value) for value in fig.axes[0].lines[0].get_ydata()))
        self.assertEqual(fig.axes[1].texts[0].get_text(), 'No completed plan intervals')

    def test_missing_empty_and_out_of_order_samples_fail_explicitly(self):
        self.samples_path.write_text('timestamp_ns,rss_bytes\n0,10\n')
        with self.assertRaisesRegex(ValueError, 'required sample columns'):
            load_memory(self.session)
        header = 'read_start_ns,read_end_ns,timestamp_ns,rss_bytes\n'
        self.samples_path.write_text(header)
        with self.assertRaisesRegex(ValueError, 'no RSS samples'):
            load_memory(self.session)
        self.samples_path.write_text(header + '2,2,2,10\n1,1,1,10\n')
        with self.assertRaisesRegex(ValueError, 'increase strictly'):
            load_memory(self.session)

    def test_changed_inputs_do_not_publish_a_plot(self):
        # Match timing plots: an export is valid only for a stable input snapshot.
        with patch('plot_memory.fingerprints', side_effect=[{'snapshot': 'a'}, {'snapshot': 'b'}]):
            with self.assertRaisesRegex(ValueError, 'changed during plotting'):
                export_memory(self.session, self.root / 'plots')
        self.assertEqual(list((self.root / 'plots').rglob('memory.png')), [])


if __name__ == '__main__':
    unittest.main()
