"""Numerical, /proc, lifecycle, and benchmark integration checks for RSS sampling."""
import contextlib
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.memory import MIB, MemorySession, _collect, aligned_operators, integrate, load_samples, process_identity, read_rss
from proto import NetworkRequests_pb2, QueryPlan_pb2, WorkRequest_pb2, WorkResponse_pb2
from proto.UnitDefinition_pb2 import TcpPackageType, UnitType
import run_query


def sample(seconds, mib):
    ns = int(seconds * 1e9)
    return {'timestamp_ns': ns, 'read_start_ns': ns, 'read_end_ns': ns,
            'rss_bytes': int(mib * MIB)}


class IntegralTests(unittest.TestCase):
    def test_constant_interpolated_boundaries_and_signed_baseline(self):
        result = integrate([sample(0, 10), sample(1, 10), sample(2, 10)],
                           250_000_000, 1_750_000_000, 12 * MIB, 2_000_000_000)
        self.assertTrue(result['coverage_complete'])
        self.assertEqual(result['integral_mib_seconds'], 15)
        self.assertEqual(result['baseline_integral_mib_seconds'], -3)
        self.assertEqual(result['average_rss_mib'], 10)

    def test_ramp(self):
        result = integrate([sample(0, 0), sample(1, 10), sample(2, 20)],
                           500_000_000, 1_500_000_000, 0, 2_000_000_000)
        self.assertEqual(result['integral_mib_seconds'], 10)
        self.assertEqual(result['start_rss_mib'], 5)

    def test_no_extrapolation_or_gap_bridging(self):
        samples = [sample(1, 10), sample(3, 10)]
        for start, end, gap, issue in [(0, 2, 5, 'window_not_bracketed_by_samples'),
                                      (1, 3, 1, 'sample_gap_exceeds_limit')]:
            result = integrate(samples, start * 10**9, end * 10**9, 0, gap * 10**9)
            self.assertFalse(result['coverage_complete'])
            self.assertIsNone(result['integral_mib_seconds'])
            self.assertIn(issue, result['issues'])

    def test_slow_reads_are_flagged(self):
        samples = [sample(0, 10), sample(1, 10)]
        samples[0]['read_end_ns'] = 2_000_000_000
        self.assertIn('sample_read_exceeds_gap_limit',
                      integrate(samples, 0, 10**9, 0, 10**9)['issues'])


