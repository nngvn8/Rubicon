"""Collect whole-CU RSS and numeric summaries; rendering lives in benchmark_plotting.

The parent records execution intervals while a separate process reads /proc.
All interval integrals describe whole-CU memory, never allocation ownership.
"""
from __future__ import annotations

import bisect
import csv
import json
import math
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

MIB = 1024 ** 2


def process_identity(pid: int, proc_root: Path = Path('/proc')) -> str:
    """Linux stat field 22, accounting for spaces/parentheses in comm."""
    stat = (proc_root / str(pid) / 'stat').read_text()
    # Only the closing parenthesis reliably separates comm from numbered fields.
    fields = stat[stat.rindex(')') + 2:].split()
    # Zombies retain a /proc directory, but no longer provide a live RAM target.
    if fields[0] in ('Z', 'X'):
        raise ProcessLookupError(f'CU PID {pid} has exited')
    return fields[19]  # Field 22 is starttime; this slice begins at field 3.


def read_rss(pid: int, source: str, proc_root: Path = Path('/proc')) -> int:
    # Both files report RSS, but status uses cheaper, approximate accounting.
    key = 'Rss:' if source == 'smaps_rollup' else 'VmRSS:'
    for line in (proc_root / str(pid) / source).read_text().splitlines():
        fields = line.split()
        if fields and fields[0] == key:
            # Linux labels these units kB even though each unit contains 1024 bytes.
            if len(fields) != 3 or fields[2] != 'kB':
                raise ValueError(f'unexpected RSS units: {line}')
            return int(fields[1]) * 1024
    raise ValueError(f'{key} missing in /proc/{pid}/{source}')


