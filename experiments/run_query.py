import argparse
import json
import math
import platform
import re
import statistics
import signal
import shlex
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict
from pathlib import Path

import yaml

from google.protobuf.json_format import MessageToDict

from utils import msg
from utils import client as tcp_client
from utils import util
from utils.unique_id import new_uint32_id
from utils.memory import MemorySession

from proto import NetworkRequests_pb2 as NetworkRequests
from proto import WorkRequest_pb2 as WorkRequest
from proto import WorkResponse_pb2 as WorkResponse
from proto import WorkItem_pb2 as WorkItem

from proto import ConfigurationRequests_pb2 as ConfigurationRequests
from proto import QueryPlan_pb2 as QueryPlan

from proto.UnitDefinition_pb2 import TcpPackageType, UnitType

from utils.queries import q_1_1, q_1_2, q_1_3, q_2_1, q_2_2, q_2_3, q_3_1, q_3_2, q_3_3, q_3_4, q_4_1, q_4_2, q_4_3

queries_dict = {"q_1_1": q_1_1, "q_1_2": q_1_2, "q_1_3": q_1_3, "q_2_1": q_2_1, "q_2_2": q_2_2, "q_2_3": q_2_3, "q_3_1": q_3_1, "q_3_2": q_3_2, "q_3_3": q_3_3, "q_3_4": q_3_4, "q_4_1": q_4_1, "q_4_2": q_4_2, "q_4_3": q_4_3}

# Set this to True to collect timings without passing --write-benchmark-results.
BENCHMARK_ROOT = Path(__file__).resolve().parent.parent / "benchmarking" / "data"
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
PLAN_SOURCES = {
    "plans": REPOSITORY_ROOT / "data" / "plans",
    "pb_plans": REPOSITORY_ROOT / "data" / "pb_plans",
}
# Metadata for the prebuilt plans; these values do not transform the plans.
DEFAULT_OPTIMIZATION = {
    "mat_type": "lateMatHybrid",
    "gco": True,
    "merge_sort": True,
    "semi_joins": False,
    "materialize_into_join": False,
}

DEFAULT_BENCHMARK_CONFIG = Path(__file__).resolve().parent / "configs" / "benchmark_example.yaml"

# Threading (or maybe also not) - not sure if needed
name_list: List[str] = []
uuid_list: List[int] = []

uuid_condition = threading.Condition()

# Plan ID -> (terminal response, client timestamp captured after parsing).
completed: Dict[int, Tuple[WorkResponse.PlanResponse, float]] = {}
complete_condition = threading.Condition()

# ComputeUnit uses this exact terminal PlanResponse.info value only after a
# complete plan reaches its ResultOperator. Failed plans receive a different
# diagnostic message (or no response on a transport failure), so this is the
# wire-level success contract used by this script.
PLAN_SUCCESS_INFO = "Plan completed successfully."

config_replies: List[bool] = []
config_condition = threading.Condition()

# ----------------------------
# Helpers: callbacks
# ----------------------------
def update_uuids(message: msg.TCPMessage):
    global name_list, uuid_list, uuid_condition
    response = NetworkRequests.UuidForUnitResponse()
    response.ParseFromString(message.payload)

    with uuid_condition:
        name_list.clear()
        uuid_list.clear()
        name_list.extend(list(response.names))
        uuid_list.extend(list(response.uuids))
        uuid_condition.notify_all()
        

def plan_finished_cb(message: msg.TCPMessage):
    global complete_condition, completed
    response: WorkResponse.PlanResponse = WorkResponse.PlanResponse()
    response.ParseFromString(message.payload)
    arrived = time.perf_counter()
    with complete_condition:
        completed[response.planId] = (response, arrived)
        complete_condition.notify_all()


def server_config_response_cb(message: msg.TCPMessage):
    """Optional: wait/confirm config changes were applied."""
    resp = NetworkRequests.ServerConfigurationResponse()
    resp.ParseFromString(message.payload)

    with config_condition:
        config_replies.append(bool(resp.success))
        config_condition.notify_all()