class ProcAndClockTests(unittest.TestCase):
    def test_collector_auto_fallback_permissions_and_pid_reuse(self):
        for scenario in ('auto', 'permission', 'reuse'):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as tmp:
                messages = []
                pipe = SimpleNamespace(send=messages.append, close=lambda: None)
                stop = threading.Event()
                stop.set()  # Read one final sample, then stop.
                def rss(pid, source):
                    if scenario == 'permission':
                        raise PermissionError('denied')
                    if source == 'smaps_rollup':
                        time.sleep(0.002)
                    return MIB
                identities = ['old', 'old', 'new'] if scenario == 'reuse' else None
                with patch('utils.memory.read_rss', side_effect=rss), \
                     patch('utils.memory.process_identity', side_effect=identities, return_value='old'):
                    _collect(123, 'auto' if scenario == 'auto' else 'status',
                             0.001, str(Path(tmp) / 'samples.csv'), stop, pipe)
                if scenario == 'auto':
                    self.assertEqual(messages[0]['source'], 'status')
                    self.assertEqual(messages[-1]['type'], 'stopped')
                else:
                    self.assertEqual(messages[-1]['type'], 'error')
                    self.assertIn('denied' if scenario == 'permission' else 'changed', messages[-1]['error'])

    def test_units_missing_fields_and_process_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proc = root / '123'
            proc.mkdir()
            (proc / 'status').write_text('Name: CU\nVmRSS: 42 kB\n')
            self.assertEqual(read_rss(123, 'status', root), 42 * 1024)
            (proc / 'smaps_rollup').write_text('Rss: 43 kB\n')
            self.assertEqual(read_rss(123, 'smaps_rollup', root), 43 * 1024)
            (proc / 'stat').write_text('123 (CU (name) with spaces) S ' + ' '.join(['0'] * 18 + ['987']))
            self.assertEqual(process_identity(123, root), '987')
            (proc / 'status').write_text('VmSize: 100 kB\n')
            with self.assertRaises(ValueError):
                read_rss(123, 'status', root)
            with self.assertRaises(FileNotFoundError):
                process_identity(124, root)

    def test_explicit_clock_anchor_and_rejection(self):
        response = WorkResponse_pb2.PlanResponse(operatorClockNs=101_000_000_000,
            collectorClockNs=1_000_000_000, clockAnchorUncertaintyNs=50)
        response.extendedResults.add(itemId=9, start=100_200_000_000, end=100_800_000_000)
        ops, error = aligned_operators(response, 0.1, 0.9)
        self.assertIsNone(error)
        self.assertEqual(ops[0]['start_ns'], 200_000_000)
        self.assertEqual(ops[0]['end_ns'], 800_000_000)
        self.assertTrue(aligned_operators(response, 0.3, 0.9)[1])
        response.ClearField('operatorClockNs')
        self.assertTrue(aligned_operators(response, 0.1, 0.9)[1])

    def test_live_sampler_detects_resident_growth_and_stops(self):
        code = ('import sys\nprint("ready", flush=True)\nsys.stdin.readline()\n'
                'buf = bytearray(32 * 1024 * 1024)\nprint("allocated", flush=True)\n'
                'sys.stdin.readline()\n')
        with tempfile.TemporaryDirectory() as tmp, subprocess.Popen(
                [sys.executable, '-u', '-c', code], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, text=True) as target:
            self.assertEqual(target.stdout.readline().strip(), 'ready')
            session = MemorySession(target.pid, Path(tmp), source='smaps_rollup',
                                    interval_ms=5, baseline_ms=40, tail_ms=20)
            try:
                session.start()
                session.baseline()
                before = session.metadata['baseline_bytes']
                target.stdin.write('\n')
                target.stdin.flush()
                self.assertEqual(target.stdout.readline().strip(), 'allocated')
                time.sleep(0.05)
            finally:
                session.finish()
                target.stdin.write('\n')
                target.stdin.flush()
            samples = load_samples(Path(tmp) / 'memory_samples.csv')
            self.assertGreater(max(s['rss_bytes'] for s in samples) - before, 28 * MIB)
            self.assertFalse(session.process.is_alive())
            # Sampling must remain independent of all rendering dependencies.
            self.assertFalse((Path(tmp) / 'memory.png').exists())
            self.assertNotIn('plot_error', session.metadata)

    def test_target_exit_is_reported_and_partial_artifacts_survive(self):
        with tempfile.TemporaryDirectory() as tmp, subprocess.Popen(
                [sys.executable, '-c', 'import time; time.sleep(30)']) as target:
            session = MemorySession(target.pid, Path(tmp), source='status',
                                    interval_ms=5, baseline_ms=30, tail_ms=20)
            try:
                session.start()
                target.terminate()
                target.wait(timeout=5)
                time.sleep(0.03)
                with self.assertRaises(RuntimeError):
                    session.check()
            finally:
                session.finish(benchmark_error='target exited')
            self.assertTrue(session.metadata['errors'])
            self.assertTrue((Path(tmp) / 'memory_summary.json').exists())
            self.assertFalse(session.process.is_alive())