def _collect(pid, source, interval, path, stop, pipe):
    """Spawned process: stream samples to disk, independent of the runner's GIL."""
    try:
        # Retain process starttime so a recycled numeric PID cannot contaminate the trace.
        identity = process_identity(pid)
        # A small pilot selects a source once. Never switch sources mid-trace.
        pilot = []
        candidate = 'smaps_rollup' if source == 'auto' else source
        try:
            for _ in range(3):
                started = time.perf_counter()
                read_rss(pid, candidate)
                pilot.append(time.perf_counter() - started)
        except (PermissionError, FileNotFoundError):
            if source != 'auto':
                raise
            # Distinguish an unavailable smaps file from a CU that has disappeared.
            process_identity(pid)
            candidate = 'status'
        if source == 'auto' and pilot and max(pilot) > interval / 4:
            # Reserve most of the sampling interval for sleeping, not page-table scans.
            candidate = 'status'
        # Fail before announcing readiness if the selected source cannot be read.
        read_rss(pid, candidate)
        cpu_start = time.process_time()
        wall_start = time.perf_counter()
        count = 0
        with Path(path).open('w', newline='', buffering=1) as stream:
            # Flush complete CSV rows promptly so crashes retain usable partial data.
            writer = csv.writer(stream)
            writer.writerow(['read_start_ns', 'read_end_ns', 'timestamp_ns', 'rss_bytes'])
            deadline = time.perf_counter()
            ready = False
            while True:
                start = time.perf_counter_ns()
                # Check identity around each RSS read, including the PID-reuse race.
                if process_identity(pid) != identity:
                    raise ProcessLookupError(f'CU PID {pid} was reused')
                rss = read_rss(pid, candidate)
                if process_identity(pid) != identity:
                    raise ProcessLookupError(f'CU PID {pid} changed during a read')
                end = time.perf_counter_ns()
                # A /proc read takes time; its midpoint is our snapshot approximation.
                writer.writerow([start, end, (start + end) // 2, rss])
                count += 1
                if not ready:
                    # Do not let the benchmark begin before its first sample exists.
                    pipe.send({'type': 'ready', 'source': candidate,
                               'pid_start_ticks': identity, 'pilot_read_seconds': pilot})
                    ready = True
                if stop.is_set():
                    break  # Include a final sample to bracket the last window.
                deadline += interval
                now = time.perf_counter()
                if deadline < now:
                    deadline = now + interval  # Rest after an overrun; never busy catch-up.
                # Event.wait permits prompt shutdown without an uninterruptible sleep.
                stop.wait(max(0, deadline - now))
        # Collector CPU time helps assess measurement cost, not CU execution cost.
        pipe.send({'type': 'stopped', 'sample_count': count,
                   'collector_cpu_seconds': time.process_time() - cpu_start,
                   'collector_wall_seconds': time.perf_counter() - wall_start})
    except Exception as error:
        # Send failures to the parent instead of silently producing a truncated trace.
        pipe.send({'type': 'error', 'error': f'{type(error).__name__}: {error}'})
    finally:
        pipe.close()


def load_samples(path: Path) -> list[dict]:
    """Load integer sample fields, tolerating a final row still being written."""
    with path.open(newline='') as stream:
        result = []
        # csv dict reader returns one dict per row
        for row in csv.DictReader(stream):
            try:
                result.append({key: int(value) for key, value in row.items()})
            except (TypeError, ValueError):
                # A baseline read may race the final, unfinished CSV row.
                continue
        return result


def integrate(samples: list[dict], start_ns: int, end_ns: int,
              baseline_bytes: float | None, max_gap_ns: int, times=None) -> dict:
    """Trapezoids with interpolated boundaries, no extrapolation or gap bridging."""
    if end_ns <= start_ns:
        raise ValueError('memory window must have positive duration')
    # Leave integrals null until the entire requested interval passes coverage checks.
    result = {'duration_seconds': (end_ns - start_ns) / 1e9,
              'coverage_complete': False, 'issues': [],
              'integral_mib_seconds': None, 'baseline_integral_mib_seconds': None,
              'average_rss_mib': None, 'start_rss_mib': None}
    if times is None:
        times = [s['timestamp_ns'] for s in samples]
    # Include the neighbor on each side so boundary values can be interpolated.
    lo = bisect.bisect_right(times, start_ns) - 1
    hi = bisect.bisect_left(times, end_ns)
    if lo < 0 or hi >= len(samples):
        # Extrapolating beyond the trace would invent unobserved memory behavior.
        result['issues'].append('window_not_bracketed_by_samples')
        return result
    selected = samples[lo:hi + 1]
    # A long gap invalidates the whole window rather than hiding it in an average.
    max_gap = max((b['timestamp_ns'] - a['timestamp_ns']
                   for a, b in zip(selected, selected[1:])), default=0)
    result['max_sample_gap_ms'] = max_gap / 1e6
    result['interior_sample_count'] = sum(start_ns <= s['timestamp_ns'] <= end_ns for s in selected)
    result['sampling_limited'] = result['interior_sample_count'] < 2
    # Check if sampling timestamps (means of RSS reads) exceed max gap
    if max_gap > max_gap_ns:
        result['issues'].append('sample_gap_exceeds_limit')
    # Check if read durations (of RSS) exceed max gap
    if any(s['read_end_ns'] - s['read_start_ns'] > max_gap_ns for s in selected):
        # A slow read is not an instantaneous observation, even at a valid midpoint.
        result['issues'].append('sample_read_exceeds_gap_limit')
    if result['issues']:
        return result
    area = 0.0
    for a, b in zip(selected, selected[1:]):
        ta, tb = a['timestamp_ns'], b['timestamp_ns']
        # Clip each sample pair to the requested interval before computing its area.
        left, right = max(start_ns, ta), min(end_ns, tb)
        if right <= left:
            continue
        # Assume a straight line between adjacent observations, not a constant RSS.
        slope = (b['rss_bytes'] - a['rss_bytes']) / (tb - ta)
        va = a['rss_bytes'] + slope * (left - ta) # for the case that left > ta interpolate va (right of ta) instad of directly using a['rss_bytes']
        vb = a['rss_bytes'] + slope * (right - ta)
        if left == start_ns:
            result['start_rss_mib'] = va / MIB
        # Trapezoid area: mean endpoint bytes multiplied by elapsed seconds.
        area += (va + vb) / 2 * ((right - left) / 1e9)
    duration = result['duration_seconds']
    result.update(coverage_complete=True, integral_mib_seconds=area / MIB,
                  average_rss_mib=area / duration / MIB)
    if baseline_bytes is not None:
        # Keep negative differences: RSS can fall below the fixed session baseline.
        result['baseline_integral_mib_seconds'] = (area - baseline_bytes * duration) / MIB
    return result


def aligned_operators(response, submitted: float, arrived: float) -> tuple[list[dict], str | None]:
    """Use an explicit CU clock anchor, never infer clock epochs from magnitudes."""
    required = ('operatorClockNs', 'collectorClockNs', 'clockAnchorUncertaintyNs')
    # Older binaries/bindings may not carry the optional calibration fields.
    if not all(name in response.DESCRIPTOR.fields_by_name and response.HasField(name)
               for name in required):
        return [], 'CU response has no clock anchor; rebuild CU and regenerate Python protobufs'
    # Paired clock readings translate native operator timestamps into collector time.
    offset = response.collectorClockNs - response.operatorClockNs
    uncertainty = response.clockAnchorUncertaintyNs
    result = []
    for item in response.extendedResults:
        start, end = item.start + offset, item.end + offset
        # Reject impossible overlays instead of guessing a different clock origin.
        if not (int(submitted * 1e9) - uncertainty <= start <= end <= int(arrived * 1e9) + uncertainty):
            return [], 'operator interval outside submission/response window; clock mapping rejected'
        result.append({'operator_id': item.itemId, 'start_ns': start, 'end_ns': end,
                       'clock_anchor_uncertainty_ns': uncertainty})
    return result, None


class MemorySession:
    """Coordinate one collector and associate its samples with benchmark intervals."""

    def __init__(self, pid: int, directory: Path, source='auto', interval_ms=20.0,
                 baseline_ms=500.0, tail_ms=500.0, max_gap_ms=None):
        # Reject NaN/infinite timing settings before allocating child-process resources.
        for name, value in [('interval_ms', interval_ms), ('baseline_ms', baseline_ms), ('tail_ms', tail_ms)]:
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f'{name} must be finite and positive')
        if max_gap_ms is not None and (not math.isfinite(max_gap_ms) or max_gap_ms < interval_ms):
            raise ValueError('max_gap_ms must be finite and at least interval_ms')
        if pid <= 0 or source not in ('auto', 'status', 'smaps_rollup'):
            raise ValueError('invalid CU PID or memory source')
        if time.get_clock_info('perf_counter').implementation != 'clock_gettime(CLOCK_MONOTONIC)':
            raise RuntimeError('memory collection requires perf_counter backed by CLOCK_MONOTONIC')
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.samples_path = self.directory / 'memory_samples.csv'
        self.pid, self.source = pid, source
        # Sleeps use seconds; stored samples and interval boundaries use nanoseconds.
        self.interval = interval_ms / 1000
        self.baseline_seconds = baseline_ms / 1000
        self.tail_seconds = tail_ms / 1000
        self.max_gap_ns = int((max_gap_ms if max_gap_ms is not None else interval_ms * 5) * 1e6)
        # Save the chosen settings so later analysis does not rely on CLI defaults.
        self.metadata = {'session_id': self.directory.name, 'cu_pid': pid,
                         'host': os.uname().nodename, 'requested_source': source,
                         'interval_ms': interval_ms, 'max_gap_ms': self.max_gap_ns / 1e6,
                         'clock': 'CLOCK_MONOTONIC', 'scope': 'whole_CU_RSS',
                         'baseline_bytes': None, 'baseline_duration_ms': baseline_ms,
                         'tail_ms': tail_ms, 'errors': []}
        # The dictionary and list share each plan's mutable interval record.
        self.windows = []
        self.plans = {}
        self.operators = []
        # Spawn avoids forking the runner after its TCP receiver thread has started.
        self.context = mp.get_context('spawn')
        self.stop_event = self.context.Event()
        # Create pipe that only works one way (duplex=False -> only child (_collect) can send to parent, not the other way around)
        # Returns sending end (child) and receiving end (self.pipe) of pipe 
        # Only readiness/errors/statistics cross the pipe; samples stream to CSV.
        self.pipe, child = self.context.Pipe(duplex=False)
        # Create process for collector (own python process with own PID, not the same as thread running under same PID)
        self.process = self.context.Process(target=_collect,
            args=(pid, source, self.interval, str(self.samples_path), self.stop_event, child),
            name='cu-memory-collector', daemon=True)
        # Saving child's pipe to close it later (not sure why not even closing now?)
        self._child_pipe = child
        self.started = False
        self.finalized = False
        self.tracking = False

    def enable_tracking(self, memlog: str, client, src_uuid: int, tgt_uuid: int):
        """Collect the CU's per-operator memory log (CU built with RAM_TRACKING, started with -memlog)."""
        # The CU runs on this host (checked via computeUnitHost), so its cwd tells where a relative path lands.
        self.memlog_path = Path(f'/proc/{self.pid}/cwd').resolve() / memlog
        self.tracking = True
        # Events older than this belong to an earlier session of the same CU process.
        self.session_start_ns = time.perf_counter_ns()
        self._client, self._src, self._tgt = client, src_uuid, tgt_uuid
        self._cond = threading.Condition()  # guards the two fields below
        self._latest_flush = 0              # highest "flush #N" seen in a CU reply
        self._flush_failed = False
        self.metadata['memtrack_log'] = str(self.memlog_path)
        # Registered once: it handles every TEXT message of the session and replaces the default print handler.
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
            # The CU answers every request twice; a late duplicate of an older reply keeps its old number.
            answered = self._cond.wait_for(
                lambda: self._latest_flush > floor or self._flush_failed, timeout)
            failed = self._flush_failed
        if not answered:
            self.metadata['errors'].append('FLUSH_MEMORY_LOG not acknowledged (CU without RAM_TRACKING?)')
        elif failed:
            self.metadata['errors'].append('CU reported: memory log flush failed')

    def start(self):
        """Wait for a usable first sample before submitting any measured work."""
        # Start previously created collector process
        self.process.start()
        self.started = True
        # The parent must close its copy so child exit becomes EOF on the read end. Sending would work with that copy left open.
        self._child_pipe.close()
        if not self.pipe.poll(30):
            raise RuntimeError('CU memory collector did not become ready within 30 seconds')
        message = self.pipe.recv()
        if message['type'] != 'ready':
            self.metadata['errors'].append(message.get('error', str(message)))
            raise RuntimeError(self.metadata['errors'][-1])
        self.metadata.update({k: v for k, v in message.items() if k != 'type'})
        print(f"Memory sampling: PID {self.pid}, {message['source']}, {self.interval * 1000:g} ms")

    def check(self):
        """Poll child messages without pausing query execution for a new sample."""
        # message['type'] is one of 'ready', 'error', 'stopped'
        while self.pipe.poll():
            try:
                message = self.pipe.recv()
            except EOFError:
                break
            if message['type'] == 'error':
                self.metadata['errors'].append(message['error'])
            # Write to metdata in case of ready or stopped (stopped reports final statistics)
            else:
                self.metadata.update({k: v for k, v in message.items() if k != 'type'})
        if self.metadata['errors']:
            raise RuntimeError(self.metadata['errors'][-1])
        if self.started and not self.stop_event.is_set() and not self.process.is_alive():
            raise RuntimeError('CU memory collector exited unexpectedly')

    def baseline(self):
        """Take one fixed reference after configuration/warmup, before measured rounds."""
        start = time.perf_counter_ns()
        time.sleep(self.baseline_seconds)
        end = time.perf_counter_ns()
        self.check()
        # Limit the median to this quiet interval, excluding earlier warmup activity.
        samples = [s for s in load_samples(self.samples_path) if start <= s['timestamp_ns'] <= end]
        if len(samples) < 2:
            raise RuntimeError('baseline requires at least two memory samples; increase --memory-baseline-ms')
        self.metadata.update(baseline_bytes=statistics.median(s['rss_bytes'] for s in samples),
                             baseline_start_ns=start, baseline_end_ns=end,
                             baseline_sample_count=len(samples))

    def begin_plan(self, plan_id, query, round_number, warmup, submitted):
        # Keep client submission time even if the plan never returns a response.
        window = {'kind': 'plan', 'plan_id': plan_id, 'query': query,
                  'round': round_number, 'warmup': warmup, 'start_ns': int(submitted * 1e9)}
        self.plans[plan_id] = window
        self.windows.append(window)

    def complete_plan(self, response, arrived):
        # Prove the measured local PID is the CU that actually executed this plan.
        if ('computeUnitPid' not in response.DESCRIPTOR.fields_by_name or
                not response.HasField('computeUnitPid') or
                not response.HasField('computeUnitHost')):
            raise RuntimeError('memory collection requires CU identity fields; rebuild CU and regenerate Python protobufs')
        if response.computeUnitPid != self.pid or response.computeUnitHost != self.metadata['host']:
            raise RuntimeError('response CU identity does not match the sampled local CU PID/host')
        window = self.plans[response.planId]
        window.update(end_ns=int(arrived * 1e9), success=response.info == 'Plan completed successfully.')
        if self.tracking and any(not i.HasField('minorFaults') for i in response.extendedResults):
            raise RuntimeError('--memtrack is set, but the CU sends no tracking data: build it with -DRAM_TRACKING=ON')
        # Preserve original timings even when their clock mapping must be rejected.
        window['native_operators'] = [{
            'operator_id': i.itemId, 'start': i.start, 'end': i.end, 'row_count': i.rowCount,
            'minor_faults': i.minorFaults if i.HasField('minorFaults') else None,
            'allocation_count': i.allocationCount if i.HasField('allocationCount') else None,
            'requested_bytes': i.requestedBytes if i.HasField('requestedBytes') else None,
        } for i in response.extendedResults]
        operators, reason = aligned_operators(response, window['start_ns'] / 1e9, arrived)
        window['operator_alignment_error'] = reason
        for operator in operators:
            # These IDs identify execution intervals, not ownership of RSS pages.
            operator.update(plan_id=response.planId, query=window['query'],
                            round=window['round'], warmup=window['warmup'])
            self.operators.append(operator)
        self.check()

    def complete_round(self, round_number, warmup, start, end):
        # Concurrent-round boundaries use the last response arrival, not wait order.
        self.windows.append({'kind': 'round', 'round': round_number, 'warmup': warmup,
                             'start_ns': int(start * 1e9), 'end_ns': int(end * 1e9)})

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
                # Observe cleanup separately from the submission-to-response windows.
                tail_start = max((w['end_ns'] for w in self.windows if w['kind'] == 'plan' and 'end_ns' in w),
                                 default=time.perf_counter_ns())
                time.sleep(max(self.tail_seconds, self.interval * 2))
                self.windows.append({'kind': 'tail', 'start_ns': tail_start,
                                     'end_ns': time.perf_counter_ns()})
        except KeyboardInterrupt as error:
            interrupted = error
            self.metadata['benchmark_error'] = 'KeyboardInterrupt during tail collection'
        finally:
            # Request shutdown even when another interrupt arrives during the tail.
            self.stop_event.set()
        tracking_events = None
        if self.tracking:
            # After the tail, so the frees of dropTable are in the log too.
            try:
                self.flush_cu_log(timeout=10)
                tracking_events = memtrack.load_events(self.memlog_path, since_ns=self.session_start_ns)
                memtrack.write_csv(tracking_events, self.directory / 'memtrack_events.csv')
            except Exception as error:  # keep the RSS results even if tracking fails
                self.metadata['errors'].append(f'memtrack: {type(error).__name__}: {error}')
        if self.started:
            self.process.join(timeout=5)
            if self.process.is_alive():
                # Bound shutdown if a kernel read or child process fails to finish.
                self.process.terminate()
                self.process.join()
                self.metadata['errors'].append('collector terminated after shutdown timeout')
            try:
                self.check()
            except RuntimeError:
                pass  # Persist error and partial trace; do not lose other results.
            if self.process.exitcode and not self.metadata['errors']:
                self.metadata['errors'].append(f'collector exited with code {self.process.exitcode}')
        self._child_pipe.close()
        # Read the finished trace only after its writer has exited and flushed data.
        samples = load_samples(self.samples_path) if self.samples_path.exists() else []
        times = [s['timestamp_ns'] for s in samples]
        reads = [(s['read_end_ns'] - s['read_start_ns']) / 1e6 for s in samples]
        gaps = [(b - a) / 1e6 for a, b in zip(times, times[1:])]
        # Report actual sampling behavior rather than assuming requested timing held.
        self.metadata.update(sample_count=len(samples),
                             mean_read_ms=statistics.fmean(reads) if reads else None,
                             max_read_ms=max(reads) if reads else None,
                             mean_sample_interval_ms=statistics.fmean(gaps) if gaps else None,
                             max_sample_interval_ms=max(gaps) if gaps else None)
        baseline = self.metadata['baseline_bytes']
        if len(samples) > 1:
            # This integral covers the entire trace, including baseline and tail.
            self.windows.append({'kind': 'session', 'start_ns': times[0], 'end_ns': times[-1]})
        for window in self.windows:
            if 'end_ns' not in window:
                # Incomplete plans retain their IDs but cannot receive an integral.
                window['memory'] = {'coverage_complete': False, 'issues': ['no_terminal_response']}
            else:
                window['memory'] = integrate(samples, window['start_ns'], window['end_ns'],
                                             baseline, self.max_gap_ns, times)
        for operator in self.operators:
            # Overlapping operator integrals describe the same CU curve; never sum them.
            if operator['end_ns'] > operator['start_ns']:
                operator['memory'] = integrate(samples, operator['start_ns'], operator['end_ns'],
                                               baseline, self.max_gap_ns, times)
        document = {'metadata': self.metadata, 'windows': self.windows, 'operators': self.operators,
                    'interpretation': 'windows/operators: whole-CU RSS during intervals, overlapping integrals are not additive. '
                                      'operator_tracking: requested capacity attributed to the producing operator (virtual, not RSS).'}
        if tracking_events is not None:
            try:
                document['operator_tracking'] = memtrack.derive(tracking_events, self.plans)
                self.metadata['memtrack_events_dropped'] = document['operator_tracking']['events_dropped']
                self.metadata['memtrack_unpaired_shrinks'] = document['operator_tracking']['unpaired_shrinks']
            except ValueError as error:  # keep the RSS results even if the log is inconsistent
                self.metadata['errors'].append(f'memtrack: {type(error).__name__}: {error}')
        summary = self.directory / 'memory_summary.json'
        # Collection exports data only; plots can be regenerated separately later.
        summary.write_text(json.dumps(document, indent=2, allow_nan=False) + '\n')
        self.pipe.close()
        if interrupted is not None:
            raise interrupted
        return {'samples': self.samples_path.name, 'summary': summary.name,
                'baseline_bytes': baseline, 'errors': self.metadata['errors']}
