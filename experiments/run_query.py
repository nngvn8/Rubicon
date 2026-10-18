import argparse
import json
import sys
import threading
import time
from datetime import datetime
from typing import List, Optional, Tuple, Dict
from pathlib import Path

from google.protobuf.json_format import MessageToDict

from utils import msg
from utils import client as tcp_client
from utils import util
from utils.unique_id import new_uint32_id

from proto import NetworkRequests_pb2 as NetworkRequests
from proto import WorkRequest_pb2 as WorkRequest
from proto import WorkResponse_pb2 as WorkResponse

from proto import ConfigurationRequests_pb2 as ConfigurationRequests
from proto import QueryPlan_pb2 as QueryPlan

from proto.UnitDefinition_pb2 import TcpPackageType, UnitType

from utils.queries import q_1_1, q_1_2, q_1_3, q_2_1, q_2_2, q_2_3, q_3_1, q_3_2, q_3_3, q_3_4, q_4_1, q_4_2, q_4_3

queries_dict = {"q_1_1": q_1_1, "q_1_2": q_1_2, "q_1_3": q_1_3, "q_2_1": q_2_1, "q_2_2": q_2_2, "q_2_3": q_2_3, "q_3_1": q_3_1, "q_3_2": q_3_2, "q_3_3": q_3_3, "q_3_4": q_3_4, "q_4_1": q_4_1, "q_4_2": q_4_2, "q_4_3": q_4_3}

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

        return complete_plans.get(plan_id, None)


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


def load_query_plan_from_pb(pb_file_path: str, src_uuid: int = 0, target_uuid: int = 0, extended_results: bool = False) -> msg.TCPMessage:
    # 1. Load the raw QueryPlan protobuf from disk
    qplan = QueryPlan.QueryPlan()
    with open(pb_file_path, "rb") as f:
        qplan.ParseFromString(f.read())

    for item in qplan.planitems:
        item.returnExtendedResult = extended_results

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

    return plan_response


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

# ----------------------------
# Main
# ----------------------------
def main():

    # Setup Parser
    parser = argparse.ArgumentParser()
    parser.add_argument("-ip", default="127.0.0.1")
    parser.add_argument("-port", default=23232)
    parser.add_argument("--scale-factor", default=2)
    parser.add_argument("--workers-per-cu", type=int, default=48)
    parser.add_argument("-info", default="Sequentially running a set of querries")
    parser.add_argument("-name", default="Sequentially running a set of querries client")
    parser.add_argument('-q', help='Which quer[ies] to run. If multiple queries are given, write as CSV.', default=False, required=False)
    parser.add_argument('-f', help='Folder to read queries from.', default='/home/mschmidt/rubi-test-2/Rubicon/data/plans')
    parser.add_argument("--out", default="results/run_query")    # Output



    args = parser.parse_args()

    # Setup Client
    client = tcp_client.TCPClient(unit_type=UnitType.QUERY_PLANER, unit_info=args.info, name=args.name)

    query_list = []
    if args.q:
        qs = args.q.split(",")
        query_list.extend([query.strip() for query in qs])
    elif args.f:
        path = Path(args.f)
        for filename in path.iterdir():
            if filename.suffix == ".pb":
                query_list.append(str(filename))
    else:
        query_list = queries_dict.keys()

    # Register callbacks (copied from concurrent query_execution_experiment.py - not sure if needed)
    client.register_callback(TcpPackageType.UUID_FOR_UNIT_RESPONSE, update_uuids)
    client.register_callback(TcpPackageType.SERVER_CONFIGURATION_RESPONSE, server_config_response_cb)
    client.register_callback(TcpPackageType.PLAN_RESPONSE, plan_finished_cb)

    client.connect(args.ip, args.port)

    # Extract relevant args
    workers_per_cu = args.workers_per_cu
    scale_factor = args.scale_factor
    out_dir_base = Path(args.out)

    # Run queries
    all_succeeded = True
    try:
        for query in query_list:
            target_out_dir = out_dir_base / (Path(query).name if args.f else query)
            target_out_dir.mkdir(parents=True, exist_ok=True)
            
            # Discover CU + set workers
            src_uuid, tgt_uuid = discover_compute_unit(client)
            set_workers_for_compute_units(client, workers_per_cu)
            time.sleep(1.0)
            
            # Generate TCP message
            if args.f:
                query_tcp_msg, query_plan = load_query_plan_from_pb(query, src_uuid=src_uuid, target_uuid=tgt_uuid, extended_results=True)
            else: 
                pid = new_uint32_id()
                q = queries_dict[query]
                query_tcp_msg, query_plan = q(planId=pid, src_uuid=src_uuid, target_uuid=tgt_uuid, scale_factor=scale_factor, extendedResult=True)
            
            # Run query
            plan_response = run_one_query(client=client, query_msg=query_tcp_msg)

            if plan_response is None or plan_response.info != PLAN_SUCCESS_INFO:
                all_succeeded = False

            if plan_response is not None:
                print(plan_response.info)
            else:
                print(f"Query {query} FAILED: no plan response received")

    finally:
        client.disconnect()

    if not all_succeeded:
        sys.exit(1)

if __name__ == "__main__":
    main()