# ----------------------------
# Helpers: Rubicon Setup
# ----------------------------
def wait_next_completion(client, plan_id, timeout=300.0):
    with complete_condition:
        deadline = time.monotonic() + timeout
        while plan_id not in completed and client.connection_up:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"Timeout waiting for plan_id={plan_id}")
            complete_condition.wait(timeout=remaining)

        # Retain the pair for round calculations; clear it at the round boundary.
        if plan_id not in completed:
            raise ConnectionError(f"Connection lost waiting for plan_id={plan_id}")
        return completed[plan_id]


def wait_for_config_reply(client: tcp_client.TCPClient) -> Optional[bool]:
    """Returns success True/False if response comes, else None."""
    with config_condition:
        while len(config_replies) == 0 and client.connection_up:
            config_condition.wait()

        if len(config_replies) > 0:
            return config_replies.pop(0)
    return None

def discover_compute_unit(client: tcp_client.TCPClient) -> Tuple[int, int]:
    """Returns (src_uuid, tgt_compute_uuid)."""
    # Ask for compute units
    work = util.create_uuid_request_item(type=UnitType.COMPUTE_UNIT)
    client.send_message(work)

    with uuid_condition:
        if len(uuid_list) == 0 and client.connection_up:
            uuid_condition.wait(timeout=5.0)

    tgt_uuid = 0
    for name, uuid in zip(name_list, uuid_list):
        if "ComputeUnit" in name:
            tgt_uuid = uuid
            break

    if tgt_uuid == 0:
        raise RuntimeError("Could not find a ComputeUnit.")

    return client.uuid, tgt_uuid


def set_workers_for_compute_units(client: tcp_client.TCPClient, workers: int):
    """Same as in your script, but extracted."""
    src_uuid = client.uuid
    for name, uuid in zip(name_list, uuid_list):
        if "ComputeUnit" not in name:
            continue
        work = util.create_configuration_item(
            source_uuid=src_uuid,
            target_uuid=uuid,
            type=ConfigurationRequests.ConfigType.SET_WORKER,
            worker_count=workers,
        )
        client.send_message(work)


def load_query_plan_from_pb(pb_file_path: str, src_uuid: int = 0, target_uuid: int = 0, extended_results: bool = False, random_pid: bool = False) -> msg.TCPMessage:
    # 1. Load the raw QueryPlan protobuf from disk
    qplan = QueryPlan.QueryPlan()
    with open(pb_file_path, "rb") as f:
        qplan.ParseFromString(f.read())

    if random_pid:
        qplan.planid = new_uint32_id()
    for item in qplan.planitems:
        item.returnExtendedResult = extended_results
        item.planId = qplan.planid

    # 2. Wrap it in a WorkRequest
    request = WorkRequest.WorkRequest()
    request.queryPlan.CopyFrom(qplan)

    # 3. Wrap it in a TCPMessage
    tcp_msg = msg.TCPMessage(
        unit_type=UnitType.QUERY_PLANER,
        package_type=TcpPackageType.QUERY_PLAN,
        src_uuid=src_uuid,
        tgt_uuid=target_uuid
    )
    tcp_msg.payload = request.SerializeToString()
    
    return tcp_msg, qplan

def run_one_query(client: tcp_client.TCPClient, query_msg: msg.TCPMessage) -> Tuple[WorkResponse.PlanResponse, float]:
    """Submit a plan and return its terminal response, if one arrives."""
    req = WorkRequest.WorkRequest()
    req.ParseFromString(query_msg.payload)
    plan_id = req.queryPlan.planid

    t_s = time.perf_counter()
    client.send_message(query_msg)
    plan_response, t_e = wait_next_completion(client, plan_id)
    total_response_time = t_e - t_s

    return plan_response, total_response_time


