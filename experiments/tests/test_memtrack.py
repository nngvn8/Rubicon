import struct
import tempfile
import unittest
from pathlib import Path

from utils import memtrack
from utils.memtrack import ALLOC, DROPPED, EVENT, FREE, HEADER, MAGIC, SHRINK, TEMP, VERSION


def write_log(path, events, magic=MAGIC, event_size=EVENT.size, torn=b''):
    header = HEADER.pack(magic, VERSION, event_size, 1024, 0)
    path.write_bytes(header + b''.join(EVENT.pack(*e) for e in events) + torn)


class MemtrackTest(unittest.TestCase):
    def test_layout_matches_cpp(self):
        self.assertEqual(EVENT.size, 32)
        self.assertEqual(HEADER.size, 32)

    def test_load_filters_old_events_and_torn_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'log.bin'
            write_log(path, [(10, 1, 1, 5, ALLOC, 1), (200, 1, 1, -5, FREE, 0)], torn=b'\x01\x02\x03')
            self.assertEqual(len(memtrack.load_events(path)), 2)
            self.assertEqual(memtrack.load_events(path, since_ns=100), [(200, 1, 1, -5, FREE, 0)])

    def test_load_rejects_foreign_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'log.bin'
            write_log(path, [], magic=b'NOTMEMLG')
            with self.assertRaises(ValueError):
                memtrack.load_events(path)
            write_log(path, [], event_size=48)
            with self.assertRaises(ValueError):
                memtrack.load_events(path)

    def test_operator_peak_integral_and_free(self):
        s = 1_000_000_000
        events = [
            (0 * s, 7, 3, 0, TEMP, 0),             # operator start
            (0 * s, 7, 3, 100, ALLOC, 1),          # output of 100 bytes requested
            (1 * s, 7, 3, 300, TEMP, 0),           # hash table 300 bytes
            (2 * s, 7, 3, 0, TEMP, 0),             # operator end, table freed
            (2 * s, 7, 3, -40, SHRINK, 1),         # shrink of the output to 60
            (5 * s, 7, 3, -60, FREE, 0),           # freed with the plan
        ]
        result = memtrack.derive(events, {7: {'query': 'q.pb', 'round': 1, 'warmup': False}})
        op, = result['operators']
        self.assertEqual(op['peak_bytes'], 400)
        self.assertEqual(op['retained_bytes'], 60)
        self.assertEqual(op['live_bytes_at_plan_end'], 0)
        self.assertEqual((op['start_ns'], op['end_ns']), (0, 2 * s))
        # Step function: 100 for 1 s, 400 for 1 s, 60 for 3 s.
        self.assertAlmostEqual(op['integral_mib_seconds'] * 1024 ** 2, 100 + 400 + 180)
        self.assertEqual(op['query'], 'q.pb')
        self.assertEqual(result['events_dropped'], 0)

    def test_route_b_moves_shrink_to_its_alloc(self):
        s = 1_000_000_000
        events = [
            (0 * s, 7, 3, 0, TEMP, 0),
            (0 * s, 7, 3, 100, ALLOC, 1),          # two worst-case buffers, shrunk in reverse order
            (0 * s, 7, 3, 200, ALLOC, 2),
            (1 * s, 7, 3, 300, TEMP, 0),
            (2 * s, 7, 3, 0, TEMP, 0),
            (2 * s, 7, 3, -190, SHRINK, 2),        # buffer 2 ends at 10 bytes
            (2 * s, 7, 3, -40, SHRINK, 1),         # buffer 1 ends at 60 bytes
            (5 * s, 7, 3, -70, FREE, 0),
        ]
        op, = memtrack.derive(events)['operators']
        self.assertEqual(op['peak_bytes'], 600)        # 300 outputs + 300 table
        self.assertEqual(op['peak_bytes_net'], 370)    # 70 outputs + 300 table
        self.assertEqual(op['retained_bytes'], 70)
        # Net: 70 for 1 s, 370 for 1 s, 70 for 3 s.
        self.assertAlmostEqual(op['integral_mib_seconds_net'] * 1024 ** 2, 70 + 370 + 210)

    def test_unfreed_output_is_reported_and_drops_counted(self):
        events = [(0, 1, 1, 0, TEMP, 0), (0, 1, 1, 50, ALLOC, 1), (9, 1, 1, 0, TEMP, 0), (10, 0, 0, 4, DROPPED, 0)]
        result = memtrack.derive(events)
        self.assertEqual(result['operators'][0]['live_bytes_at_plan_end'], 50)
        self.assertEqual(result['events_dropped'], 4)

    def test_inconsistent_logs_raise(self):
        with self.assertRaises(ValueError):  # Alloc without buffer id
            memtrack.derive([(0, 1, 1, 0, TEMP, 0), (1, 1, 1, 50, ALLOC, 0), (2, 1, 1, 0, TEMP, 0)])
        with self.assertRaises(ValueError):  # unknown kind
            memtrack.derive([(0, 1, 1, 0, 9, 0)])
        with self.assertRaises(ValueError):  # operator without start and end snapshot
            memtrack.derive([(0, 1, 1, -5, FREE, 0)])

    def test_missing_snapshots_are_skipped_only_when_events_were_dropped(self):
        events = [(0, 1, 1, -5, FREE, 0), (0, 2, 2, 0, TEMP, 0), (1, 2, 2, 0, TEMP, 0), (2, 0, 0, 3, DROPPED, 0)]
        result = memtrack.derive(events)
        self.assertEqual([op['plan_id'] for op in result['operators']], [2])
        self.assertEqual(result['events_dropped'], 3)

    def test_shrink_without_alloc_is_counted(self):
        events = [(0, 1, 1, 0, TEMP, 0), (1, 1, 1, -10, SHRINK, 77), (2, 1, 1, 0, TEMP, 0)]
        result = memtrack.derive(events)
        self.assertEqual(result['unpaired_shrinks'], 1)
        self.assertEqual(memtrack.derive([(0, 1, 1, 0, TEMP, 0), (0, 1, 1, 50, ALLOC, 1), (1, 1, 1, -10, SHRINK, 1),
                                          (2, 1, 1, 0, TEMP, 0)])['unpaired_shrinks'], 0)

    def test_plan_timeline_sums_operators_and_thins(self):
        events = []
        for item in (1, 2):
            events += [(item * 10, 5, item, 0, TEMP, 0), (item * 10, 5, item, 100, ALLOC, item)]
        timeline = memtrack.derive(events)['plans'][0]['timeline']
        self.assertEqual(timeline[-1][1], 200)
        many = [[t, t] for t in range(10_000)]
        steps = [[(t, t, t) for t in range(10_000)]]
        self.assertLessEqual(len(memtrack.plan_timeline(steps, max_points=100)), 101)
        self.assertEqual(len(many), 10_000)


if __name__ == '__main__':
    unittest.main()
