import struct
import tempfile
import unittest
from pathlib import Path

from utils import memtrack
from utils.memtrack import DELTA, DROPPED, EVENT, HEADER, MAGIC, TEMP, VERSION


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
            write_log(path, [(10, 1, 1, 5, DELTA), (200, 1, 1, -5, DELTA)], torn=b'\x01\x02\x03')
            self.assertEqual(len(memtrack.load_events(path)), 2)
            self.assertEqual(memtrack.load_events(path, since_ns=100), [(200, 1, 1, -5, DELTA)])

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
            (0 * s, 7, 3, 0, TEMP),                # operator start
            (0 * s, 7, 3, 100, DELTA),             # output of 100 bytes requested
            (1 * s, 7, 3, 300, TEMP),              # hash table 300 bytes
            (2 * s, 7, 3, 0, TEMP),                # operator end, table freed
            (2 * s, 7, 3, -40, DELTA),             # shrink of the output to 60
            (5 * s, 7, 3, -60, DELTA),             # freed with the plan
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

    def test_unfreed_output_is_reported_and_drops_counted(self):
        events = [(0, 1, 1, 0, TEMP), (0, 1, 1, 50, DELTA), (9, 1, 1, 0, TEMP), (10, 0, 0, 4, DROPPED)]
        result = memtrack.derive(events)
        self.assertEqual(result['operators'][0]['live_bytes_at_plan_end'], 50)
        self.assertEqual(result['events_dropped'], 4)

    def test_plan_timeline_sums_operators_and_thins(self):
        events = []
        for item in (1, 2):
            events += [(item * 10, 5, item, 0, TEMP), (item * 10, 5, item, 100, DELTA)]
        timeline = memtrack.derive(events)['plans'][0]['timeline']
        self.assertEqual(timeline[-1][1], 200)
        many = [[t, t] for t in range(10_000)]
        steps = [[(t, t, t) for t in range(10_000)]]
        self.assertLessEqual(len(memtrack.plan_timeline(steps, max_points=100)), 101)
        self.assertEqual(len(many), 10_000)


if __name__ == '__main__':
    unittest.main()