class FakeClient:
    """Deterministic protocol peer; concurrent responses finish out of order."""
    instances = []
    failed = False

    def __init__(self, **kwargs):
        self.callbacks = {}
        self.uuid = 10
        self.connection_up = True
        self.timers = []
        self.disconnected = False
        self.instances.append(self)

    def register_callback(self, kind, callback):
        self.callbacks[kind] = callback

    def connect(self, *args):
        assert isinstance(args[1], int), 'socket port must be an integer'

    def send_message(self, message):
        if message.package_type == TcpPackageType.UUID_FOR_UNIT_REQUEST:
            reply = NetworkRequests_pb2.UuidForUnitResponse(names=['ComputeUnit'], uuids=[99],
                                                           requestedUnitType=UnitType.COMPUTE_UNIT)
            self.callbacks[TcpPackageType.UUID_FOR_UNIT_RESPONSE](SimpleNamespace(payload=reply.SerializeToString()))
        elif message.package_type == TcpPackageType.QUERY_PLAN:
            request = WorkRequest_pb2.WorkRequest()
            request.ParseFromString(message.payload)
            plan = request.queryPlan
            start = time.perf_counter_ns()
            def complete():
                end = time.perf_counter_ns()
                reply = WorkResponse_pb2.PlanResponse(planId=plan.planid, success=not self.failed,
                    info='failure' if self.failed else run_query.PLAN_SUCCESS_INFO,
                    operatorClockNs=end + 10**12, collectorClockNs=end,
                    clockAnchorUncertaintyNs=100, computeUnitPid=os.getpid(),
                    computeUnitHost=os.uname().nodename)
                reply.extendedResults.add(itemId=1, start=start + 10**12, end=end + 10**12, rowCount=1)
                self.callbacks[TcpPackageType.PLAN_RESPONSE](SimpleNamespace(payload=reply.SerializeToString()))
            timer = threading.Timer(0.09 if plan.planitems[0].itemId == 1 else 0.04, complete)
            self.timers.append(timer)
            timer.start()

    def disconnect(self):
        for timer in self.timers:
            timer.join()
        self.disconnected = True


class ComputeUnitDiscoveryTests(unittest.TestCase):
    def test_discovery_and_rejections(self):
        header = 'USER PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND\n'
        command = './build/bin/computeUnit -ip 127.0.0.1 -port 23233 -path data/binary/sf2 -basedata bin -worker 48 -node 0 -cxl_node 1'
        row = 'user 123 0 0 100 100 ? S 12:00 0:00 ' + command + '\n'
        # Unrelated processes mentioning the CU must not count as CU executables.
        unrelated = 'user 124 0 0 100 100 ? S 12:00 0:00 grep /bin/computeUnit\n'
        for listing, error in [(header + row + unrelated, None), (header, RuntimeError),
                               (header + row + row, RuntimeError),
                               (header + row.replace(' -worker 48', ''), RuntimeError),
                               (header + row.replace('sf2', 'dataset'), ValueError)]:
            with self.subTest(listing=listing), patch.object(run_query.subprocess, 'run',
                    return_value=SimpleNamespace(stdout=listing)):
                if error:
                    with self.assertRaises(error):
                        run_query.running_compute_unit()
                else:
                    result = run_query.running_compute_unit()
                    self.assertEqual((result['cu_pid'], result['scale_factor'], result['workers_per_cu']),
                                     (123, 2, 48))
                    self.assertEqual((result['ip'], result['port'], result['node'], result['cxl_node']),
                                     ('127.0.0.1', 23233, 0, 1))