def enrich_query_plan(query_plan: QueryPlan.QueryPlan, plan_response: WorkResponse.PlanResponse) -> Dict:
    ext_results = {
        ext.itemId: {
            "itemId": ext.itemId,
            "start": ext.start,
            "end": ext.end,
            "rowCount": ext.rowCount,
        }
        for ext in plan_response.extendedResults
    }

    enriched_plan = MessageToDict(query_plan, preserving_proto_field_name=True)
    enriched_plan["success"] = plan_response.success
    enriched_plan["info"] = plan_response.info

    orig_items = {item.itemId: item for item in query_plan.planitems}
    for item_dict in enriched_plan["planitems"]:
        item_id = item_dict["itemId"]
        if orig_items[item_id].returnExtendedResult and item_id in ext_results:
            item_dict["extendedResult"] = ext_results[item_id]
            item_dict.pop("returnExtendedResult", None)

    return enriched_plan


def summarize(samples: List[Dict]) -> Dict[str, Dict[str, float]]:
    """Calculate summary statistics for each timing metric with observations."""
    summary: Dict[str, Dict[str, float]] = {}
    for metric in ("total_response_time", "plan_duration", "operator_work"):
        values = [sample[metric] for sample in samples]
        if not values:
            continue
        summary[metric] = {
            "count": len(values),
            "mean": statistics.fmean(values),
            "median": statistics.median(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
            "min": min(values),
            "max": max(values),
        }
    return summary


def natural_sort_key(path: Path) -> List[object]:
    """Sort q_1_2.pb before q_1_10.pb, independent of filesystem order."""
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", path.name)]


def normalize_variant_value(value: object) -> bool | int | float | str:
    """Keep variant metadata scalar, so it is stable in JSON and path names."""
    if isinstance(value, (bool, int, float, str)):
        return value
    raise ValueError(f"variant values must be scalar, got {type(value).__name__}")


def parse_variant_assignments(assignments: List[str]) -> Dict[str, bool | int | float | str]:
    """Parse repeatable key=value CLI variant overrides."""
    variants: Dict[str, bool | int | float | str] = {}
    for assignment in assignments:
        if "=" not in assignment:
            raise ValueError(f"invalid variant {assignment!r}; expected key=value")
        key, raw_value = assignment.split("=", 1)
        if not key:
            raise ValueError("variant key must not be empty")
        try:
            value = yaml.safe_load(raw_value)
        except yaml.YAMLError as error:
            raise ValueError(f"invalid variant value for {key!r}: {error}") from error
        variants[key] = normalize_variant_value(value)
    return variants


def variant_slug(variant: Dict[str, bool | int | float | str]) -> str:
    """Create a deterministic filesystem-friendly category for a variant map."""
    if not variant:
        return "default"

    def slugify(value: object) -> str:
        return re.sub(r"[^a-zA-Z0-9._-]+", "-", str(value).lower()).strip("-") or "empty"

    return "__".join(
        f"{slugify(key)}={slugify(value)}" for key, value in sorted(variant.items())
    )


def load_benchmark_config(config_path: Optional[str]) -> Dict:
    """Load and minimally validate an optional YAML benchmark configuration."""
    if config_path is None:
        return {}
    path = Path(config_path)
    try:
        with path.open("r", encoding="utf-8") as config_file:
            config = yaml.safe_load(config_file) or {}
    ################## Data Validation START ####################
    except (OSError, yaml.YAMLError) as error:
        raise ValueError(f"could not read config {path}: {error}") from error
    if not isinstance(config, dict):
        raise ValueError("benchmark config must contain a YAML mapping")
    for key in ("benchmark", "variant", "experiment", "optimization", "compilation"):
        if key in config and not isinstance(config[key], dict):
            raise ValueError(f"config field {key!r} must be a mapping")
    for key in ("optimization_level", "log_level"):
        if key in config.get("compilation", {}):
            value = config["compilation"][key]
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"compilation field {key!r} must be a nonempty string")
    if "plan_source" in config and config["plan_source"] not in PLAN_SOURCES:
        raise ValueError(f"config plan_source must be one of: {', '.join(PLAN_SOURCES)}")
    mode = config.get("benchmark", {}).get("execution_mode", "sequential")
    if mode not in ("sequential", "concurrent"):
        raise ValueError("benchmark execution_mode must be sequential or concurrent")
    optimization = {**DEFAULT_OPTIMIZATION, **config.get("optimization", {})}
    if optimization["mat_type"] not in ("std", "lateMat", "lateMatHybrid"):
        raise ValueError("optimization mat_type must be std, lateMat, or lateMatHybrid")
    for key, value in optimization.items():
        if key != "mat_type" and not isinstance(value, bool):
            raise ValueError(f"optimization field {key!r} must be a boolean")
    ################## Data Validation END ####################
    config["optimization"] = optimization
    if "variant" in config:
        config["variant"] = {
            str(key): normalize_variant_value(value)
            for key, value in config["variant"].items()
        }
    return config


