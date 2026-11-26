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

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plot_memory import (MIB, all_rounds_trace, batch_description, deviation_matrix, export_memory, load_memory,
                         mean_trace, plan_cross_metrics, render_memory, round_trace)
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
            'plans': [
                {'query': 'q1.pb', 'plan_id': 7, 'round': 1, 'warmup': False,
                 'start_ns': 100_000_000, 'end_ns': 1_900_000_000},
            ],
            'operator_tracking': {'plans': [], 'operators': [
                {'query': 'q1.pb', 'plan_id': 7, 'item': 3, 'start_ns': 200_000_000, 'end_ns': 1_500_000_000}]},
            'interpretation': 'Whole-CU RSS; overlapping intervals are not additive.',
        }
        self.summary_path.write_text(json.dumps(self.summary))
        with self.samples_path.open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['timestamp_ns', 'rss_bytes'])
            for second, mib in enumerate((8, 12, 8)):
                ns = second * 10**9
                writer.writerow([ns, mib * MIB])
        (self.session / 'results.json').write_text(json.dumps({
            'memory': {'summary': self.summary_path.name, 'samples': self.samples_path.name}}))

    def test_export_is_offline_readonly_and_records_inputs(self):
        # Rendering must not update the collector's summary or its results.json links.
        before = {path.name: path.read_bytes() for path in self.session.iterdir()}
        output = export_memory(self.session / 'results.json', self.root / 'plots')
        self.assertTrue((output / 'memory/round_1.png').exists())
        self.assertTrue((output / 'memory/all_rounds.png').exists())
        # The fixture has a single round, so the versions that need more are skipped.
        self.assertFalse((output / 'memory/round_2.png').exists())
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.session.iterdir()})
        manifest = json.loads((output / 'manifest.json').read_text())
        self.assertEqual(manifest['figures'], ['memory/round_1.png', 'memory/all_rounds.png'])
        self.assertEqual(manifest['metadata']['source'], 'status')
        self.assertEqual(manifest['inputs'][str(self.samples_path)],
                         hashlib.sha256(self.samples_path.read_bytes()).hexdigest())
        # Regeneration publishes a separate batch instead of overwriting the first plot.
        second = export_memory(self.summary_path, self.root / 'plots')
        self.assertNotEqual(output, second)
        self.assertTrue((output / 'memory/round_1.png').exists())

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
        fig = render_memory(all_rounds_trace(samples, summary), 'title', max_gap_s=2)
        self.addCleanup(plt.close, fig)
        top, lanes = fig.axes
        # RSS is shown above the 8 MiB baseline.
        self.assertEqual(list(top.lines[0].get_ydata()), [0, 4, 0])
        self.assertEqual(list(lanes.lines[0].get_xdata()), [0.2, 1.5])
        self.assertEqual(top.get_title(), 'title')

    def test_round_view_starts_at_the_first_plan_of_the_round(self):
        samples, summary, _ = load_memory(self.session)
        trace = round_trace(samples, summary, 1)
        self.assertEqual(trace['plans'], [('q1.pb', 0.0, 1.8, False)])
        self.assertEqual([round(t, 6) for t in trace['t']], [-0.1, 0.9, 1.9])
        with self.assertRaisesRegex(ValueError, 'no measured plans in round 2'):
            round_trace(samples, summary, 2)

    def test_mean_trace_aligns_rounds_of_different_length_on_plan_boundaries(self):
        samples, summary, _ = load_memory(self.session)
        summary['metadata']['benchmark'] = {'execution_mode': 'sequential'}
        # Round 2 takes 1 s, round 3 takes 2 s; RSS rises when the plan starts and falls when it ends.
        summary['plans'] = [
            {'query': 'q1.pb', 'plan_id': 1, 'round': 2, 'warmup': False,
             'start_ns': 10 * 10**9, 'end_ns': 11 * 10**9},
            {'query': 'q1.pb', 'plan_id': 2, 'round': 3, 'warmup': False,
             'start_ns': 20 * 10**9, 'end_ns': 22 * 10**9}]
        samples = [{'timestamp_ns': ns, 'rss_bytes': (8 + (10 if start <= ns <= end else 0)) * MIB}
                   for start, end in ((10 * 10**9, 11 * 10**9), (20 * 10**9, 22 * 10**9))
                   for ns in range(start - 10**9, end + 10**9, 10**8)]
        samples = sorted({s['timestamp_ns']: s for s in samples}.values(), key=lambda s: s['timestamp_ns'])
        trace = mean_trace(samples, summary)
        (query, start, end, _), = trace['plans']
        self.assertEqual(query, 'q1.pb')
        self.assertAlmostEqual(end - start, 1.5)
        inside = (trace['t'] > start + 0.1) & (trace['t'] < end - 0.1)
        self.assertTrue(np.allclose(trace['rss'][inside], 10))
        outside = (trace['t'] < start - 0.1) | (trace['t'] > end + 0.1)
        self.assertTrue(np.allclose(trace['rss'][outside], 0))

    def test_net_timeline_is_traced_next_to_gross_when_recorded(self):
        samples, summary, _ = load_memory(self.session)
        self.assertIsNone(round_trace(samples, summary, 1)['tracked_net'])
        summary['operator_tracking']['plans'] = [
            {'plan_id': 7, 'timeline': [[0, 100 * MIB], [10**9, 0]], 'timeline_net': [[0, 40 * MIB], [10**9, 0]]}]
        trace = round_trace(samples, summary, 1)
        self.assertEqual(trace['tracked'].max(), 100)
        self.assertEqual(trace['tracked_net'].max(), 40)
        figure = render_memory(trace, 'net')
        self.addCleanup(plt.close, figure)
        self.assertTrue(any('net' in text.get_text() for text in figure.axes[0].get_legend().get_texts()))

    def test_stacked_render_gives_rss_gross_and_net_their_own_panels(self):
        samples, summary, _ = load_memory(self.session)
        summary['operator_tracking']['plans'] = [
            {'plan_id': 7, 'timeline': [[0, 100 * MIB], [10**9, 0]], 'timeline_net': [[0, 40 * MIB], [10**9, 0]]}]
        trace = round_trace(samples, summary, 1)
        figure = render_memory(trace, 'stacked', stacked=True)
        self.addCleanup(plt.close, figure)
        self.assertEqual(len(figure.axes), 4)  # RSS, gross, net, plans
        self.assertEqual([len(ax.lines) + len(ax.patches) > 0 for ax in figure.axes[:3]], [True] * 3)

    def test_cross_scale_metrics_use_net_curve_inside_the_plan_window_and_median_over_rounds(self):
        def plan(plan_id, round_number, level_mib):
            window = {'query': 'q1.pb', 'plan_id': plan_id, 'round': round_number, 'warmup': False,
                      'start_ns': 0, 'end_ns': 4 * 10**9}
            # 10 MiB for 1 s, then level_mib for 1 s, then 5 MiB until the window ends and beyond.
            tracked = {'plan_id': plan_id, 'timeline': [[0, 999 * MIB]],
                       'timeline_net': [[0, 10 * MIB], [10**9, level_mib * MIB], [2 * 10**9, 5 * MIB]]}
            return window, tracked
        rows = [plan(i, i, level) for i, level in enumerate((20, 30, 1000), start=1)]
        summary = {'plans': [w for w, _ in rows], 'operator_tracking': {'plans': [t for _, t in rows]}}
        metrics = plan_cross_metrics(summary)['q1.pb']
        # Integrals: 10 + 20 + 2*5 = 40, 50 and 1020 MiB*s; the median belongs to the second round.
        self.assertAlmostEqual(metrics['integral'], 50)
        self.assertAlmostEqual(metrics['average'], 50 / 4)
        self.assertAlmostEqual(metrics['peak'], 30)
        runs = {False: {2: {'q1.pb': {'peak': 100.0}}}, True: {2: {'q1.pb': {'peak': 75.0}, 'q2.pb': {'peak': 1.0}}}}
        matrix = deviation_matrix(runs, ['q1.pb', 'q2.pb'], [2], 'peak')
        self.assertAlmostEqual(matrix[0, 0], -25)
        self.assertTrue(np.isnan(matrix[1, 0]))  # no non-merged baseline

    def test_gap_breaks_curve_and_partial_session_can_render(self):
        samples, summary, _ = load_memory(self.session)
        summary['plans'] = []
        fig = render_memory(all_rounds_trace(samples, summary), 'title', max_gap_s=0.5)
        self.addCleanup(plt.close, fig)
        self.assertTrue(any(math.isnan(value) for value in fig.axes[0].lines[0].get_ydata()))
        self.assertEqual(fig.axes[1].texts[0].get_text(), 'No completed plan intervals')

    def test_missing_empty_and_out_of_order_samples_fail_explicitly(self):
        self.samples_path.write_text('rss_bytes\n10\n')
        with self.assertRaisesRegex(ValueError, 'required sample columns'):
            load_memory(self.session)
        header = 'timestamp_ns,rss_bytes\n'
        self.samples_path.write_text(header)
        with self.assertRaisesRegex(ValueError, 'no RSS samples'):
            load_memory(self.session)
        self.samples_path.write_text(header + '2,10\n1,10\n')
        with self.assertRaisesRegex(ValueError, 'increase strictly'):
            load_memory(self.session)

    def test_changed_inputs_do_not_publish_a_plot(self):
        # Match timing plots: an export is valid only for a stable input snapshot.
        with patch('plot_memory.fingerprints', side_effect=[{'snapshot': 'a'}, {'snapshot': 'b'}]):
            with self.assertRaisesRegex(ValueError, 'changed during plotting'):
                export_memory(self.session, self.root / 'plots')
        self.assertEqual(list((self.root / 'plots').rglob('round_1.png')), [])


if __name__ == '__main__':
    unittest.main()