class RunnerIntegrationTests(unittest.TestCase):
    def run_benchmark(self, root, mode, enabled=True, failed=False):
        plans = root / 'plans'
        plans.mkdir(exist_ok=True)
        for number in (1, 2):
            plan = QueryPlan_pb2.QueryPlan(planid=number)
            plan.planitems.add(itemId=number)
            (plans / f'q{number}.pb').write_bytes(plan.SerializeToString())
        config = root / 'config.yaml'
        config.write_text('benchmark:\n  runs: 2\n  warmup_runs: 1\n')
        argv = ['run_query.py', '--config', str(config), '-f', str(plans), '--execution-mode', mode]
        if enabled:
            argv += ['--measure-memory', '--memory-source', 'status',
                     '--memory-interval-ms', '5', '--memory-baseline-ms', '40', '--memory-tail-ms', '20']
        FakeClient.failed = failed
        original_import = __import__
        def collection_import(name, *args, **kwargs):
            # Fail if the benchmark path tries to invoke plotting again.
            if name == 'matplotlib' or name.startswith('matplotlib.'):
                raise AssertionError('collection must not import matplotlib')
            return original_import(name, *args, **kwargs)
        with patch.object(run_query.tcp_client, 'TCPClient', FakeClient), \
             patch.object(run_query, 'running_compute_unit', return_value={
                 'cu_pid': os.getpid(), 'ip': '127.0.0.1', 'port': 23233,
                 'scale_factor': 2, 'workers_per_cu': 48}), \
             patch.object(run_query, 'BENCHMARK_ROOT', root / 'results'), \
             patch('builtins.__import__', side_effect=collection_import), \
             patch.object(sys, 'argv', argv), contextlib.redirect_stdout(io.StringIO()):
            if failed:
                with self.assertRaises(SystemExit) as raised:
                    run_query.main()
                self.assertEqual(raised.exception.code, 1)
            else:
                run_query.main()
        path = next((root / 'results').rglob('results.json'))
        return path, json.loads(path.read_text())

    def test_sequential_and_concurrent_with_warmup(self):
        for mode in ('sequential', 'concurrent'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                old_handler = signal.getsignal(signal.SIGTERM)
                path, result = self.run_benchmark(Path(tmp), mode)
                memory = json.loads((path.parent / result['memory']['summary']).read_text())
                rounds = [w for w in memory['windows'] if w['kind'] == 'round']
                plans = [w for w in memory['windows'] if w['kind'] == 'plan']
                self.assertEqual(len(rounds), 3)
                self.assertEqual(len(memory['operators']), 6)
                self.assertTrue(all(w['memory']['coverage_complete'] for w in rounds))
                self.assertEqual(sum(w['warmup'] for w in rounds), 1)
                self.assertEqual([w['round'] for w in rounds], [1, 1, 2])
                self.assertEqual(len(result['queries']['q1.pb']['samples']), 2)
                self.assertGreater(memory['metadata']['baseline_sample_count'], 1)
                # A separate benchmark_plotting invocation renders these artifacts.
                self.assertFalse((path.parent / 'memory.png').exists())
                self.assertNotIn('plot', result['memory'])
                self.assertTrue(FakeClient.instances[-1].disconnected)
                self.assertEqual(signal.getsignal(signal.SIGTERM), old_handler)
                first, second = plans[:2]
                if mode == 'concurrent':
                    self.assertLess(second['start_ns'], first['end_ns'])
                    self.assertLess(second['end_ns'], first['end_ns'])
                else:
                    self.assertGreaterEqual(second['start_ns'], first['end_ns'])

    def test_disabled_keeps_existing_result_schema(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(run_query, 'MemorySession', side_effect=AssertionError('must stay disabled')):
            path, result = self.run_benchmark(Path(tmp), 'sequential', enabled=False)
            self.assertNotIn('memory', result)
            self.assertFalse((path.parent / 'memory_samples.csv').exists())
            self.assertNotIn('plan_id', result['queries']['q1.pb']['samples'][0])

    def test_failed_plans_still_save_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, result = self.run_benchmark(Path(tmp), 'concurrent', failed=True)
            memory = json.loads((path.parent / result['memory']['summary']).read_text())
            self.assertTrue(all(not w['success'] for w in memory['windows'] if w['kind'] == 'plan'))
            self.assertTrue(FakeClient.instances[-1].disconnected)

    def test_interrupt_preserves_trace_and_stops_collector(self):
        original = FakeClient.send_message
        sessions = []
        def interrupt(client, message):
            if message.package_type == TcpPackageType.QUERY_PLAN:
                raise KeyboardInterrupt('test interruption')
            return original(client, message)
        def create_session(*args, **kwargs):
            session = MemorySession(*args, **kwargs)
            sessions.append(session)
            return session
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(FakeClient, 'send_message', interrupt), \
             patch.object(run_query, 'MemorySession', side_effect=create_session):
            with self.assertRaises(KeyboardInterrupt):
                self.run_benchmark(Path(tmp), 'concurrent')
            session = sessions[0]
            self.assertFalse(session.process.is_alive())
            document = json.loads((session.directory / 'memory_summary.json').read_text())
            self.assertIn('KeyboardInterrupt', document['metadata']['benchmark_error'])
            self.assertTrue(FakeClient.instances[-1].disconnected)


if __name__ == '__main__':
    unittest.main()
