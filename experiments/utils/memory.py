"""Memory session: relates the collector's RSS samples to plan intervals and the CU memtrack log.

All interval integrals describe whole-CU RSS, never allocation ownership.
Operator intervals exist only with --memtrack: they come from the CU memtrack snapshots,
which share the CLOCK_MONOTONIC clock of the RSS samples.
"""
from __future__ import annotations

import bisect
import json
import multiprocessing as mp
import os
from pathlib import Path
import re
import statistics
import threading
import time

from proto import ConfigurationRequests_pb2 as ConfigurationRequests
from proto.UnitDefinition_pb2 import TcpPackageType
from utils import memtrack, util
from utils.memory_collector import collect_samples, load_samples

MIB = 1024 ** 2
GAP_FACTOR = 5  # sample gaps above GAP_FACTOR * interval are reported as a warning


def integrate(samples: list[dict], times: list[int], start_ns: int, end_ns: int) -> dict | None:
    """Trapezoid integral of RSS over [start_ns, end_ns]; None if the interval is not covered by samples."""
    if end_ns <= start_ns:
        return None

    # the neighbouring samples on each side bracket the interval (times is sorted)
    lo = bisect.bisect_right(times, start_ns) - 1
    hi = bisect.bisect_left(times, end_ns)

    if lo < 0 or hi >= len(samples):
        return None  # extrapolating beyond the trace would invent unobserved memory

    area = 0.0

    for a, b in zip(samples[lo:hi + 1], samples[lo + 1:hi + 1]):
        ta, tb = a['timestamp_ns'], b['timestamp_ns']

        # clip the sample pair to the interval
        left, right = max(start_ns, ta), min(end_ns, tb)
        if right <= left:
            continue

        # linear RSS between two samples: interpolate the clipped end points
        slope = (b['rss_bytes'] - a['rss_bytes']) / (tb - ta)
        value_left = a['rss_bytes'] + slope * (left - ta)
        value_right = a['rss_bytes'] + slope * (right - ta)

        # trapezoid: mean end point bytes times elapsed seconds
        area += (value_left + value_right) / 2 * ((right - left) / 1e9)

    duration = (end_ns - start_ns) / 1e9

    return {'duration_seconds': duration,
            'integral_mib_seconds': area / MIB,
            'average_rss_mib': area / duration / MIB,
            # fewer than 2 samples inside: the value comes from interpolating between outside samples
            'interpolated_only': bisect.bisect_right(times, end_ns) - bisect.bisect_left(times, start_ns) < 2}


