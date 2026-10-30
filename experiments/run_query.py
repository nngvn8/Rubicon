import argparse
import json
import platform
import re
import statistics
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
WRITE_BENCHMARK_RESULTS = True
BENCHMARK_ROOT = Path(__file__).resolve().parent.parent / "benchmarking"
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
PLAN_SOURCES = {
    "plans": REPOSITORY_ROOT / "data" / "plans",
    "pb_plans": REPOSITORY_ROOT / "data" / "pb_plans",
}
DEFAULT_BENCHMARK_CONFIG = Path(__file__).resolve().parent / "configs" / "benchmark_example.yaml"

# Threading (or maybe also not) - not sure if needed
name_list: List[str] = []
uuid_list: List[int] = []

uuid_condition = threading.Condition()

complete_plans: Dict[int, WorkResponse.PlanResponse] = {}
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
    global complete_condition, complete_plans
    response: WorkResponse.PlanResponse = WorkResponse.PlanResponse()
    response.ParseFromString(message.payload)
    with complete_condition:
        complete_plans[response.planId] = response
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
        deadline = time.time() + timeout
        while plan_id not in complete_plans and client.connection_up:
            remaining = deadline - time.time()
            if remaining <= 0:
                print(f"[Warn] Timeout waiting for plan_id={plan_id}")
                return None
            complete_condition.wait(timeout=remaining)

        # Plan ids are unique for every execution. Remove the terminal response
        # once consumed so a long benchmark does not retain every prior result.
        return complete_plans.pop(plan_id, None)


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

def run_one_query(client: tcp_client.TCPClient, query_msg: msg.TCPMessage) -> Optional[WorkResponse.PlanResponse]:
    """Submit a plan and return its terminal response, if one arrives."""
    req = WorkRequest.WorkRequest()
    req.ParseFromString(query_msg.payload)
    plan_id = req.queryPlan.planid

    t_s = datetime.now()
    client.send_message(query_msg)
    plan_response = wait_next_completion(client, plan_id)
    t_e = datetime.now()
    total_response_time = (t_e - t_s).total_seconds()

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
        values = [sample[metric] for sample in samples if sample[metric] is not None]
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
    except (OSError, yaml.YAMLError) as error:
        raise ValueError(f"could not read config {path}: {error}") from error
    if not isinstance(config, dict):
        raise ValueError("benchmark config must contain a YAML mapping")
    for key in ("benchmark", "variant", "experiment"):
        if key in config and not isinstance(config[key], dict):
            raise ValueError(f"config field {key!r} must be a mapping")
    if "plan_source" in config and config["plan_source"] not in PLAN_SOURCES:
        raise ValueError(f"config plan_source must be one of: {', '.join(PLAN_SOURCES)}")
    if "variant" in config:
        config["variant"] = {
            str(key): normalize_variant_value(value)
            for key, value in config["variant"].items()
        }
    return config