def create_benchmark_file(
    workers: int, scale_factor: int, runs: int, variant: Dict[str, bool | int | float | str],
    execution_mode: str,
) -> Path:
    """Create a unique benchmark directory without using randomized plan ids."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    if execution_mode not in ("concurrent", "sequential"):
        raise ValueError("execution_mode must be sequential or concurrent")
    run_name = f"{timestamp}_sf-{scale_factor}_runs-{runs}_workers-{workers}"
    mode_dir = BENCHMARK_ROOT / variant_slug(variant) / execution_mode
    benchmark_dir = mode_dir / run_name
    suffix = 1
    while benchmark_dir.exists():
        benchmark_dir = mode_dir / f"{run_name}_{suffix}"
        suffix += 1
    benchmark_dir.mkdir(parents=True)
    return benchmark_dir / "results.json"


def write_benchmark_results(benchmark_file: Path, results: Dict) -> None:
    """Write one self-contained benchmark result file."""
    with benchmark_file.open("w", encoding="utf-8") as output_file:
        json.dump(results, output_file, indent=2, sort_keys=True)
        output_file.write("\n")

def running_compute_unit(user="mschmidt") -> Dict:
    """Extract configuration from exactly one CU owned by mschmidt."""
    # Avoid a shell/grep subprocess matching its own search command; keep full command lines.
    listing = subprocess.run(['ps', 'auxww'], check=True, capture_output=True, text=True).stdout
    expected = ('-ip', '-port', '-path', '-basedata', '-worker', '-node', '-cxl_node')
    matches = []
    candidates = []
    for line in listing.splitlines()[1:]:
        # ps aux has ten fixed columns followed by the complete COMMAND column.
        columns = line.split(None, 10)
        if len(columns) != 11:
            continue
        # Ignore ComputeUnits belonging to other users on the shared machine.
        if columns[0] != user:
            continue
        command = columns[10]
        # Match the executable, not another process mentioning a CU in its arguments.
        executable = command.split(None, 1)[0]
        if not re.search(r'/bin/computeUnit$', executable):
            continue
        candidates.append(f'PID {columns[1]}: {command}')
        tokens = shlex.split(command)
        # Require every expected flag exactly once, followed by its value.
        # All of them must be there. 
        # All of them must be followed by a value. 
        # There cannot not be too many as otherwise exceeding length.
        if any(tokens.count(flag) != 1 or tokens.index(flag) + 1 >= len(tokens)
               or tokens[tokens.index(flag) + 1] in expected for flag in expected):
            continue
        flags = {flag: tokens[tokens.index(flag) + 1] for flag in expected}
        # Matches are pairs of pids and their corresponding flag dictionaries.
        matches.append((int(columns[1]), flags))
    if len(matches) != 1:
        raise RuntimeError(f'Expected exactly one /bin/computeUnit owned by mschmidt with flags {expected}; '
                           f'found {len(matches)} matching processes. CU candidates: {candidates}')
    pid, flags = matches[0]
    # Scale factor is encoded in the dataset directory, not an independent CU flag.
    scale = re.fullmatch(r'sf([1-9][0-9]*)', Path(flags['-path']).name)
    if scale is None:
        raise ValueError(f"Cannot infer scale factor from CU data path {flags['-path']!r}; expected sf<number>")
    port, workers = int(flags['-port']), int(flags['-worker'])
    if not 1 <= port <= 65535 or workers <= 0:
        raise ValueError(f'Invalid CU port or worker count: {flags}')
    # Preserve the other launch settings as provenance alongside the benchmark results.
    return {'cu_pid': pid, 'ip': flags['-ip'], 'port': port,
            'workers_per_cu': workers, 'scale_factor': int(scale[1]),
            'data_path': flags['-path'], 'basedata': flags['-basedata'],
            'node': int(flags['-node']), 'cxl_node': int(flags['-cxl_node'])}


# ----------------------------
# Main
# ----------------------------
def main():
    # Parse --config first so its values become defaults, while later CLI
    # arguments still take precedence over that configuration.
    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument(
        "--config",
        default=str(DEFAULT_BENCHMARK_CONFIG),
        help="YAML benchmark configuration file.",
    )
    config_args, _ = config_parser.parse_known_args()
    try:
        benchmark_config = load_benchmark_config(config_args.config)
    except ValueError as error:
        config_parser.error(str(error))
    benchmark_defaults = benchmark_config.get("benchmark", {})

    # Setup Parser
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default=str(DEFAULT_BENCHMARK_CONFIG),
        help="YAML benchmark configuration file (default: configs/benchmark_example.yaml).",
    )
    parser.add_argument(
        "--execution-mode", choices=("sequential", "concurrent"),
        default=benchmark_defaults.get("execution_mode", "sequential"),
        help="Submit and wait per query, or submit the entire batch before waiting.",
    )
    # Client labels and optional query selection remain CLI-only settings.
    parser.add_argument("-info", default="Query benchmark")
    parser.add_argument("-name", default="Query benchmark client")
    parser.add_argument('-q', help='Which queries to run, as a comma-separated string.')
    parser.add_argument('-f', help='Folder or single .pb query file to read (overrides --plan-source).')
    parser.add_argument(
        "--plan-source",
        choices=PLAN_SOURCES.keys(),
        default=benchmark_config.get("plan_source", "plans"),
        help="Named repository plan directory (default: %(default)s).",
    )
    parser.add_argument(
        "--variant",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Override or add experiment variant metadata; repeatable.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=benchmark_defaults.get("runs", 1),
        help="Number of measured full-batch rounds to execute (default: %(default)s).",
    )
    parser.add_argument(
        "--warmup-runs",
        type=int,
        default=benchmark_defaults.get("warmup_runs", 0),
        help="Number of full-batch warmup rounds to execute before measuring (default: %(default)s).",
    )
    parser.add_argument(
        "--write-benchmark-results",
        action=argparse.BooleanOptionalAction,
        default=benchmark_defaults.get("write_benchmark_results", True),
        help="Write a timestamped benchmark result directory under benchmarking/.",
    )
    # Memory collection uses the PID discovered from the local CU process.
    # BooleanOptionalAction also permits --no-measure-memory to override YAML true.
    parser.add_argument('--measure-memory', action=argparse.BooleanOptionalAction,
                        default=benchmark_defaults.get('measure_memory', False),
                        help='Collect local CU RSS and integrals beside benchmark results.')
    parser.add_argument('--memory-source', choices=('auto', 'smaps_rollup', 'status'),
                        default=benchmark_defaults.get('memory_source', 'auto'),
                        help='auto pilots smaps_rollup cost and selects one source for the session.')
    parser.add_argument('--memory-interval-ms', type=float, default=benchmark_defaults.get('memory_interval_ms', 20.0))
    parser.add_argument('--memory-baseline-ms', type=float, default=benchmark_defaults.get('memory_baseline_ms', 500.0))
    parser.add_argument('--memory-tail-ms', type=float, default=benchmark_defaults.get('memory_tail_ms', 500.0))
    parser.add_argument('--memory-max-gap-ms', type=float, default=benchmark_defaults.get('memory_max_gap_ms'),
                        help='Reject integration across larger sample gaps (default: 5 sampling intervals).')

    args = parser.parse_args()
    # Discover only after parsing, so --help works without a running CU.
    cu_settings = running_compute_unit()
    vars(args).update(cu_settings)
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    if args.warmup_runs < 0:
        parser.error("--warmup-runs must not be negative")
    if args.measure_memory:
        # Validate settings before connecting or launching a sampling process.
        for name in ('memory_interval_ms', 'memory_baseline_ms', 'memory_tail_ms'):
            if not math.isfinite(getattr(args, name)) or getattr(args, name) <= 0:
                parser.error(f'--{name.replace("_", "-")} must be finite and positive')
        if args.memory_max_gap_ms is not None and (not math.isfinite(args.memory_max_gap_ms)
                or args.memory_max_gap_ms < args.memory_interval_ms):
            parser.error('--memory-max-gap-ms must be finite and at least --memory-interval-ms')
    try:
        variant = dict(benchmark_config.get("variant", {}))
        variant.update(parse_variant_assignments(args.variant))
    except ValueError as error:
        parser.error(str(error))

    # Setup Client
    client = tcp_client.TCPClient(unit_type=UnitType.QUERY_PLANER, unit_info=args.info, name=args.name)

    query_list: List[str] = []
    using_pb_files = not bool(args.q)
    if args.q:
        qs = args.q.split(",")
        query_list.extend([query.strip() for query in qs])
    elif args.f:
        path = Path(args.f)
        # A single protobuf file permits process restarts without moving plan files.
        if path.is_file() and path.suffix == ".pb":
            query_list = [str(path)]
        elif path.is_dir():
            query_list = [str(path) for path in sorted(path.glob("*.pb"), key=natural_sort_key)]
        else:
            parser.error(f"plan folder or .pb file does not exist: {path}")
    else:
        path = PLAN_SOURCES[args.plan_source]
        if not path.is_dir():
            parser.error(f"named plan source does not exist: {path}")
        query_list = [str(path) for path in sorted(path.glob("*.pb"), key=natural_sort_key)]

    if not query_list:
        parser.error('no query plans selected')

    # Register callbacks (copied from concurrent query_execution_experiment.py - not sure if needed)
    client.register_callback(TcpPackageType.UUID_FOR_UNIT_RESPONSE, update_uuids)
    client.register_callback(TcpPackageType.SERVER_CONFIGURATION_RESPONSE, server_config_response_cb)
    client.register_callback(TcpPackageType.PLAN_RESPONSE, plan_finished_cb)

    client.connect(args.ip, args.port)

    # Extract relevant args
    workers_per_cu = args.workers_per_cu
    scale_factor = args.scale_factor
    write_benchmark_results_enabled =  args.write_benchmark_results
    benchmark_results: Dict[str, Dict] = {}
    round_results: List[Dict] = []
    benchmark_file: Optional[Path] = None
    if write_benchmark_results_enabled:
        benchmark_file = create_benchmark_file(
            workers_per_cu, scale_factor, args.runs, variant, args.execution_mode
        )

    # Configure the ComputeUnit once. This keeps discovery and configuration
    # out of every measured execution.
    all_succeeded = True
    EXTENDED_RESULT = True
    RANDOM_PID = True
    memory = None
    memory_artifacts = None
    previous_sigterm = None
    try:
        src_uuid, tgt_uuid = discover_compute_unit(client)
        set_workers_for_compute_units(client, workers_per_cu)
        time.sleep(1.0)
        if args.measure_memory:
            assert benchmark_file is not None
            # Write measurements next to this session's timing JSON for later plotting.
            memory = MemorySession(args.cu_pid, benchmark_file.parent,
                source=args.memory_source, interval_ms=args.memory_interval_ms,
                baseline_ms=args.memory_baseline_ms, tail_ms=args.memory_tail_ms,
                max_gap_ms=args.memory_max_gap_ms)
            # Preserve context even if an exception prevents results.json from being written.
            memory.metadata['benchmark'] = {
                'execution_mode': args.execution_mode, 'scale_factor': scale_factor,
                'workers_per_cu': workers_per_cu, 'warmup_rounds': args.warmup_runs,
                'measured_rounds': args.runs, 'variant': variant, 'config_file': args.config,
                'query_order': [Path(query).name for query in query_list],
            }
            # Ensure SIGTERM also passes through the collector's cleanup path.
            def terminate_benchmark(signum, frame):
                raise KeyboardInterrupt('benchmark terminated')
            previous_sigterm = signal.signal(signal.SIGTERM, terminate_benchmark)
            # start() waits for the first sample, ensuring future windows are bracketed.
            memory.start()

        for query in query_list:
            benchmark_results[Path(query).name] = {"samples": [], "failures": []}

        def submit(query_msg, plan_id, submitted, send_ends, query):
            submitted[plan_id] = time.perf_counter()
            if memory:
                # Save the same submission time used by latency measurements.
                memory.begin_plan(plan_id, Path(query).name,
                                  round_number if is_warmup else measured_round,
                                  is_warmup, submitted[plan_id])
            client.send_message(query_msg)
            send_ends.append(time.perf_counter())

        total_rounds = args.warmup_runs + args.runs
        for round_number in range(1, total_rounds + 1):
            is_warmup = round_number <= args.warmup_runs
            measured_round = round_number - args.warmup_runs
            label = "warmup" if is_warmup else f"measured round {measured_round}/{args.runs}"
            print(f"\n=== {label} ===")
            if memory:
                memory.check()
                if round_number == args.warmup_runs + 1:
                    # Measure the reference once; later rounds must retain memory drift.
                    memory.baseline()

            with complete_condition:
                completed.clear()

            # Prepare all plans before the measured submission interval.
            prepared = []
            for query in query_list:
                if using_pb_files:
                    query_tcp_msg, query_plan = load_query_plan_from_pb(
                        query, src_uuid=src_uuid, target_uuid=tgt_uuid,
                        extended_results=EXTENDED_RESULT, random_pid=RANDOM_PID,
                    )
                else:
                    q = queries_dict[query]
                    query_tcp_msg, query_plan = q(
                        planId=new_uint32_id(), src_uuid=src_uuid, target_uuid=tgt_uuid,
                        scale_factor=scale_factor, extendedResult=EXTENDED_RESULT,
                    )

                prepared.append((query, query_tcp_msg, query_plan))

            # Maps plan ID to the client timestamp immediately before sending.
            submitted = {}
            # Maps plan ID to its saved sample dictionary (a reference, not a copy).
            samples_by_plan = {}
            # Client timestamps after each socket send returns; not server receipt times.
            send_ends = []
            # Start of this round
            round_start = time.perf_counter()

            if args.execution_mode == "concurrent":
                for query, query_msg, plan in prepared:
                    submit(query_msg, plan.planid, submitted, send_ends, query)

            # Responses can arrive in any order; their arrival times are captured
            # by the receiver, independently of the order in which we collect them.
            for query, query_msg, query_plan in prepared:
                print(query)
                plan_id = query_plan.planid
                if args.execution_mode == "sequential":
                    submit(query_msg, plan_id, submitted, send_ends, query)
                remaining = max(0.0, submitted[plan_id] + 300.0 - time.perf_counter())
                plan_response, arrived = wait_next_completion(client, plan_id, timeout=remaining)
                if memory:
                    # Use receiver arrival time, not this loop's response-processing order.
                    memory.complete_plan(plan_response, arrived)
                total_response_time = arrived - submitted[plan_id]
                print(f"Total response time: {total_response_time} seconds")

                extended = plan_response.extendedResults
                if not extended:
                    raise RuntimeError(f"Missing operator timings for plan_id={plan_id}")
                plan_duration_s = (max(item.end for item in extended) - min(item.start for item in extended)) / 1e9
                operator_work_s = sum(item.end - item.start for item in extended) / 1e9
                print(f"Plan duration: {plan_duration_s} seconds")
                print(f"Operator work: {operator_work_s} seconds")

                succeeded = plan_response.info == PLAN_SUCCESS_INFO
                if not succeeded:
                    failure = plan_response.info
                    print(f"Query {query} FAILED: {failure}")
                    if not is_warmup:
                        all_succeeded = False
                        benchmark_results[Path(query).name]["failures"].append({
                            "round": measured_round, "error": failure,
                        })
                elif not is_warmup:
                    benchmark_results[Path(query).name]["samples"].append({
                        "round": measured_round,
                        "total_response_time": total_response_time,
                        "plan_duration": plan_duration_s,
                        "operator_work": operator_work_s,
                        "submission_offset": submitted[plan_id] - round_start,
                    })
                    samples_by_plan[plan_id] = benchmark_results[Path(query).name]["samples"][-1]
                    if memory:
                        # Randomized plan IDs link a timing sample to its memory window.
                        samples_by_plan[plan_id]['plan_id'] = plan_id
                    print(plan_response.info)

            extended = [item for response, _ in completed.values()
                        for item in response.extendedResults]
            first_start = min(item.start for item in extended)
            last_end = max(item.end for item in extended)
            arrivals = [arrived for _, arrived in completed.values()]
            if memory:
                # Warmup and measured rounds each start at 1; the warmup flag disambiguates.
                memory.complete_round(round_number if is_warmup else measured_round,
                                      is_warmup, round_start, max(arrivals))
            if not is_warmup:
                # All durations/offsets are seconds. Server offsets use the
                # earliest operator start in this round as their origin.
                round_results.append({
                    "round": measured_round,
                    "submission_span": max(send_ends) - round_start,
                    "total_response_time": max(arrivals) - round_start,
                    "server_round_duration": (last_end - first_start) / 1e9,
                })
                for query, _, plan in prepared:
                    response, _ = completed[plan.planid]
                    if response.info != PLAN_SUCCESS_INFO:
                        continue
                    sample = samples_by_plan[plan.planid]
                    sample["server_start_offset"] = (min(i.start for i in response.extendedResults) - first_start) / 1e9
                    sample["server_end_offset"] = (max(i.end for i in response.extendedResults) - first_start) / 1e9
        for result in benchmark_results.values():
            result["summary"] = summarize(result["samples"])

    finally:
        try:
            if memory:
                error = sys.exc_info()[1]
                # Keep partial numeric artifacts on errors, then let the original error propagate.
                memory_artifacts = memory.finish(
                    benchmark_error=f'{type(error).__name__}: {error}' if error else None)
                print(f'Memory artifacts written to {benchmark_file.parent}')
        finally:
            if previous_sigterm is not None:
                signal.signal(signal.SIGTERM, previous_sigterm)
            client.disconnect()

    if write_benchmark_results_enabled:
        assert benchmark_file is not None
        results = {
            "metadata": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "host": platform.node(),
                "compute_unit": cu_settings,
                "workers_per_cu": workers_per_cu,
                "scale_factor": scale_factor,
                "warmup_rounds": args.warmup_runs,
                "measured_rounds": args.runs,
                "cu_restarted_between_runs": False,
                "plan_source": args.f if args.f else args.plan_source,
                "query_order": [Path(query).name for query in query_list],
                "execution_mode": args.execution_mode,
                "optimization": benchmark_config.get("optimization", dict(DEFAULT_OPTIMIZATION)),
                "compilation": benchmark_config.get("compilation", {}),
                "variant": variant,
                "experiment": benchmark_config.get("experiment", {}),
                "config_file": args.config,
            },
            "rounds": round_results,
            "queries": benchmark_results,
        }
        if memory_artifacts is not None:
            # Link raw collection files only; plotting is an independent command.
            results['memory'] = memory_artifacts
        write_benchmark_results(benchmark_file, results)
        print(f"Benchmark results written to {benchmark_file}")

    if not all_succeeded:
        sys.exit(1)
    if memory_artifacts and memory_artifacts['errors']:
        raise RuntimeError(f'Memory collection failed: {memory_artifacts["errors"]}')

if __name__ == "__main__":
    main()