class MemorySession:
    """Coordinate one collector process and relate its samples to plan intervals."""

    def __init__(self, pid: int, directory: Path, interval_ms=20.0, baseline_ms=500.0, tail_ms=500.0):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.samples_path = self.directory / 'memory_samples.csv'
        self.pid = pid

        # seconds for sleeps; nanoseconds for stored samples and interval boundaries
        self.interval = interval_ms / 1000
        self.baseline_seconds = baseline_ms / 1000
        self.tail_seconds = tail_ms / 1000
        self.max_gap_ns = int(interval_ms * GAP_FACTOR * 1e6)

        # settings are persisted so later analysis does not depend on CLI defaults
        self.metadata = {'session_id': self.directory.name, 'cu_pid': pid,
                         'host': os.uname().nodename, 'source': 'status',
                         'interval_ms': interval_ms, 'max_gap_ms': self.max_gap_ns / 1e6,
                         'clock': 'CLOCK_MONOTONIC', 'scope': 'whole_CU_RSS',
                         'baseline_bytes': None, 'baseline_duration_ms': baseline_ms,
                         'tail_ms': tail_ms, 'errors': [], 'warnings': []}

        # plan_id -> plan dict, in submission order; filled by begin_plan and complete_plan
        self.plans = {}

        # spawn avoids forking the runner after its TCP receiver thread has started
        self.context = mp.get_context('spawn')
        self.stop_event = self.context.Event()

        # one-way pipe: the collector sends readiness, errors and statistics; samples go to the CSV
        self.pipe, child = self.context.Pipe(duplex=False)
        self.process = self.context.Process(target=collect_samples,
            args=(pid, self.interval, str(self.samples_path), self.stop_event, child),
            name='cu-memory-collector', daemon=True)

        # the parent's copy of the send end is closed in start(), so child exit gives EOF on the read end
        self._child_pipe = child
        self.started = False
        self.finalized = False
        self.tracking = False

    def enable_tracking(self, memlog: str, client, src_uuid: int, tgt_uuid: int):
        """Collect the CU's per-operator memory log (CU built with RAM_TRACKING, started with -memlog)."""
        # the CU runs on this host, so its cwd tells where a relative -memlog path lands
        self.memlog_path = Path(f'/proc/{self.pid}/cwd').resolve() / memlog
        self.tracking = True

        # events older than this belong to an earlier session of the same CU process
        self.session_start_ns = time.perf_counter_ns()
        self._client, self._src, self._tgt = client, src_uuid, tgt_uuid

        self._cond = threading.Condition()  # guards the two fields below
        self._latest_flush = 0              # highest "flush #N" seen in a CU reply
        self._flush_failed = False
        self.metadata['memtrack_log'] = str(self.memlog_path)

        # registered once: handles every TEXT message of the session, replaces the default print handler
        client.register_callback(TcpPackageType.TEXT, self._on_cu_text)

    def _on_cu_text(self, message):
        """Runs on the client's receiver thread for every TEXT message, independent of flush_cu_log."""
        text = message.payload.decode()
        print(f'Received Text: {text}')

        found = re.search(r'flushed to .* \(flush #(\d+)\)', text)

        with self._cond:
            if found:
                self._latest_flush = max(self._latest_flush, int(found[1]))
            elif 'flush FAILED' in text:
                self._flush_failed = True

            self._cond.notify_all()  # wake up flush_cu_log

    def flush_cu_log(self, timeout=30):
        """Ask the CU to write its event log and wait for the acknowledgement."""
        with self._cond:
            floor = self._latest_flush  # only a reply with a higher number answers this request
            self._flush_failed = False

        self._client.send_message(util.create_configuration_item(
            source_uuid=self._src, target_uuid=self._tgt,
            type=ConfigurationRequests.ConfigType.FLUSH_MEMORY_LOG))

        with self._cond:
            # the CU answers every request twice; a late duplicate of an older reply keeps its old number
            answered = self._cond.wait_for(
                lambda: self._latest_flush > floor or self._flush_failed, timeout)
            failed = self._flush_failed

        if not answered:
            self.metadata['errors'].append('FLUSH_MEMORY_LOG not acknowledged (CU without RAM_TRACKING?)')
        elif failed:
            self.metadata['errors'].append('CU reported: memory log flush failed')

    def start(self):
        """Launch the collector and wait for its first sample before any measured work is submitted."""
        self.process.start()
        self.started = True
        self._child_pipe.close()

        if not self.pipe.poll(30):
            raise RuntimeError('CU memory collector did not become ready within 30 seconds')

        message = self.pipe.recv()
        if message['type'] != 'ready':
            self.metadata['errors'].append(message.get('error', str(message)))
            raise RuntimeError(self.metadata['errors'][-1])

        self.metadata.update({k: v for k, v in message.items() if k != 'type'})
        print(f'Memory sampling: PID {self.pid}, status, {self.interval * 1000:g} ms')

    def check(self):
        """Drain collector messages without waiting; raise on a reported error or an unexpected exit."""
        # message['type'] is one of 'ready', 'error', 'stopped'
        while self.pipe.poll():
            try:
                message = self.pipe.recv()
            except EOFError:
                break

            if message['type'] == 'error':
                self.metadata['errors'].append(message['error'])
            else:
                # 'ready' and 'stopped' (final statistics) go into the metadata
                self.metadata.update({k: v for k, v in message.items() if k != 'type'})

        if self.metadata['errors']:
            raise RuntimeError(self.metadata['errors'][-1])

        if self.started and not self.stop_event.is_set() and not self.process.is_alive():
            raise RuntimeError('CU memory collector exited unexpectedly')

    def baseline(self):
        """Take one fixed reference after configuration/warmup, before the measured rounds."""
        start = time.perf_counter_ns()
        time.sleep(self.baseline_seconds)  # the collector keeps sampling while we wait
        end = time.perf_counter_ns()
        self.check()

        # median over this quiet interval only, excluding earlier warmup activity
        samples = [s for s in load_samples(self.samples_path) if start <= s['timestamp_ns'] <= end]
        if len(samples) < 2:
            raise RuntimeError('baseline requires at least two memory samples; increase --memory-baseline-ms')

        self.metadata.update(baseline_bytes=statistics.median(s['rss_bytes'] for s in samples),
                             baseline_start_ns=start, baseline_end_ns=end,
                             baseline_sample_count=len(samples))

    def begin_plan(self, plan_id, query, round_number, warmup, submitted):
        """Register a plan at submission; end_ns and success are added by complete_plan."""
        # submission time is kept even if the plan never returns a response
        self.plans[plan_id] = {'plan_id': plan_id, 'query': query, 'round': round_number,
                               'warmup': warmup, 'start_ns': int(submitted * 1e9)}

    def complete_plan(self, response, arrived):
        """Close the plan interval at the response arrival time."""
        self.plans[response.planId].update(end_ns=int(arrived * 1e9),
                                           success=response.info == 'Plan completed successfully.')
        self.check()

    def finish(self, benchmark_error=None):
        """Stop sampling and persist numeric output, including interrupted executions."""
        if self.finalized:
            return self.metadata
        self.finalized = True
        interrupted = None

        try:
            if benchmark_error:
                self.metadata['benchmark_error'] = benchmark_error
            elif self.started and self.process.is_alive():
                # tail: keep sampling after the last response to observe cleanup (late frees)
                time.sleep(max(self.tail_seconds, self.interval * 2))
        except KeyboardInterrupt as error:
            interrupted = error
            self.metadata['benchmark_error'] = 'KeyboardInterrupt during tail collection'
        finally:
            # request shutdown even when another interrupt arrives during the tail
            self.stop_event.set()

        tracking_events = None
        if self.tracking:
            # after the tail, so the frees of dropTable are in the log too
            try:
                self.flush_cu_log(timeout=10)
                tracking_events = memtrack.load_events(self.memlog_path, since_ns=self.session_start_ns)
                memtrack.write_csv(tracking_events, self.directory / 'memtrack_events.csv')
            except Exception as error:  # keep the RSS results even if tracking fails
                self.metadata['errors'].append(f'memtrack: {type(error).__name__}: {error}')

        if self.started:
            self.process.join(timeout=5)

            if self.process.is_alive():
                # bound the shutdown if a /proc read or the child hangs
                self.process.terminate()
                self.process.join()
                self.metadata['errors'].append('collector terminated after shutdown timeout')

            try:
                self.check()  # collects the 'stopped' statistics and late errors
            except RuntimeError:
                pass  # persist the error and the partial trace; do not lose other results

            if self.process.exitcode and not self.metadata['errors']:
                self.metadata['errors'].append(f'collector exited with code {self.process.exitcode}')

        self._child_pipe.close()

        # read the trace only after its writer has exited and flushed
        samples = load_samples(self.samples_path) if self.samples_path.exists() else []
        times = [s['timestamp_ns'] for s in samples]
        gaps_ns = [b - a for a, b in zip(times, times[1:])]

        # report the sampling behaviour that was actually achieved
        self.metadata.update(sample_count=len(samples),
                             mean_sample_interval_ms=statistics.fmean(gaps_ns) / 1e6 if gaps_ns else None,
                             max_sample_interval_ms=max(gaps_ns) / 1e6 if gaps_ns else None)

        long_gaps = sum(gap > self.max_gap_ns for gap in gaps_ns)
        if long_gaps:
            warning = (f'{long_gaps} sample gaps exceed {self.max_gap_ns / 1e6:g} ms '
                       f'(max {max(gaps_ns) / 1e6:.1f} ms, interval {self.interval * 1000:g} ms)')
            self.metadata['warnings'].append(warning)
            print(f'WARNING: {warning}')

        # plans without a response have no end_ns and therefore no integral
        for plan in self.plans.values():
            plan['rss'] = integrate(samples, times, plan['start_ns'], plan['end_ns']) if 'end_ns' in plan else None

        document = {'metadata': self.metadata, 'plans': list(self.plans.values()),
                    'interpretation': 'plans: whole-CU RSS during the plan interval, overlapping integrals are not additive. '
                                      'operator_tracking: requested capacity attributed to the producing operator (virtual, not RSS); '
                                      'its operators carry the whole-CU RSS during their interval under "rss".'}

        if tracking_events is not None:
            try:
                tracking = memtrack.derive(tracking_events, self.plans)

                # operator intervals come from the memtrack snapshots, on the same clock as the samples
                for operator in tracking['operators']:
                    operator['rss'] = integrate(samples, times, operator['start_ns'], operator['end_ns'])

                document['operator_tracking'] = tracking
                self.metadata['memtrack_events_dropped'] = tracking['events_dropped']
                self.metadata['memtrack_unpaired_shrinks'] = tracking['unpaired_shrinks']
            except ValueError as error:  # keep the RSS results even if the log is inconsistent
                self.metadata['errors'].append(f'memtrack: {type(error).__name__}: {error}')

        # collection exports data only; plots are regenerated separately from these files
        summary = self.directory / 'memory_summary.json'
        summary.write_text(json.dumps(document, indent=2, allow_nan=False) + '\n')
        self.pipe.close()

        if interrupted is not None:
            raise interrupted

        return {'samples': self.samples_path.name, 'summary': summary.name,
                'baseline_bytes': self.metadata['baseline_bytes'], 'errors': self.metadata['errors']}