def create_benchmark_file(
    workers: int, scale_factor: int, runs: int, variant: Dict[str, bool | int | float | str]
) -> Path:
    """Create a unique benchmark directory without using randomized plan ids."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    run_name = f"{timestamp}_workers-{workers}_sf-{scale_factor}_runs-{runs}"
    benchmark_dir = BENCHMARK_ROOT / variant_slug(variant) / run_name
    suffix = 1
    while benchmark_dir.exists():
        benchmark_dir = BENCHMARK_ROOT / variant_slug(variant) / f"{run_name}_{suffix}"
        suffix += 1
    benchmark_dir.mkdir(parents=True)
    return benchmark_dir / "results.json"


def write_benchmark_results(benchmark_file: Path, results: Dict) -> None:
    """Write one self-contained benchmark result file."""
    with benchmark_file.open("w", encoding="utf-8") as output_file:
        json.dump(results, output_file, indent=2, sort_keys=True)
        output_file.write("\n")

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
    parser.add_argument("-ip", default="127.0.0.1")
    parser.add_argument("-port", default=23233)
    parser.add_argument("--scale-factor", type=int, default=benchmark_defaults.get("scale_factor", 2))
    parser.add_argument("--workers-per-cu", type=int, default=benchmark_defaults.get("workers_per_cu", 48))
    parser.add_argument("-info", default="Sequentially running a set of querries")
    parser.add_argument("-name", default="Sequentially running a set of querries client")
    parser.add_argument('-q', help='Which quer[ies] to run. If multiple queries are given, write as CSV.', default=False, required=False)
    parser.add_argument('-f', help='Folder to read .pb queries from (overrides --plan-source).')
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
    parser.add_argument("--out", default="results/run_query")    # Output
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
        action="store_true",
        help="Write a timestamped benchmark result directory under benchmarking/.",
    )



    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    if args.warmup_runs < 0:
        parser.error("--warmup-runs must not be negative")
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
        if not path.is_dir():
            parser.error(f"plan folder does not exist: {path}")
        query_list = [str(path) for path in sorted(path.glob("*.pb"), key=natural_sort_key)]
    else:
        path = PLAN_SOURCES[args.plan_source]
        if not path.is_dir():
            parser.error(f"named plan source does not exist: {path}")
        query_list = [str(path) for path in sorted(path.glob("*.pb"), key=natural_sort_key)]

    # Register callbacks (copied from concurrent query_execution_experiment.py - not sure if needed)
    client.register_callback(TcpPackageType.UUID_FOR_UNIT_RESPONSE, update_uuids)
    client.register_callback(TcpPackageType.SERVER_CONFIGURATION_RESPONSE, server_config_response_cb)
    client.register_callback(TcpPackageType.PLAN_RESPONSE, plan_finished_cb)

    client.connect(args.ip, args.port)

    # Extract relevant args
    workers_per_cu = args.workers_per_cu
    scale_factor = args.scale_factor
    write_benchmark_results_enabled = WRITE_BENCHMARK_RESULTS or args.write_benchmark_results
    benchmark_results: Dict[str, Dict] = {}
    benchmark_file: Optional[Path] = None
    if write_benchmark_results_enabled:
        benchmark_file = create_benchmark_file(workers_per_cu, scale_factor, args.runs, variant)

    # Configure the ComputeUnit once. This keeps discovery and configuration
    # out of every measured execution.
    all_succeeded = True
    EXTENDED_RESULT = True
    RANDOM_PID = True
    try:
        src_uuid, tgt_uuid = discover_compute_unit(client)
        set_workers_for_compute_units(client, workers_per_cu)
        time.sleep(1.0)

        for query in query_list:
            benchmark_results[Path(query).name] = {"samples": [], "failures": []}

        total_rounds = args.warmup_runs + args.runs
        for round_number in range(1, total_rounds + 1):
            is_warmup = round_number <= args.warmup_runs
            measured_round = round_number - args.warmup_runs
            label = "warmup" if is_warmup else f"measured round {measured_round}/{args.runs}"
            print(f"\n=== {label} ===")

            # A round is a complete sequential pass over the selected batch.
            for query in query_list:
                print(query)
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

                plan_response, total_response_time = run_one_query(client=client, query_msg=query_tcp_msg)
                print(f"Total response time: {total_response_time} seconds")

                plan_duration_s = None
                operator_work_s = None
                if plan_response is not None and plan_response.extendedResults:
                    extended = plan_response.extendedResults
                    plan_duration_s = (max(item.end for item in extended) - min(item.start for item in extended)) / 1_000_000_000
                    operator_work_s = sum(item.end - item.start for item in extended) / 1_000_000_000
                    print(f"Plan duration: {plan_duration_s} seconds")
                    print(f"Operator work: {operator_work_s} seconds")

                succeeded = plan_response is not None and plan_response.info == PLAN_SUCCESS_INFO
                if not succeeded:
                    failure = "no plan response received" if plan_response is None else plan_response.info
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
                    })
                    print(plan_response.info)

        for result in benchmark_results.values():
            result["summary"] = summarize(result["samples"])

    finally:
        client.disconnect()

    if write_benchmark_results_enabled:
        assert benchmark_file is not None
        write_benchmark_results(benchmark_file, {
            "metadata": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "host": platform.node(),
                "workers_per_cu": workers_per_cu,
                "scale_factor": scale_factor,
                "warmup_rounds": args.warmup_runs,
                "measured_rounds": args.runs,
                "cu_restarted_between_runs": False,
                "plan_source": args.f if args.f else args.plan_source,
                "query_order": [Path(query).name for query in query_list],
                "variant": variant,
                "experiment": benchmark_config.get("experiment", {}),
                "config_file": args.config,
            },
            "queries": benchmark_results,
        })
        print(f"Benchmark results written to {benchmark_file}")

    if not all_succeeded:
        sys.exit(1)

if __name__ == "__main__":
    main()
