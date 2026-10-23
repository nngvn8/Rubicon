from utils import msg
from utils import util

from proto import WorkItem_pb2 as WorkItem

def q_1_1(planId: int = 1, src_uuid: int = 0, target_uuid: int = 0, scale_factor: int = 1, extendedResult: bool = False) -> msg.TCPMessage:
    name_prefix: str = f"{planId}_{q_1_1.__name__}"
    inter_tab_name:str = f"{planId}_inter"

    workItems = []
    workItems.append(util.create_work_item(itemType="int_filter",
        planId=planId, itemId=1, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="lineorder", inputColumn="lo_discount", inputType=WorkItem.TYPE_INTEGER, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_1", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_BETWEEN, filterArgVals=[1, 3]))

    workItems.append(util.create_work_item(itemType="int_filter",
        planId=planId, itemId=2, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="lineorder", inputColumn="lo_quantity", inputType=WorkItem.TYPE_INTEGER, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_2", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_LT, filterArgVals=[25]))

    workItems.append(util.create_work_item(itemType="int_filter",
        planId=planId, itemId=3, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="date", inputColumn="d_year", inputType=WorkItem.TYPE_INTEGER, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_3", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_EQ, filterArgVals=[1993]))

    workItems.append(util.create_work_item(itemType="set_operation",
        planId=planId, itemId=4, dependsOn=[1, 2], operatorId=WorkItem.OP_SETOPERATION,
        operation=WorkItem.REL_INTERSECTION, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_1", innerType=WorkItem.TYPE_POSLIST,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_2", outerType=WorkItem.TYPE_POSLIST,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_4", outputType=WorkItem.TYPE_POSLIST))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=5, dependsOn=[4], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_4", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_orderdate", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_5", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=6, dependsOn=[3], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_3", indexType=WorkItem.TYPE_POSLIST,
        filterTable="date", filterColumn="d_datekey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_6", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=7, dependsOn=[5, 6], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_6", innerType=WorkItem.TYPE_INTEGER,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_5", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_7", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=8, dependsOn=[4], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_4", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_extendedprice", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_8", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=9, dependsOn=[4], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_4", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_discount", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_9", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=10, dependsOn=[7, 8], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_7_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_8", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_10", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=11, dependsOn=[7, 9], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_7_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_9", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_11", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="map",
        planId=planId, itemId=12, dependsOn=[10, 11], operatorId=WorkItem.OP_MAP, operatorType=WorkItem.ARITH_MUL, extendedResult=extendedResult,
        inputTable=inter_tab_name, inputColumn=f"{name_prefix}_it_10", inputType=WorkItem.TYPE_POSLIST,
        partnerTable=inter_tab_name, partnerColumn=f"{name_prefix}_it_11", partnerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_12", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="aggregate",
        planId=planId, itemId=13, dependsOn=[12], operatorId=WorkItem.OP_AGGREGATE, aggregationFunction=WorkItem.AGG_SUM, extendedResult=extendedResult,
        inputTable=inter_tab_name, inputColumn=f"{name_prefix}_it_12", inputType=WorkItem.TYPE_POSLIST,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_13", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="result", 
        planId=planId, itemId=14, dependsOn=[13], operatorId=WorkItem.OP_RESULT, extendedResult=extendedResult,
        resultTables=[inter_tab_name], resultColumns=[f"{name_prefix}_it_13"], 
        resultHeader=["revenue"], resultName=f"sf{scale_factor}_{name_prefix}_result"))
    
    return util.create_query_plan(planId=planId, workItems=workItems, source_uuid=src_uuid, target_uuid=target_uuid)


def q_1_2(planId: int = 2, src_uuid: int = 0, target_uuid: int = 0, scale_factor: int = 1, extendedResult: bool = False) -> msg.TCPMessage:
    name_prefix: str = f"{planId}_{q_1_2.__name__}"
    inter_tab_name:str = f"{planId}_inter"

    workItems = []
    workItems.append(util.create_work_item(itemType="int_filter",
        planId=planId, itemId=1, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="lineorder", inputColumn="lo_discount", inputType=WorkItem.TYPE_INTEGER, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_1", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_BETWEEN, filterArgVals=[4, 6]))

    workItems.append(util.create_work_item(itemType="int_filter",
        planId=planId, itemId=2, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="lineorder", inputColumn="lo_quantity", inputType=WorkItem.TYPE_INTEGER, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_2", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_BETWEEN, filterArgVals=[26, 35]))

    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=3, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="date", inputColumn="d_yearmonth", inputType=WorkItem.TYPE_STRING, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_3", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_EQ, filterArgVals=["Jan1994"]))

    workItems.append(util.create_work_item(itemType="set_operation",
        planId=planId, itemId=4, dependsOn=[1, 2], operatorId=WorkItem.OP_SETOPERATION,
        operation=WorkItem.REL_INTERSECTION, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_1", innerType=WorkItem.TYPE_POSLIST,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_2", outerType=WorkItem.TYPE_POSLIST,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_4", outputType=WorkItem.TYPE_POSLIST))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=5, dependsOn=[4], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_4", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_orderdate", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_5", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=6, dependsOn=[3], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_3", indexType=WorkItem.TYPE_POSLIST,
        filterTable="date", filterColumn="d_datekey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_6", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=7, dependsOn=[5, 6], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_6", innerType=WorkItem.TYPE_INTEGER,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_5", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_7", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=8, dependsOn=[4], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_4", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_extendedprice", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_8", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=9, dependsOn=[4], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_4", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_discount", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_9", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=10, dependsOn=[7, 8], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_7_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_8", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_10", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=11, dependsOn=[7, 9], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_7_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_9", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_11", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="map",
        planId=planId, itemId=12, dependsOn=[10, 11], operatorId=WorkItem.OP_MAP, operatorType=WorkItem.ARITH_MUL, extendedResult=extendedResult,
        inputTable=inter_tab_name, inputColumn=f"{name_prefix}_it_10", inputType=WorkItem.TYPE_POSLIST,
        partnerTable=inter_tab_name, partnerColumn=f"{name_prefix}_it_11", partnerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_12", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="aggregate",
        planId=planId, itemId=13, dependsOn=[12], operatorId=WorkItem.OP_AGGREGATE, aggregationFunction=WorkItem.AGG_SUM, extendedResult=extendedResult,
        inputTable=inter_tab_name, inputColumn=f"{name_prefix}_it_12", inputType=WorkItem.TYPE_POSLIST,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_13", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="result",
        planId=planId, itemId=14, dependsOn=[13], operatorId=WorkItem.OP_RESULT, extendedResult=extendedResult,
        resultTables=[inter_tab_name], resultColumns=[f"{name_prefix}_it_13"], 
        resultHeader=["revenue"], resultName=f"sf{scale_factor}_{name_prefix}_result"))
    
    return util.create_query_plan(planId=planId, workItems=workItems, source_uuid=src_uuid, target_uuid=target_uuid)
    

def q_1_3(planId: int = 3, src_uuid: int = 0, target_uuid: int = 0, scale_factor: int = 1, extendedResult: bool = False) -> msg.TCPMessage:
    name_prefix: str = f"{planId}_{q_1_3.__name__}"
    inter_tab_name:str = f"{planId}_inter"

    workItems = []
    workItems.append(util.create_work_item(itemType="int_filter",
        planId=planId, itemId=1, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="date", inputColumn="d_weeknuminyear", inputType=WorkItem.TYPE_INTEGER, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_1", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_EQ, filterArgVals=[6]))

    workItems.append(util.create_work_item(itemType="int_filter",
        planId=planId, itemId=2, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="date", inputColumn="d_year", inputType=WorkItem.TYPE_STRING, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_2", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_EQ, filterArgVals=[1994]))

    workItems.append(util.create_work_item(itemType="int_filter",
        planId=planId, itemId=3, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="lineorder", inputColumn="lo_discount", inputType=WorkItem.TYPE_INTEGER, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_3", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_BETWEEN, filterArgVals=[5, 7]))

    workItems.append(util.create_work_item(itemType="int_filter",
        planId=planId, itemId=4, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="lineorder", inputColumn="lo_quantity", inputType=WorkItem.TYPE_INTEGER, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_4", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_BETWEEN, filterArgVals=[26, 35]))

    workItems.append(util.create_work_item(itemType="set_operation",
        planId=planId, itemId=5, dependsOn=[1, 2], operatorId=WorkItem.OP_SETOPERATION,
        operation=WorkItem.REL_INTERSECTION, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_1", innerType=WorkItem.TYPE_POSLIST,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_2", outerType=WorkItem.TYPE_POSLIST,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_5", outputType=WorkItem.TYPE_POSLIST))

    workItems.append(util.create_work_item(itemType="set_operation",
        planId=planId, itemId=6, dependsOn=[3, 4], operatorId=WorkItem.OP_SETOPERATION,
        operation=WorkItem.REL_INTERSECTION, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_3", innerType=WorkItem.TYPE_POSLIST,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_4", outerType=WorkItem.TYPE_POSLIST,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_6", outputType=WorkItem.TYPE_POSLIST))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=7, dependsOn=[5], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_5", indexType=WorkItem.TYPE_POSLIST,
        filterTable="date", filterColumn="d_datekey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_7", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=8, dependsOn=[6], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_6", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_orderdate", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_8", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=9, dependsOn=[7, 8], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_7", innerType=WorkItem.TYPE_INTEGER,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_8", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_9", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=10, dependsOn=[6], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_6", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_extendedprice", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_10", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=11, dependsOn=[6], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_6", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_discount", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_11", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=12, dependsOn=[9, 10], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_9_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_10", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_12", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=13, dependsOn=[9, 11], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_9_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_11", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_13", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="map",
        planId=planId, itemId=14, dependsOn=[12, 13], operatorId=WorkItem.OP_MAP, operatorType=WorkItem.ARITH_MUL, extendedResult=extendedResult,
        inputTable=inter_tab_name, inputColumn=f"{name_prefix}_it_12", inputType=WorkItem.TYPE_POSLIST,
        partnerTable=inter_tab_name, partnerColumn=f"{name_prefix}_it_13", partnerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_14", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="aggregate",
        planId=planId, itemId=15, dependsOn=[14], operatorId=WorkItem.OP_AGGREGATE, aggregationFunction=WorkItem.AGG_SUM, extendedResult=extendedResult,
        inputTable=inter_tab_name, inputColumn=f"{name_prefix}_it_14", inputType=WorkItem.TYPE_POSLIST,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_15", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="result",
        planId=planId, itemId=16, dependsOn=[15], operatorId=WorkItem.OP_RESULT, extendedResult=extendedResult,
        resultTables=[inter_tab_name], resultColumns=[f"{name_prefix}_it_15"], 
        resultHeader=["revenue"], resultName=f"sf{scale_factor}_{name_prefix}_result"))
    
    return util.create_query_plan(planId=planId, workItems=workItems, source_uuid=src_uuid, target_uuid=target_uuid)
    
    
def q_2_1(planId: int = 4, src_uuid: int = 0, target_uuid: int = 0, scale_factor: int = 1, extendedResult: bool = False) -> msg.TCPMessage:
    name_prefix: str = f"{planId}_{q_2_1.__name__}"
    inter_tab_name:str = f"{planId}_inter"   

    workItems = []
    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=1, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="part", inputColumn="p_category", inputType=WorkItem.TYPE_STRING, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_1", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_EQ, filterArgVals=["MFGR#12"]))
    
    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=2, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="supplier", inputColumn="s_region", inputType=WorkItem.TYPE_STRING, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_2", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_EQ, filterArgVals=["AMERICA"]))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=3, dependsOn=[1], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_1", indexType=WorkItem.TYPE_POSLIST,
        filterTable="part", filterColumn="p_partkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_3", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=4, dependsOn=[2], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_2", indexType=WorkItem.TYPE_POSLIST,
        filterTable="supplier", filterColumn="s_suppkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_4", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=5, dependsOn=[1], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_1", indexType=WorkItem.TYPE_POSLIST,
        filterTable="part", filterColumn="p_brand", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_5", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=6, dependsOn=[3], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_3", innerType=WorkItem.TYPE_INTEGER,
        outerTable="lineorder", outerColumn="lo_partkey", outerType=WorkItem.TYPE_INTEGER, outerIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_6", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=7, dependsOn=[6], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_6_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_suppkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_7", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=90, dependsOn=[6], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_6_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_orderdate", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_7_ord", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=70, dependsOn=[6], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_6_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_revenue", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_7_rev", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=12, dependsOn=[5, 6], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_6_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_5", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_12", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=8, dependsOn=[4, 7], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_4", innerType=WorkItem.TYPE_INTEGER,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_7", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_8", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=9, dependsOn=[8, 90], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_8_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_7_ord", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_9", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=91, dependsOn=[70, 8], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_8_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_7_rev", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_9_rev", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=13, dependsOn=[8, 12], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_8_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_12", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_13", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=10, dependsOn=[9], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable="date", innerColumn="d_datekey", innerType=WorkItem.TYPE_INTEGER, innerIsBase=True,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_9", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_10", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=11, dependsOn=[10], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="date", filterColumn="d_year", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_11", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=14, dependsOn=[10, 91], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_9_rev", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_14", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=15, dependsOn=[10, 13], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_13", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_15", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="multigroup",
        planId=planId, itemId=16, dependsOn=[11, 14, 15], operatorId = WorkItem.OP_GROUPBY, extendedResult=extendedResult,
        tables=[inter_tab_name, inter_tab_name], 
        columns=[f"{name_prefix}_it_11", f"{name_prefix}_it_15"], 
        columntypes=[WorkItem.TYPE_INTEGER,WorkItem.TYPE_INTEGER],
        outputIndexTable=inter_tab_name, outputIndexColumn=f"{name_prefix}_it_16_idx", 
        outputClustersTable=inter_tab_name, outputClustersColumn=f"{name_prefix}_it_16_cluster",
        aggregationTable=inter_tab_name, aggregationColumn=f"{name_prefix}_it_14", agregationColumnType=WorkItem.TYPE_INTEGER,
        aggregationResultTable=inter_tab_name, aggregationResultColumn=f"{name_prefix}_it_16", agregationResultColumnType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=30, dependsOn=[11, 16], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_16_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_11", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_d_year", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=31, dependsOn=[15, 16], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_16_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_15", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_p_brand", outputType=WorkItem.TYPE_INTEGER))
        
    workItems.append(util.create_work_item(itemType="sort",
        planId=planId, itemId=18, dependsOn=[31], operatorId=WorkItem.OP_SORT, extendedResult=extendedResult,
        inputTables=[inter_tab_name], 
        inputColumns=[f"{name_prefix}_it_p_brand"],
        indexOutputTable=inter_tab_name, indexOutputColumn=f"{name_prefix}_final_idx",
        sortOrder=[True]))

    workItems.append(util.create_work_item(itemType="result",
        planId=planId, itemId=19, dependsOn=[16, 18, 30, 31], operatorId=WorkItem.OP_RESULT, extendedResult=extendedResult,
        resultTables=[inter_tab_name,inter_tab_name,inter_tab_name], 
        resultColumns=[f"{name_prefix}_it_16",f"{name_prefix}_d_year",f"{name_prefix}_it_p_brand"],
        resultHeader=["sum(lo_revenue)","d_year","p_brand"],
        resultIndexTable=inter_tab_name, resultIndexColumn=f"{name_prefix}_final_idx",
        resultName=f"sf{scale_factor}_{name_prefix}_result"))
    
    return util.create_query_plan(planId=planId, workItems=workItems, source_uuid=src_uuid, target_uuid=target_uuid)
    
    
def q_2_2(planId: int = 5, src_uuid: int = 0, target_uuid: int = 0, scale_factor: int = 1, extendedResult: bool = False) -> msg.TCPMessage:
    name_prefix: str = f"{planId}_{q_2_2.__name__}"
    inter_tab_name:str = f"{planId}_inter"

    workItems = []
    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=1, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="part", inputColumn="p_brand", inputType=WorkItem.TYPE_STRING, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_1", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_BETWEEN, filterArgVals=["MFGR#2221", "MFGR#2228"]))
    
    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=2, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="supplier", inputColumn="s_region", inputType=WorkItem.TYPE_STRING, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_2", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_EQ, filterArgVals=["ASIA"]))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=3, dependsOn=[1], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_1", indexType=WorkItem.TYPE_POSLIST,
        filterTable="part", filterColumn="p_partkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_3", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=4, dependsOn=[2], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_2", indexType=WorkItem.TYPE_POSLIST,
        filterTable="supplier", filterColumn="s_suppkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_4", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=5, dependsOn=[1], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_1", indexType=WorkItem.TYPE_POSLIST,
        filterTable="part", filterColumn="p_brand", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_5", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=6, dependsOn=[3], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_3", innerType=WorkItem.TYPE_INTEGER,
        outerTable="lineorder", outerColumn="lo_partkey", outerType=WorkItem.TYPE_INTEGER, outerIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_6", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=7, dependsOn=[6], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_6_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_suppkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_7", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=90, dependsOn=[6], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_6_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_orderdate", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_7_ord", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=70, dependsOn=[6], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_6_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_revenue", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_7_rev", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=12, dependsOn=[5, 6], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_6_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_5", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_12", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=8, dependsOn=[4, 7], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_4", innerType=WorkItem.TYPE_INTEGER,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_7", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_8", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=9, dependsOn=[8, 90], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_8_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_7_ord", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_9", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=91, dependsOn=[70, 8], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_8_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_7_rev", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_9_rev", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=13, dependsOn=[8, 12], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_8_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_12", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_13", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=10, dependsOn=[9], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable="date", innerColumn="d_datekey", innerType=WorkItem.TYPE_INTEGER, innerIsBase=True,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_9", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_10", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=11, dependsOn=[10], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="date", filterColumn="d_year", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_11", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=14, dependsOn=[10, 91], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_9_rev", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_14", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=15, dependsOn=[10, 13], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_13", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_15", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="multigroup",
        planId=planId, itemId=16, dependsOn=[11, 14, 15], operatorId = WorkItem.OP_GROUPBY, extendedResult=extendedResult,
        tables=[inter_tab_name, inter_tab_name], 
        columns=[f"{name_prefix}_it_11", f"{name_prefix}_it_15"], 
        columntypes=[WorkItem.TYPE_INTEGER,WorkItem.TYPE_INTEGER],
        outputIndexTable=inter_tab_name, outputIndexColumn=f"{name_prefix}_it_16_idx", 
        outputClustersTable=inter_tab_name, outputClustersColumn=f"{name_prefix}_it_16_cluster",
        aggregationTable=inter_tab_name, aggregationColumn=f"{name_prefix}_it_14", agregationColumnType=WorkItem.TYPE_INTEGER,
        aggregationResultTable=inter_tab_name, aggregationResultColumn=f"{name_prefix}_it_16", agregationResultColumnType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=17, dependsOn=[11, 16], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_16_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_11", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_17", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=18, dependsOn=[15, 16], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_16_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_15", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_18", outputType=WorkItem.TYPE_INTEGER))
        

    workItems.append(util.create_work_item(itemType="result",
        planId=planId, itemId=19, dependsOn=[16, 17, 18], operatorId=WorkItem.OP_RESULT, extendedResult=extendedResult,
        resultTables=[inter_tab_name,inter_tab_name,inter_tab_name], 
        resultColumns=[f"{name_prefix}_it_16",f"{name_prefix}_it_17",f"{name_prefix}_it_18"],
        resultHeader=["sum(lo_revenue)","d_year","p_brand"],
        resultName=f"sf{scale_factor}_{name_prefix}_result"))
    
    return util.create_query_plan(planId=planId, workItems=workItems, source_uuid=src_uuid, target_uuid=target_uuid)

    
def q_2_3(planId: int = 6, src_uuid: int = 0, target_uuid: int = 0, scale_factor: int = 1, extendedResult: bool = False) -> msg.TCPMessage:
    name_prefix: str = f"{planId}_{q_2_3.__name__}"
    inter_tab_name:str = f"{planId}_inter"

    workItems = []
    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=1, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="part", inputColumn="p_brand", inputType=WorkItem.TYPE_STRING, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_1", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_EQ, filterArgVals=["MFGR#2239"]))
    
    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=2, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="supplier", inputColumn="s_region", inputType=WorkItem.TYPE_STRING, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_2", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_EQ, filterArgVals=["EUROPE"]))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=3, dependsOn=[1], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_1", indexType=WorkItem.TYPE_POSLIST,
        filterTable="part", filterColumn="p_brand", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_3", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=4, dependsOn=[1], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_1", indexType=WorkItem.TYPE_POSLIST,
        filterTable="part", filterColumn="p_partkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_4", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=5, dependsOn=[2], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_2", indexType=WorkItem.TYPE_POSLIST,
        filterTable="supplier", filterColumn="s_suppkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_5", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=6, dependsOn=[5], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_5", innerType=WorkItem.TYPE_INTEGER,
        outerTable="lineorder", outerColumn="lo_suppkey", outerType=WorkItem.TYPE_INTEGER, outerIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_6", outputType=WorkItem.TYPE_INTEGER))  

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=7, dependsOn=[6], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_6_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_partkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_7", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=8, dependsOn=[6], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_6_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_revenue", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_8", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=9, dependsOn=[6], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_6_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_orderdate", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_9", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=10, dependsOn=[4, 7], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_4", innerType=WorkItem.TYPE_INTEGER,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_7", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_10", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=11, dependsOn=[10, 3], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_3", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_11", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=12, dependsOn=[10, 8], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_8", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_12", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=13, dependsOn=[10, 9], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_9", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_13", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=14, dependsOn=[13], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable="date", innerColumn="d_datekey", innerType=WorkItem.TYPE_INTEGER, innerIsBase=True,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_13", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_14", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=15, dependsOn=[14], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_14_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="date", filterColumn="d_year", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_15", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=16, dependsOn=[14, 12], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_14_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_12", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_16", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=17, dependsOn=[14, 11], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_14_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_11", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_17", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="multigroup",
        planId=planId, itemId=18, dependsOn=[15, 17, 16], operatorId = WorkItem.OP_GROUPBY, extendedResult=extendedResult,
        tables=[inter_tab_name, inter_tab_name], 
        columns=[f"{name_prefix}_it_15", f"{name_prefix}_it_17"], 
        columntypes=[WorkItem.TYPE_INTEGER,WorkItem.TYPE_INTEGER,WorkItem.TYPE_INTEGER],
        outputIndexTable=inter_tab_name, outputIndexColumn=f"{name_prefix}_it_18_idx", 
        outputClustersTable=inter_tab_name, outputClustersColumn=f"{name_prefix}_it_18_cluster",
        aggregationTable=inter_tab_name, aggregationColumn=f"{name_prefix}_it_16", agregationColumnType=WorkItem.TYPE_INTEGER,
        aggregationResultTable=inter_tab_name, aggregationResultColumn=f"{name_prefix}_it_18", agregationResultColumnType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=19, dependsOn=[18, 17], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_18_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_17", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_19", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=20, dependsOn=[18, 15], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_18_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_15", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_20", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="result",
        planId=planId, itemId=21, dependsOn=[18, 19, 20], operatorId=WorkItem.OP_RESULT, extendedResult=extendedResult,
        resultTables=[inter_tab_name,inter_tab_name,inter_tab_name], 
        resultColumns=[f"{name_prefix}_it_18",f"{name_prefix}_it_20",f"{name_prefix}_it_19"],
        resultHeader=["sum(lo_revenue)","d_year","p_brand"],
        resultName=f"sf{scale_factor}_{name_prefix}_result"))
    
    return util.create_query_plan(planId=planId, workItems=workItems, source_uuid=src_uuid, target_uuid=target_uuid)


def q_3_1(planId: int = 7, src_uuid: int = 0, target_uuid: int = 0, scale_factor: int = 1, extendedResult: bool = False) -> msg.TCPMessage:
    name_prefix: str = f"{planId}_{q_3_1.__name__}"
    inter_tab_name:str = f"{planId}_inter"

    workItems = []
    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=1, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="customer", inputColumn="c_region", inputType=WorkItem.TYPE_STRING, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_1", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_EQ, filterArgVals=["ASIA"]))
    
    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=2, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="supplier", inputColumn="s_region", inputType=WorkItem.TYPE_STRING, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_2", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_EQ, filterArgVals=["ASIA"]))
    
    workItems.append(util.create_work_item(itemType="int_filter",
        planId=planId, itemId=3, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="date", inputColumn="d_year", inputType=WorkItem.TYPE_INTEGER, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_3", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_BETWEEN, filterArgVals=[1992, 1997]))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=4, dependsOn=[1], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_1", indexType=WorkItem.TYPE_POSLIST,
        filterTable="customer", filterColumn="c_custkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_4", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=5, dependsOn=[1], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_1", indexType=WorkItem.TYPE_POSLIST,
        filterTable="customer", filterColumn="c_nation", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_5", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=6, dependsOn=[2], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_2", indexType=WorkItem.TYPE_POSLIST,
        filterTable="supplier", filterColumn="s_suppkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_6", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=7, dependsOn=[2], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_2", indexType=WorkItem.TYPE_POSLIST,
        filterTable="supplier", filterColumn="s_nation", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_7", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=8, dependsOn=[3], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_3", indexType=WorkItem.TYPE_POSLIST,
        filterTable="date", filterColumn="d_datekey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_8", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=9, dependsOn=[3], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_3", indexType=WorkItem.TYPE_POSLIST,
        filterTable="date", filterColumn="d_year", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_9", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=10, dependsOn=[4], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_4", innerType=WorkItem.TYPE_INTEGER,
        outerTable="lineorder", outerColumn="lo_custkey", outerType=WorkItem.TYPE_INTEGER, outerIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_10", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=11, dependsOn=[10], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_suppkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_11", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=12, dependsOn=[10], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_orderdate", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_12", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=13, dependsOn=[10], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_revenue", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_13", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=50, dependsOn=[10, 5], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_5", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_50", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=14, dependsOn=[6, 11], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_6", innerType=WorkItem.TYPE_INTEGER,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_11", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_14", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=15, dependsOn=[14, 12], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_14_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_12", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_15", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=16, dependsOn=[14, 13], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_14_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_13", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_16", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=17, dependsOn=[14, 7], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_14_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_7", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_17", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=18, dependsOn=[14, 50], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_14_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_50", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_18", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=19, dependsOn=[8, 15], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_8", innerType=WorkItem.TYPE_INTEGER,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_15", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_19", outputType=WorkItem.TYPE_INTEGER))   
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=20, dependsOn=[19, 16], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_19_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_16", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_20", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=21, dependsOn=[19, 9], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_19_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_9", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_21", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=22, dependsOn=[19, 18], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_19_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_18", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_22", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=23, dependsOn=[19, 17], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_19_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_17", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_23", outputType=WorkItem.TYPE_INTEGER))
 
    workItems.append(util.create_work_item(itemType="multigroup",
        planId=planId, itemId=24, dependsOn=[22, 23, 21, 20], operatorId = WorkItem.OP_GROUPBY, extendedResult=extendedResult,
        tables=[inter_tab_name, inter_tab_name,inter_tab_name], 
        columns=[f"{name_prefix}_it_22", f"{name_prefix}_it_23",f"{name_prefix}_it_21"], 
        columntypes=[WorkItem.TYPE_INTEGER,WorkItem.TYPE_INTEGER,WorkItem.TYPE_INTEGER],
        outputIndexTable=inter_tab_name, outputIndexColumn=f"{name_prefix}_it_24_idx", 
        outputClustersTable=inter_tab_name, outputClustersColumn=f"{name_prefix}_it_24_cluster",
        aggregationTable=inter_tab_name, aggregationColumn=f"{name_prefix}_it_20", agregationColumnType=WorkItem.TYPE_INTEGER,
        aggregationResultTable=inter_tab_name, aggregationResultColumn=f"{name_prefix}_it_24", agregationResultColumnType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=26, dependsOn=[21, 24], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_24_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_21", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_26", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=27, dependsOn=[22, 24], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_24_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_22", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_27", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=28, dependsOn=[23, 24], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_24_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_23", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_28", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="sort",
        planId=planId, itemId=29, dependsOn=[26, 24], operatorId=WorkItem.OP_SORT, extendedResult=extendedResult,
        inputTables=[inter_tab_name,inter_tab_name], 
        inputColumns=[f"{name_prefix}_it_26",f"{name_prefix}_it_24"],
        indexOutputTable=inter_tab_name, indexOutputColumn=f"{name_prefix}_it_29",
        sortOrder=[True,False]))

    workItems.append(util.create_work_item(itemType="result",
        planId=planId, itemId=30, dependsOn=[24, 26, 27, 28, 29], operatorId=WorkItem.OP_RESULT, extendedResult=extendedResult,
        resultTables=[inter_tab_name,inter_tab_name,inter_tab_name,inter_tab_name], 
        resultColumns=[f"{name_prefix}_it_27",f"{name_prefix}_it_28",f"{name_prefix}_it_26",f"{name_prefix}_it_24"],
        resultHeader=["c_nation","s_nation","d_year","revenue"],
        resultIndexTable=inter_tab_name, resultIndexColumn=f"{name_prefix}_it_29",
        resultName=f"sf{scale_factor}_{name_prefix}_result"))
    
    return util.create_query_plan(planId=planId, workItems=workItems, source_uuid=src_uuid, target_uuid=target_uuid)


def q_3_2(planId: int = 8, src_uuid: int = 0, target_uuid: int = 0, scale_factor: int = 1, extendedResult: bool = False) -> msg.TCPMessage:
    name_prefix: str = f"{planId}_{q_3_2.__name__}"
    inter_tab_name:str = f"{planId}_inter"

    workItems = []
    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=1, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="customer", inputColumn="c_nation", inputType=WorkItem.TYPE_STRING, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_1", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_EQ, filterArgVals=["UNITED STATES"]))
    
    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=2, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="supplier", inputColumn="s_nation", inputType=WorkItem.TYPE_STRING, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_2", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_EQ, filterArgVals=["UNITED STATES"]))
    
    workItems.append(util.create_work_item(itemType="int_filter",
        planId=planId, itemId=3, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="date", inputColumn="d_year", inputType=WorkItem.TYPE_INTEGER, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_3", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_BETWEEN, filterArgVals=[1992, 1997]))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=4, dependsOn=[1], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_1", indexType=WorkItem.TYPE_POSLIST,
        filterTable="customer", filterColumn="c_custkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_4", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=5, dependsOn=[1], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_1", indexType=WorkItem.TYPE_POSLIST,
        filterTable="customer", filterColumn="c_city", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_5", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=6, dependsOn=[2], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_2", indexType=WorkItem.TYPE_POSLIST,
        filterTable="supplier", filterColumn="s_suppkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_6", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=7, dependsOn=[2], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_2", indexType=WorkItem.TYPE_POSLIST,
        filterTable="supplier", filterColumn="s_city", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_7", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=8, dependsOn=[3], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_3", indexType=WorkItem.TYPE_POSLIST,
        filterTable="date", filterColumn="d_datekey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_8", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=9, dependsOn=[3], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_3", indexType=WorkItem.TYPE_POSLIST,
        filterTable="date", filterColumn="d_year", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_9", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=10, dependsOn=[4], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_4", innerType=WorkItem.TYPE_INTEGER,
        outerTable="lineorder", outerColumn="lo_custkey", outerType=WorkItem.TYPE_INTEGER, outerIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_10", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=11, dependsOn=[10], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_suppkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_11", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=12, dependsOn=[10], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_orderdate", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_12", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=13, dependsOn=[10], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_revenue", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_13", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=50, dependsOn=[10, 5], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_5", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_50", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=14, dependsOn=[6, 11], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_6", innerType=WorkItem.TYPE_INTEGER,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_11", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_14", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=15, dependsOn=[14, 12], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_14_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_12", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_15", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=16, dependsOn=[14, 13], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_14_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_13", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_16", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=17, dependsOn=[14, 7], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_14_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_7", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_17", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=18, dependsOn=[14, 50], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_14_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_50", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_18", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=19, dependsOn=[8, 15], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_8", innerType=WorkItem.TYPE_INTEGER,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_15", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_19", outputType=WorkItem.TYPE_INTEGER)) 
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=20, dependsOn=[19, 16], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_19_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_16", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_20", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=21, dependsOn=[19, 9], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_19_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_9", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_21", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=22, dependsOn=[19, 18], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_19_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_18", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_22", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=23, dependsOn=[19, 17], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_19_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_17", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_23", outputType=WorkItem.TYPE_INTEGER))
        
    workItems.append(util.create_work_item(itemType="multigroup",
        planId=planId, itemId=24, dependsOn=[20, 21, 22, 23], operatorId = WorkItem.OP_GROUPBY, extendedResult=extendedResult,
        tables=[inter_tab_name, inter_tab_name,inter_tab_name], 
        columns=[f"{name_prefix}_it_22", f"{name_prefix}_it_23",f"{name_prefix}_it_21"], 
        columntypes=[WorkItem.TYPE_INTEGER,WorkItem.TYPE_INTEGER,WorkItem.TYPE_INTEGER],
        outputIndexTable=inter_tab_name, outputIndexColumn=f"{name_prefix}_it_24_idx", 
        outputClustersTable=inter_tab_name, outputClustersColumn=f"{name_prefix}_it_24_cluster",
        aggregationTable=inter_tab_name, aggregationColumn=f"{name_prefix}_it_20", agregationColumnType=WorkItem.TYPE_INTEGER,
        aggregationResultTable=inter_tab_name, aggregationResultColumn=f"{name_prefix}_it_24", agregationResultColumnType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=26, dependsOn=[21, 24], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_24_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_21", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_26", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=27, dependsOn=[22, 24], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_24_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_22", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_27", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=28, dependsOn=[23, 24], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_24_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_23", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_28", outputType=WorkItem.TYPE_INTEGER))
      
    workItems.append(util.create_work_item(itemType="sort",
        planId=planId, itemId=29, dependsOn=[24, 26], operatorId=WorkItem.OP_SORT, extendedResult=extendedResult,
        inputTables=[inter_tab_name,inter_tab_name], 
        inputColumns=[f"{name_prefix}_it_26",f"{name_prefix}_it_24"],
        indexOutputTable=inter_tab_name, indexOutputColumn=f"{name_prefix}_it_29",
        sortOrder=[True,False]))

    workItems.append(util.create_work_item(itemType="result",
        planId=planId, itemId=30, dependsOn=[24, 26, 27, 28, 29], operatorId=WorkItem.OP_RESULT, extendedResult=extendedResult,
        resultTables=[inter_tab_name,inter_tab_name,inter_tab_name,inter_tab_name], 
        resultColumns=[f"{name_prefix}_it_27",f"{name_prefix}_it_28",f"{name_prefix}_it_26",f"{name_prefix}_it_24"],
        resultHeader=["c_city","s_city","d_year","revenue"],
        resultIndexTable=inter_tab_name, resultIndexColumn=f"{name_prefix}_it_29",
        resultName=f"sf{scale_factor}_{name_prefix}_result"))
    
    return util.create_query_plan(planId=planId, workItems=workItems, source_uuid=src_uuid, target_uuid=target_uuid)


def q_3_3(planId: int = 9, src_uuid: int = 0, target_uuid: int = 0, scale_factor: int = 1, extendedResult: bool = False) -> msg.TCPMessage:
    name_prefix: str = f"{planId}_{q_3_3.__name__}"
    inter_tab_name:str = f"{planId}_inter"

    workItems = []
    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=1, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="customer", inputColumn="c_city", inputType=WorkItem.TYPE_STRING, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_1", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_IN, filterArgVals=["UNITED KI1", "UNITED KI5"]))
    
    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=2, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="supplier", inputColumn="s_city", inputType=WorkItem.TYPE_STRING, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_2", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_IN, filterArgVals=["UNITED KI1", "UNITED KI5"]))
    
    workItems.append(util.create_work_item(itemType="int_filter",
        planId=planId, itemId=3, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="date", inputColumn="d_year", inputType=WorkItem.TYPE_INTEGER, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_3", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_BETWEEN, filterArgVals=[1992, 1997]))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=4, dependsOn=[1], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_1", indexType=WorkItem.TYPE_POSLIST,
        filterTable="customer", filterColumn="c_custkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_4", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=5, dependsOn=[1], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_1", indexType=WorkItem.TYPE_POSLIST,
        filterTable="customer", filterColumn="c_city", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_5", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=6, dependsOn=[2], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_2", indexType=WorkItem.TYPE_POSLIST,
        filterTable="supplier", filterColumn="s_suppkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_6", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=7, dependsOn=[2], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_2", indexType=WorkItem.TYPE_POSLIST,
        filterTable="supplier", filterColumn="s_city", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_7", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=8, dependsOn=[3], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_3", indexType=WorkItem.TYPE_POSLIST,
        filterTable="date", filterColumn="d_datekey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_8", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=9, dependsOn=[3], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_3", indexType=WorkItem.TYPE_POSLIST,
        filterTable="date", filterColumn="d_year", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_9", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=10, dependsOn=[4], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_4", innerType=WorkItem.TYPE_INTEGER,
        outerTable="lineorder", outerColumn="lo_custkey", outerType=WorkItem.TYPE_INTEGER, outerIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_10", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=11, dependsOn=[10], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_suppkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_11", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=12, dependsOn=[10], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_orderdate", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_12", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=13, dependsOn=[10], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_revenue", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_13", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=50, dependsOn=[10, 5], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_5", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_50", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=14, dependsOn=[6, 11], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_6", innerType=WorkItem.TYPE_INTEGER,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_11", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_14", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=15, dependsOn=[14, 12], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_14_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_12", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_15", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=16, dependsOn=[14, 13], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_14_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_13", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_16", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=17, dependsOn=[14, 7], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_14_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_7", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_17", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=18, dependsOn=[14, 50], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_14_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_50", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_18", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=19, dependsOn=[8, 15], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_8", innerType=WorkItem.TYPE_INTEGER,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_15", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_19", outputType=WorkItem.TYPE_INTEGER)) 
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=20, dependsOn=[19, 16], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_19_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_16", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_20", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=21, dependsOn=[19, 9], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_19_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_9", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_21", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=22, dependsOn=[19, 18], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_19_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_18", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_22", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=23, dependsOn=[19, 17], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_19_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_17", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_23", outputType=WorkItem.TYPE_INTEGER))
        
    workItems.append(util.create_work_item(itemType="multigroup",
        planId=planId, itemId=24, dependsOn=[20, 21, 22, 23], operatorId = WorkItem.OP_GROUPBY, extendedResult=extendedResult,
        tables=[inter_tab_name, inter_tab_name,inter_tab_name], 
        columns=[f"{name_prefix}_it_22", f"{name_prefix}_it_23",f"{name_prefix}_it_21"], 
        columntypes=[WorkItem.TYPE_INTEGER,WorkItem.TYPE_INTEGER,WorkItem.TYPE_INTEGER],
        outputIndexTable=inter_tab_name, outputIndexColumn=f"{name_prefix}_it_24_idx", 
        outputClustersTable=inter_tab_name, outputClustersColumn=f"{name_prefix}_it_24_cluster",
        aggregationTable=inter_tab_name, aggregationColumn=f"{name_prefix}_it_20", agregationColumnType=WorkItem.TYPE_INTEGER,
        aggregationResultTable=inter_tab_name, aggregationResultColumn=f"{name_prefix}_it_24", agregationResultColumnType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=26, dependsOn=[21, 24], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_24_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_21", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_26", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=27, dependsOn=[22, 24], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_24_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_22", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_27", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=28, dependsOn=[23, 24], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_24_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_23", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_28", outputType=WorkItem.TYPE_INTEGER))
      
    workItems.append(util.create_work_item(itemType="sort",
        planId=planId, itemId=29, dependsOn=[24, 26], operatorId=WorkItem.OP_SORT, extendedResult=extendedResult,
        inputTables=[inter_tab_name,inter_tab_name], 
        inputColumns=[f"{name_prefix}_it_26",f"{name_prefix}_it_24"],
        indexOutputTable=inter_tab_name, indexOutputColumn=f"{name_prefix}_it_29",
        sortOrder=[True,False]))

    workItems.append(util.create_work_item(itemType="result",
        planId=planId, itemId=30, dependsOn=[24, 26, 27, 28, 29], operatorId=WorkItem.OP_RESULT, extendedResult=extendedResult,
        resultTables=[inter_tab_name,inter_tab_name,inter_tab_name,inter_tab_name], 
        resultColumns=[f"{name_prefix}_it_27",f"{name_prefix}_it_28",f"{name_prefix}_it_26",f"{name_prefix}_it_24"],
        resultHeader=["c_city","s_city","d_year","revenue"],
        resultIndexTable=inter_tab_name, resultIndexColumn=f"{name_prefix}_it_29",
        resultName=f"sf{scale_factor}_{name_prefix}_result"))
    
    return util.create_query_plan(planId=planId, workItems=workItems, source_uuid=src_uuid, target_uuid=target_uuid)


def q_3_4(planId: int = 10, src_uuid: int = 0, target_uuid: int = 0, scale_factor: int = 1, extendedResult: bool = False) -> msg.TCPMessage:
    name_prefix: str = f"{planId}_{q_3_4.__name__}"
    inter_tab_name:str = f"{planId}_inter"

    workItems = []
    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=1, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="customer", inputColumn="c_city", inputType=WorkItem.TYPE_STRING, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_1", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_IN, filterArgVals=["UNITED KI1", "UNITED KI5"]))
    
    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=2, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="supplier", inputColumn="s_city", inputType=WorkItem.TYPE_STRING, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_2", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_IN, filterArgVals=["UNITED KI1", "UNITED KI5"]))
    
    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=3, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="date", inputColumn="d_yearmonth", inputType=WorkItem.TYPE_INTEGER, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_3", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_EQ, filterArgVals=["Dec1997"]))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=4, dependsOn=[1], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_1", indexType=WorkItem.TYPE_POSLIST,
        filterTable="customer", filterColumn="c_custkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_4", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=5, dependsOn=[1], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_1", indexType=WorkItem.TYPE_POSLIST,
        filterTable="customer", filterColumn="c_city", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_5", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=6, dependsOn=[2], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_2", indexType=WorkItem.TYPE_POSLIST,
        filterTable="supplier", filterColumn="s_suppkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_6", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=7, dependsOn=[2], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_2", indexType=WorkItem.TYPE_POSLIST,
        filterTable="supplier", filterColumn="s_city", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_7", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=8, dependsOn=[3], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_3", indexType=WorkItem.TYPE_POSLIST,
        filterTable="date", filterColumn="d_datekey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_8", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=9, dependsOn=[3], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_3", indexType=WorkItem.TYPE_POSLIST,
        filterTable="date", filterColumn="d_year", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_9", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=10, dependsOn=[4], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_4", innerType=WorkItem.TYPE_INTEGER,
        outerTable="lineorder", outerColumn="lo_custkey", outerType=WorkItem.TYPE_INTEGER, outerIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_10", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=11, dependsOn=[10], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_suppkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_11", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=12, dependsOn=[10], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_orderdate", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_12", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=13, dependsOn=[10], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_revenue", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_13", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=50, dependsOn=[10, 5], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_5", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_50", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=14, dependsOn=[6, 11], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_6", innerType=WorkItem.TYPE_INTEGER,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_11", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_14", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=15, dependsOn=[14, 12], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_14_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_12", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_15", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=16, dependsOn=[14, 13], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_14_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_13", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_16", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=17, dependsOn=[14, 7], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_14_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_7", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_17", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=18, dependsOn=[14, 50], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_14_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_50", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_18", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=19, dependsOn=[8, 15], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_8", innerType=WorkItem.TYPE_INTEGER,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_15", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_19", outputType=WorkItem.TYPE_INTEGER)) 
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=20, dependsOn=[19, 16], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_19_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_16", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_20", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=21, dependsOn=[19, 9], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_19_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_9", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_21", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=22, dependsOn=[19, 18], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_19_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_18", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_22", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=23, dependsOn=[19, 17], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_19_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_17", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_23", outputType=WorkItem.TYPE_INTEGER))
        
    workItems.append(util.create_work_item(itemType="multigroup",
        planId=planId, itemId=24, dependsOn=[20, 21, 22, 23], operatorId = WorkItem.OP_GROUPBY, extendedResult=extendedResult,
        tables=[inter_tab_name, inter_tab_name,inter_tab_name], 
        columns=[f"{name_prefix}_it_22", f"{name_prefix}_it_23",f"{name_prefix}_it_21"], 
        columntypes=[WorkItem.TYPE_INTEGER,WorkItem.TYPE_INTEGER,WorkItem.TYPE_INTEGER],
        outputIndexTable=inter_tab_name, outputIndexColumn=f"{name_prefix}_it_24_idx", 
        outputClustersTable=inter_tab_name, outputClustersColumn=f"{name_prefix}_it_24_cluster",
        aggregationTable=inter_tab_name, aggregationColumn=f"{name_prefix}_it_20", agregationColumnType=WorkItem.TYPE_INTEGER,
        aggregationResultTable=inter_tab_name, aggregationResultColumn=f"{name_prefix}_it_24", agregationResultColumnType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=26, dependsOn=[21, 24], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_24_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_21", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_26", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=27, dependsOn=[22, 24], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_24_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_22", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_27", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=28, dependsOn=[23, 24], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_24_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_23", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_28", outputType=WorkItem.TYPE_INTEGER))
      
    workItems.append(util.create_work_item(itemType="sort",
        planId=planId, itemId=29, dependsOn=[24, 26], operatorId=WorkItem.OP_SORT, extendedResult=extendedResult,
        inputTables=[inter_tab_name,inter_tab_name], 
        inputColumns=[f"{name_prefix}_it_26",f"{name_prefix}_it_24"],
        indexOutputTable=inter_tab_name, indexOutputColumn=f"{name_prefix}_it_29",
        sortOrder=[True,False]))

    workItems.append(util.create_work_item(itemType="result",
        planId=planId, itemId=30, dependsOn=[24, 26, 27, 28, 29], operatorId=WorkItem.OP_RESULT, extendedResult=extendedResult,
        resultTables=[inter_tab_name,inter_tab_name,inter_tab_name,inter_tab_name], 
        resultColumns=[f"{name_prefix}_it_27",f"{name_prefix}_it_28",f"{name_prefix}_it_26",f"{name_prefix}_it_24"],
        resultHeader=["c_city","s_city","d_year","revenue"],
        resultIndexTable=inter_tab_name, resultIndexColumn=f"{name_prefix}_it_29",
        resultName=f"sf{scale_factor}_{name_prefix}_result"))
    
    return util.create_query_plan(planId=planId, workItems=workItems, source_uuid=src_uuid, target_uuid=target_uuid)


def q_4_1(planId: int = 11, src_uuid: int = 0, target_uuid: int = 0, scale_factor: int = 1, extendedResult: bool = False) -> msg.TCPMessage:
    name_prefix: str = f"{planId}_{q_4_1.__name__}"
    inter_tab_name:str = f"{planId}_inter"

    workItems = [] 
    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=1, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="customer", inputColumn="c_region", inputType=WorkItem.TYPE_STRING, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_1_cu_i", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_EQ, filterArgVals=["AMERICA"]))
    
    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=2, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="supplier", inputColumn="s_region", inputType=WorkItem.TYPE_STRING, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_2_su_i", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_EQ, filterArgVals=["AMERICA"]))
    
    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=3, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="part", inputColumn="p_mfgr", inputType=WorkItem.TYPE_INTEGER, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_3_pa_i", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_IN, filterArgVals=["MFGR#1", "MFGR#2"]))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=6, dependsOn=[2], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_2_su_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="supplier", filterColumn="s_suppkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_6_su_m", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=8, dependsOn=[3], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_3_pa_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="part", filterColumn="p_partkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_8_pa_m", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=9, dependsOn=[1], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_1_cu_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="customer", filterColumn="c_custkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_9_cu_m", outputType=WorkItem.TYPE_INTEGER))
    
    # Semi join --> supplier not needed in output
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=10, dependsOn=[6], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_6_su_m", innerType=WorkItem.TYPE_INTEGER,
        outerTable="lineorder", outerColumn="lo_suppkey", outerType=WorkItem.TYPE_INTEGER, outerIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_10", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=14, dependsOn=[10], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_partkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_14_lo_m", outputType=WorkItem.TYPE_INTEGER))

    # Semi join --> part not needed in output
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=16, dependsOn=[8, 14], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_8_pa_m", innerType=WorkItem.TYPE_INTEGER,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_14_lo_m", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_16", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=17, dependsOn=[16, 10], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_16_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_10_o", filterType=WorkItem.TYPE_POSLIST,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_17_lo_i", outputType=WorkItem.TYPE_INTEGER))
   
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=19, dependsOn=[17], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_17_lo_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_custkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_19_lo_mat", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=21, dependsOn=[9, 19], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_9_cu_m", innerType=WorkItem.TYPE_INTEGER,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_19_lo_mat", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_21", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=22, dependsOn=[21, 17], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_21_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_17_lo_i", filterType=WorkItem.TYPE_POSLIST,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_22_lo_i", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=23, dependsOn=[22], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_22_lo_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_orderdate", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_23_lo_mat", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=25, dependsOn=[1, 21], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_21_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_1_cu_i", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_25_cu_i", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=26, dependsOn=[23], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable="date", innerColumn="d_datekey", innerType=WorkItem.TYPE_INTEGER, innerIsBase=True,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_23_lo_mat", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_26", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=27, dependsOn=[22, 26], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_26_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_22_lo_i", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_27_lo_i", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=28, dependsOn=[25, 26], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_26_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_25_cu_i", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_28_cu_i", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=280, dependsOn=[28], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_28_cu_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="customer", filterColumn="c_nation", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_280_cu_m", outputType=WorkItem.TYPE_INTEGER))  

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=30, dependsOn=[26], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_26_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="date", filterColumn="d_year", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_30_da_m", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=31, dependsOn=[27], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_27_lo_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_revenue", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_31_lo_m", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=32, dependsOn=[27], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_27_lo_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_supplycost", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_32_lo_m", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="map",
        planId=planId, itemId=310, dependsOn=[31, 32], operatorId=WorkItem.OP_MAP, operatorType=WorkItem.ARITH_SUB, extendedResult=extendedResult,
        inputTable=inter_tab_name, inputColumn=f"{name_prefix}_it_31_lo_m", inputType=WorkItem.TYPE_INTEGER,
        partnerTable=inter_tab_name, partnerColumn=f"{name_prefix}_it_32_lo_m", partnerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_310", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="multigroup",
        planId=planId, itemId=33, dependsOn=[280, 30, 32, 310], operatorId = WorkItem.OP_GROUPBY, extendedResult=extendedResult,
        tables=[inter_tab_name, inter_tab_name], 
        columns=[f"{name_prefix}_it_30_da_m", f"{name_prefix}_it_280_cu_m"], 
        columntypes=[WorkItem.TYPE_INTEGER,WorkItem.TYPE_INTEGER],
        outputIndexTable=inter_tab_name, outputIndexColumn=f"{name_prefix}_it_33_idx", 
        outputClustersTable=inter_tab_name, outputClustersColumn=f"{name_prefix}_it_33_cluster",
        aggregationTable=inter_tab_name, aggregationColumn=f"{name_prefix}_it_310", agregationColumnType=WorkItem.TYPE_INTEGER,
        aggregationResultTable=inter_tab_name, aggregationResultColumn=f"{name_prefix}_it_33", agregationResultColumnType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=34, dependsOn=[33, 30], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_33_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_30_da_m", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_34", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=35, dependsOn=[33, 280], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_33_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_280_cu_m", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_35", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="result",
        planId=planId, itemId=36, dependsOn=[33, 34, 35], operatorId=WorkItem.OP_RESULT, extendedResult=extendedResult,
        resultTables=[inter_tab_name,inter_tab_name,inter_tab_name], 
        resultColumns=[f"{name_prefix}_it_34",f"{name_prefix}_it_35",f"{name_prefix}_it_33",],
        resultHeader=["d_year","c_nation","profit"],
        resultName=f"sf{scale_factor}_{name_prefix}_result"))
    
    return util.create_query_plan(planId=planId, workItems=workItems, source_uuid=src_uuid, target_uuid=target_uuid)


def q_4_2(planId: int = 12, src_uuid: int = 0, target_uuid: int = 0, scale_factor: int = 1, extendedResult: bool = False) -> msg.TCPMessage:
    name_prefix: str = f"{planId}_{q_4_2.__name__}"
    inter_tab_name:str = f"{planId}_inter"

    workItems = [] 
    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=1, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="supplier", inputColumn="s_region", inputType=WorkItem.TYPE_STRING, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_1", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_EQ, filterArgVals=["AMERICA"]))
    
    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=2, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="customer", inputColumn="c_region", inputType=WorkItem.TYPE_STRING, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_2", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_EQ, filterArgVals=["AMERICA"]))
    
    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=3, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="part", inputColumn="p_mfgr", inputType=WorkItem.TYPE_INTEGER, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_3", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_IN, filterArgVals=["MFGR#1", "MFGR#2"]))

    workItems.append(util.create_work_item(itemType="int_filter",
        planId=planId, itemId=5, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="date", inputColumn="d_year", inputType=WorkItem.TYPE_INTEGER, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_5", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_BETWEEN, filterArgVals=[1997,1998]))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=7, dependsOn=[5], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_5", indexType=WorkItem.TYPE_POSLIST,
        filterTable="date", filterColumn="d_year", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_7", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=9, dependsOn=[5], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_5", indexType=WorkItem.TYPE_POSLIST,
        filterTable="date", filterColumn="d_datekey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_9", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=10, dependsOn=[2], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_2", indexType=WorkItem.TYPE_POSLIST,
        filterTable="customer", filterColumn="c_custkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_10", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=11, dependsOn=[1], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_1", indexType=WorkItem.TYPE_POSLIST,
        filterTable="supplier", filterColumn="s_suppkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_11", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=12, dependsOn=[1], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_1", indexType=WorkItem.TYPE_POSLIST,
        filterTable="supplier", filterColumn="s_nation", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_12", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=13, dependsOn=[3], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_3", indexType=WorkItem.TYPE_POSLIST,
        filterTable="part", filterColumn="p_category", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_13", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=14, dependsOn=[3], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_3", indexType=WorkItem.TYPE_POSLIST,
        filterTable="part", filterColumn="p_partkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_14", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=15, dependsOn=[11], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_11", innerType=WorkItem.TYPE_INTEGER,
        outerTable="lineorder", outerColumn="lo_suppkey", outerType=WorkItem.TYPE_INTEGER, outerIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_15", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=16, dependsOn=[15], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_15_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_revenue", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_16", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=17, dependsOn=[15], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_15_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_custkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_17", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=18, dependsOn=[15], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_15_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_supplycost", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_18", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=19, dependsOn=[15], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_15_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_partkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_19", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=20, dependsOn=[15], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_15_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_orderdate", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_20", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=21, dependsOn=[15, 12], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_15_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_12", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_21", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=22, dependsOn=[10, 17], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_10", innerType=WorkItem.TYPE_INTEGER,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_17", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_22", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=23, dependsOn=[22, 20], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_22_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_20", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_23", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=24, dependsOn=[22, 16], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_22_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_16", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_24", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=25, dependsOn=[22, 18], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_22_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_18", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_25", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=26, dependsOn=[22, 19], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_22_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_19", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_26", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=27, dependsOn=[22, 21], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_22_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_21", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_27", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=28, dependsOn=[9, 23], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_9", innerType=WorkItem.TYPE_INTEGER,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_23", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_28", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=29, dependsOn=[28, 7], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_28_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_7", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_29", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=30, dependsOn=[28, 24], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_28_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_24", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_30", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=31, dependsOn=[28, 27], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_28_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_27", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_31", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=32, dependsOn=[28, 25], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_28_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_25", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_32", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=33, dependsOn=[28, 26], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_28_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_26", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_33", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=34, dependsOn=[14, 33], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_14", innerType=WorkItem.TYPE_INTEGER,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_33", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_34", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=35, dependsOn=[34, 13], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_34_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_13", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_35", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=36, dependsOn=[34, 29], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_34_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_29", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_36", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=37, dependsOn=[34, 30], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_34_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_30", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_37", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=38, dependsOn=[34, 32], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_34_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_32", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_38", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=39, dependsOn=[34, 31], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_34_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_31", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_39", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="map",
        planId=planId, itemId=40, dependsOn=[37, 38], operatorId=WorkItem.OP_MAP, operatorType=WorkItem.ARITH_SUB, extendedResult=extendedResult,
        inputTable=inter_tab_name, inputColumn=f"{name_prefix}_it_37", inputType=WorkItem.TYPE_INTEGER,
        partnerTable=inter_tab_name, partnerColumn=f"{name_prefix}_it_38", partnerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_40", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="multigroup",
        planId=planId, itemId=41, dependsOn=[35, 36, 39, 40], operatorId = WorkItem.OP_GROUPBY, extendedResult=extendedResult,
        tables=[inter_tab_name, inter_tab_name,inter_tab_name], 
        columns=[f"{name_prefix}_it_36", f"{name_prefix}_it_39", f"{name_prefix}_it_35"], 
        columntypes=[WorkItem.TYPE_INTEGER,WorkItem.TYPE_INTEGER,WorkItem.TYPE_INTEGER],
        outputIndexTable=inter_tab_name, outputIndexColumn=f"{name_prefix}_it_41_idx", 
        outputClustersTable=inter_tab_name, outputClustersColumn=f"{name_prefix}_it_41_cluster",
        aggregationTable=inter_tab_name, aggregationColumn=f"{name_prefix}_it_40", agregationColumnType=WorkItem.TYPE_INTEGER,
        aggregationResultTable=inter_tab_name, aggregationResultColumn=f"{name_prefix}_it_41", agregationResultColumnType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=42, dependsOn=[41, 36], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_41_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_36", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_42", outputType=WorkItem.TYPE_INTEGER))
            
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=43, dependsOn=[41, 39], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_41_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_39", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_43", outputType=WorkItem.TYPE_INTEGER))
            
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=44, dependsOn=[35, 41], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_41_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_35", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_44", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="result",
        planId=planId, itemId=45, dependsOn=[41, 42, 43, 44], operatorId=WorkItem.OP_RESULT, extendedResult=extendedResult,
        resultTables=[inter_tab_name,inter_tab_name,inter_tab_name,inter_tab_name], 
        resultColumns=[f"{name_prefix}_it_42",f"{name_prefix}_it_43",f"{name_prefix}_it_44",f"{name_prefix}_it_41"],
        resultHeader=["d_year","s_nation","p_category","profit"],
        resultName=f"sf{scale_factor}_{name_prefix}_result"))
    
    return util.create_query_plan(planId=planId, workItems=workItems, source_uuid=src_uuid, target_uuid=target_uuid)


def q_4_2_v2(planId: int = 12, src_uuid: int = 0, target_uuid: int = 0, scale_factor: int = 1, extendedResult: bool = False) -> msg.TCPMessage:
    name_prefix: str = f"{q_4_2.__name__}"
    inter_tab_name:str = f"{planId}_inter"

    workItems = [] 
    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=1, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="supplier", inputColumn="s_region", inputType=WorkItem.TYPE_STRING, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_1_su_i", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_EQ, filterArgVals=["AMERICA"]))
    
    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=2, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="customer", inputColumn="c_region", inputType=WorkItem.TYPE_STRING, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_2_cu_i", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_EQ, filterArgVals=["AMERICA"]))
    
    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=3, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="part", inputColumn="p_mfgr", inputType=WorkItem.TYPE_INTEGER, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_3_pa_i", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_IN, filterArgVals=["MFGR#1", "MFGR#2"]))

    workItems.append(util.create_work_item(itemType="int_filter",
        planId=planId, itemId=5, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="date", inputColumn="d_year", inputType=WorkItem.TYPE_INTEGER, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_5_da_i", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_BETWEEN, filterArgVals=[1997,1998]))
    
    # workItems.append(util.create_work_item(itemType="materialize",
    #     planId=planId, itemId=7, dependsOn=[5], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
    #     indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_5", indexType=WorkItem.TYPE_POSLIST,
    #     filterTable="date", filterColumn="d_year", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
    #     outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_7", outputType=WorkItem.TYPE_INTEGER))
    
    # workItems.append(util.create_work_item(itemType="materialize",
    #     planId=planId, itemId=9, dependsOn=[5], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
    #     indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_5", indexType=WorkItem.TYPE_POSLIST,
    #     filterTable="date", filterColumn="d_datekey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
    #     outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_9", outputType=WorkItem.TYPE_INTEGER))
    
    # workItems.append(util.create_work_item(itemType="materialize",
    #     planId=planId, itemId=10, dependsOn=[2], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
    #     indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_2", indexType=WorkItem.TYPE_POSLIST,
    #     filterTable="customer", filterColumn="c_custkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
    #     outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_10", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=11, dependsOn=[1], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_1_su_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="supplier", filterColumn="s_suppkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_11_su_m", outputType=WorkItem.TYPE_INTEGER))
    
    # workItems.append(util.create_work_item(itemType="materialize",
    #     planId=planId, itemId=12, dependsOn=[1], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
    #     indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_1", indexType=WorkItem.TYPE_POSLIST,
    #     filterTable="supplier", filterColumn="s_nation", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
    #     outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_12", outputType=WorkItem.TYPE_INTEGER))

    # workItems.append(util.create_work_item(itemType="materialize",
    #     planId=planId, itemId=13, dependsOn=[3], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
    #     indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_3", indexType=WorkItem.TYPE_POSLIST,
    #     filterTable="part", filterColumn="p_category", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
    #     outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_13", outputType=WorkItem.TYPE_INTEGER))
    
    # workItems.append(util.create_work_item(itemType="materialize",
    #     planId=planId, itemId=14, dependsOn=[3], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
    #     indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_3", indexType=WorkItem.TYPE_POSLIST,
    #     filterTable="part", filterColumn="p_partkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
    #     outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_14", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=15, dependsOn=[11], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_11_su_m", innerType=WorkItem.TYPE_INTEGER,
        outerTable="lineorder", outerColumn="lo_suppkey", outerType=WorkItem.TYPE_INTEGER, outerIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_15", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=11, dependsOn=[11, 1], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_1_su_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_15_i", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_11_su_m", outputType=WorkItem.TYPE_INTEGER))

    # workItems.append(util.create_work_item(itemType="materialize",
    #     planId=planId, itemId=16, dependsOn=[15], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
    #     indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_15_o", indexType=WorkItem.TYPE_POSLIST,
    #     filterTable="lineorder", filterColumn="lo_revenue", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
    #     outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_16", outputType=WorkItem.TYPE_INTEGER))

    # workItems.append(util.create_work_item(itemType="materialize",
    #     planId=planId, itemId=17, dependsOn=[15], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
    #     indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_15_o", indexType=WorkItem.TYPE_POSLIST,
    #     filterTable="lineorder", filterColumn="lo_custkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
    #     outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_17", outputType=WorkItem.TYPE_INTEGER))

    # workItems.append(util.create_work_item(itemType="materialize",
    #     planId=planId, itemId=18, dependsOn=[15], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
    #     indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_15_o", indexType=WorkItem.TYPE_POSLIST,
    #     filterTable="lineorder", filterColumn="lo_supplycost", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
    #     outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_18", outputType=WorkItem.TYPE_INTEGER))

    # workItems.append(util.create_work_item(itemType="materialize",
    #     planId=planId, itemId=19, dependsOn=[15], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
    #     indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_15_o", indexType=WorkItem.TYPE_POSLIST,
    #     filterTable="lineorder", filterColumn="lo_partkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
    #     outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_19", outputType=WorkItem.TYPE_INTEGER))

    # workItems.append(util.create_work_item(itemType="materialize",
    #     planId=planId, itemId=20, dependsOn=[15], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
    #     indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_15_o", indexType=WorkItem.TYPE_POSLIST,
    #     filterTable="lineorder", filterColumn="lo_orderdate", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
    #     outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_20", outputType=WorkItem.TYPE_INTEGER))

    # workItems.append(util.create_work_item(itemType="materialize",
    #     planId=planId, itemId=21, dependsOn=[15, 12], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
    #     indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_15_i", indexType=WorkItem.TYPE_POSLIST,
    #     filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_12", filterType=WorkItem.TYPE_INTEGER,
    #     outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_21", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=22, dependsOn=[10, 17], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_10", innerType=WorkItem.TYPE_INTEGER,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_17", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_22", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=23, dependsOn=[22, 20], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_22_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_20", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_23", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=24, dependsOn=[22, 16], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_22_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_16", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_24", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=25, dependsOn=[22, 18], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_22_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_18", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_25", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=26, dependsOn=[22, 19], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_22_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_19", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_26", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=27, dependsOn=[22, 21], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_22_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_21", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_27", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=28, dependsOn=[9, 23], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_9", innerType=WorkItem.TYPE_INTEGER,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_23", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_28", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=29, dependsOn=[28, 7], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_28_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_7", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_29", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=30, dependsOn=[28, 24], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_28_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_24", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_30", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=31, dependsOn=[28, 27], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_28_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_27", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_31", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=32, dependsOn=[28, 25], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_28_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_25", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_32", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=33, dependsOn=[28, 26], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_28_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_26", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_33", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=34, dependsOn=[14, 33], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_14", innerType=WorkItem.TYPE_INTEGER,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_33", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_34", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=35, dependsOn=[34, 13], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_34_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_13", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_35", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=36, dependsOn=[34, 29], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_34_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_29", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_36", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=37, dependsOn=[34, 30], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_34_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_30", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_37", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=38, dependsOn=[34, 32], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_34_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_32", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_38", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=39, dependsOn=[34, 31], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_34_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_31", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_39", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="map",
        planId=planId, itemId=40, dependsOn=[37, 38], operatorId=WorkItem.OP_MAP, operatorType=WorkItem.ARITH_SUB, extendedResult=extendedResult,
        inputTable=inter_tab_name, inputColumn=f"{name_prefix}_it_37", inputType=WorkItem.TYPE_INTEGER,
        partnerTable=inter_tab_name, partnerColumn=f"{name_prefix}_it_38", partnerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_40", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="multigroup",
        planId=planId, itemId=41, dependsOn=[35, 36, 39, 40], operatorId = WorkItem.OP_GROUPBY, extendedResult=extendedResult,
        tables=[inter_tab_name, inter_tab_name,inter_tab_name], 
        columns=[f"{name_prefix}_it_36", f"{name_prefix}_it_39", f"{name_prefix}_it_35"], 
        columntypes=[WorkItem.TYPE_INTEGER,WorkItem.TYPE_INTEGER,WorkItem.TYPE_INTEGER],
        outputIndexTable=inter_tab_name, outputIndexColumn=f"{name_prefix}_it_41_idx", 
        outputClustersTable=inter_tab_name, outputClustersColumn=f"{name_prefix}_it_41_cluster",
        aggregationTable=inter_tab_name, aggregationColumn=f"{name_prefix}_it_40", agregationColumnType=WorkItem.TYPE_INTEGER,
        aggregationResultTable=inter_tab_name, aggregationResultColumn=f"{name_prefix}_it_41", agregationResultColumnType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=42, dependsOn=[41, 36], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_41_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_36", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_42", outputType=WorkItem.TYPE_INTEGER))
            
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=43, dependsOn=[41, 39], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_41_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_39", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_43", outputType=WorkItem.TYPE_INTEGER))
            
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=44, dependsOn=[35, 41], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_41_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_35", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_44", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="result",
        planId=planId, itemId=45, dependsOn=[41, 42, 43, 44], operatorId=WorkItem.OP_RESULT, extendedResult=extendedResult,
        resultTables=[inter_tab_name,inter_tab_name,inter_tab_name,inter_tab_name], 
        resultColumns=[f"{name_prefix}_it_42",f"{name_prefix}_it_43",f"{name_prefix}_it_44",f"{name_prefix}_it_41"],
        resultHeader=["d_year","s_nation","p_category","profit"],
        resultName=f"sf{scale_factor}_{name_prefix}_result"))
    
    return util.create_query_plan(planId=planId, workItems=workItems, source_uuid=src_uuid, target_uuid=target_uuid)


def q_4_2_vai(planId: int = 12, src_uuid: int = 0, target_uuid: int = 0, scale_factor: int = 1, extendedResult: bool = False) -> msg.TCPMessage:
    name_prefix: str = f"{q_4_2.__name__}"
    inter_tab_name: str = f"{planId}_inter"

    workItems = []

    # === FILTERS ===
    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=1, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="customer", inputColumn="c_region", inputType=WorkItem.TYPE_STRING, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_1_cu_i", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_EQ, filterArgVals=["AMERICA"]))

    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=2, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="supplier", inputColumn="s_region", inputType=WorkItem.TYPE_STRING, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_2_su_i", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_EQ, filterArgVals=["AMERICA"]))

    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=3, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="part", inputColumn="p_mfgr", inputType=WorkItem.TYPE_INTEGER, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_3_pa_i", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_IN, filterArgVals=["MFGR#1", "MFGR#2"]))

    workItems.append(util.create_work_item(itemType="int_filter",
        planId=planId, itemId=5, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="date", inputColumn="d_year", inputType=WorkItem.TYPE_INTEGER, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_5_da_i", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_BETWEEN, filterArgVals=[1997, 1998]))

    # === MATERIALIZE JOIN KEYS ONLY ===
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=6, dependsOn=[2], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_2_su_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="supplier", filterColumn="s_suppkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_6_su_m", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=8, dependsOn=[3], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_3_pa_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="part", filterColumn="p_partkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_8_pa_m", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=9, dependsOn=[1], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_1_cu_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="customer", filterColumn="c_custkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_9_cu_m", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=7, dependsOn=[5], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_5_da_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="date", filterColumn="d_datekey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_7_da_m", outputType=WorkItem.TYPE_INTEGER))

    # === JOIN 1: supplier ⋈ lineorder (NOT semi — need s_nation in output) ===
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=10, dependsOn=[6], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_6_su_m", innerType=WorkItem.TYPE_INTEGER,
        outerTable="lineorder", outerColumn="lo_suppkey", outerType=WorkItem.TYPE_INTEGER, outerIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_10", outputType=WorkItem.TYPE_INTEGER))

    # Materialize lo_partkey for join 2
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=14, dependsOn=[10], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_partkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_14_lo_m", outputType=WorkItem.TYPE_INTEGER))

    # === JOIN 2: part ⋈ ... (NOT semi — need p_category in output) ===
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=16, dependsOn=[8, 14], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_8_pa_m", innerType=WorkItem.TYPE_INTEGER,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_14_lo_m", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_16", outputType=WorkItem.TYPE_INTEGER))

    # Update running lineorder index
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=17, dependsOn=[16, 10], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_16_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_10_o", filterType=WorkItem.TYPE_POSLIST,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_17_lo_i", outputType=WorkItem.TYPE_INTEGER))

    # Materialize lo_custkey for join 3
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=19, dependsOn=[17], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_17_lo_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_custkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_19_lo_mat", outputType=WorkItem.TYPE_INTEGER))

    # === JOIN 3: customer ⋈ ... (SEMI join — customer not needed in output) ===
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=21, dependsOn=[9, 19], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_9_cu_m", innerType=WorkItem.TYPE_INTEGER,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_19_lo_mat", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_21", outputType=WorkItem.TYPE_INTEGER))

    # Update running lineorder index
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=22, dependsOn=[21, 17], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_21_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_17_lo_i", filterType=WorkItem.TYPE_POSLIST,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_22_lo_i", outputType=WorkItem.TYPE_INTEGER))

    # Materialize lo_orderdate for join 4
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=23, dependsOn=[22], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_22_lo_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_orderdate", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_23_lo_mat", outputType=WorkItem.TYPE_INTEGER))

    # === JOIN 4: date ⋈ ... (NOT semi — need d_year in output) ===
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=26, dependsOn=[7, 23], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_7_da_m", innerType=WorkItem.TYPE_INTEGER,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_23_lo_mat", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_26", outputType=WorkItem.TYPE_INTEGER))

    # Final running lineorder index
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=27, dependsOn=[22, 26], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_26_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_22_lo_i", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_27_lo_i", outputType=WorkItem.TYPE_INTEGER))

    # === CHAIN SUPPLIER INNER POSITIONS (join 1) through joins 2, 3, 4 ===
    # Get supplier filter positions matched in join 1
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=25, dependsOn=[2, 10], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_2_su_i", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_25_su_i", outputType=WorkItem.TYPE_INTEGER))

    # Chain through join 2 (part)
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=28, dependsOn=[25, 16], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_16_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_25_su_i", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_28_su_i", outputType=WorkItem.TYPE_INTEGER))

    # Chain through join 3 (customer semi)
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=29, dependsOn=[28, 21], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_21_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_28_su_i", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_29_su_i", outputType=WorkItem.TYPE_INTEGER))

    # Chain through join 4 (date)
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=290, dependsOn=[29, 26], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_26_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_29_su_i", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_290_su_i", outputType=WorkItem.TYPE_INTEGER))

    # Materialize s_nation from supplier base
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=291, dependsOn=[290], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_290_su_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="supplier", filterColumn="s_nation", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_291_su_m", outputType=WorkItem.TYPE_INTEGER))

    # === CHAIN PART INNER POSITIONS (join 2) through joins 3, 4 ===
    # Get part filter positions matched in join 2
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=40, dependsOn=[3, 16], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_16_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_3_pa_i", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_40_pa_i", outputType=WorkItem.TYPE_INTEGER))

    # Chain through join 3 (customer semi)
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=41, dependsOn=[40, 21], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_21_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_40_pa_i", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_41_pa_i", outputType=WorkItem.TYPE_INTEGER))

    # Chain through join 4 (date)
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=42, dependsOn=[41, 26], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_26_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_41_pa_i", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_42_pa_i", outputType=WorkItem.TYPE_INTEGER))

    # Materialize p_category from part base
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=43, dependsOn=[42], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_42_pa_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="part", filterColumn="p_category", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_43_pa_m", outputType=WorkItem.TYPE_INTEGER))

    # === DATE: d_year from join 4 inner positions ===
    # Get date base positions from filtered date poslist using join 4 inner
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=30, dependsOn=[5, 26], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_26_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_5_da_i", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_30_da_i", outputType=WorkItem.TYPE_INTEGER))

    # Materialize d_year from date base
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=301, dependsOn=[30], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_30_da_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="date", filterColumn="d_year", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_301_da_m", outputType=WorkItem.TYPE_INTEGER))

    # === MATERIALIZE lo_revenue and lo_supplycost using final running index ===
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=31, dependsOn=[27], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_27_lo_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_revenue", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_31_lo_m", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=32, dependsOn=[27], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_27_lo_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_supplycost", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_32_lo_m", outputType=WorkItem.TYPE_INTEGER))

    # === PROFIT = lo_revenue - lo_supplycost ===
    workItems.append(util.create_work_item(itemType="map",
        planId=planId, itemId=310, dependsOn=[31, 32], operatorId=WorkItem.OP_MAP, operatorType=WorkItem.ARITH_SUB, extendedResult=extendedResult,
        inputTable=inter_tab_name, inputColumn=f"{name_prefix}_it_31_lo_m", inputType=WorkItem.TYPE_INTEGER,
        partnerTable=inter_tab_name, partnerColumn=f"{name_prefix}_it_32_lo_m", partnerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_310", outputType=WorkItem.TYPE_INTEGER))

    # === GROUP BY d_year, s_nation, p_category; SUM(profit) ===
    workItems.append(util.create_work_item(itemType="multigroup",
        planId=planId, itemId=33, dependsOn=[301, 291, 43, 310], operatorId=WorkItem.OP_GROUPBY, extendedResult=extendedResult,
        tables=[inter_tab_name, inter_tab_name, inter_tab_name],
        columns=[f"{name_prefix}_it_301_da_m", f"{name_prefix}_it_291_su_m", f"{name_prefix}_it_43_pa_m"],
        columntypes=[WorkItem.TYPE_INTEGER, WorkItem.TYPE_INTEGER, WorkItem.TYPE_INTEGER],
        outputIndexTable=inter_tab_name, outputIndexColumn=f"{name_prefix}_it_33_idx",
        outputClustersTable=inter_tab_name, outputClustersColumn=f"{name_prefix}_it_33_cluster",
        aggregationTable=inter_tab_name, aggregationColumn=f"{name_prefix}_it_310", agregationColumnType=WorkItem.TYPE_INTEGER,
        aggregationResultTable=inter_tab_name, aggregationResultColumn=f"{name_prefix}_it_33", agregationResultColumnType=WorkItem.TYPE_INTEGER))

    # === RESULT MATERIALIZATIONS ===
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=34, dependsOn=[33, 301], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_33_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_301_da_m", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_34", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=35, dependsOn=[33, 291], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_33_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_291_su_m", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_35", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=36, dependsOn=[33, 43], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_33_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_43_pa_m", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_36", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="result",
        planId=planId, itemId=37, dependsOn=[33, 34, 35, 36], operatorId=WorkItem.OP_RESULT, extendedResult=extendedResult,
        resultTables=[inter_tab_name, inter_tab_name, inter_tab_name, inter_tab_name],
        resultColumns=[f"{name_prefix}_it_34", f"{name_prefix}_it_35", f"{name_prefix}_it_36", f"{name_prefix}_it_33"],
        resultHeader=["d_year", "s_nation", "p_category", "profit"],
        resultName=f"sf{scale_factor}_{name_prefix}_result"))

    return util.create_query_plan(planId=planId, workItems=workItems, source_uuid=src_uuid, target_uuid=target_uuid)


def q_4_3(planId: int = 13, src_uuid: int = 0, target_uuid: int = 0, scale_factor: int = 1, extendedResult: bool = False) -> msg.TCPMessage:
    name_prefix: str = f"{planId}_{q_4_3.__name__}"
    inter_tab_name:str = f"{planId}_inter"
    
    workItems = [] 
    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=1, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="supplier", inputColumn="s_nation", inputType=WorkItem.TYPE_STRING, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_1", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_EQ, filterArgVals=["UNITED STATES"]))
    
    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=3, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="part", inputColumn="p_category", inputType=WorkItem.TYPE_INTEGER, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_3", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_EQ, filterArgVals=["MFGR#14"]))

    workItems.append(util.create_work_item(itemType="int_filter",
        planId=planId, itemId=5, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="date", inputColumn="d_year", inputType=WorkItem.TYPE_INTEGER, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_5", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_BETWEEN, filterArgVals=[1997,1998]))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=7, dependsOn=[5], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_5", indexType=WorkItem.TYPE_POSLIST,
        filterTable="date", filterColumn="d_year", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_7", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=9, dependsOn=[5], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_5", indexType=WorkItem.TYPE_POSLIST,
        filterTable="date", filterColumn="d_datekey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_9", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=11, dependsOn=[1], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_1", indexType=WorkItem.TYPE_POSLIST,
        filterTable="supplier", filterColumn="s_suppkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_11", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=12, dependsOn=[1], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_1", indexType=WorkItem.TYPE_POSLIST,
        filterTable="supplier", filterColumn="s_city", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_12", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=13, dependsOn=[3], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_3", indexType=WorkItem.TYPE_POSLIST,
        filterTable="part", filterColumn="p_brand", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_13", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=14, dependsOn=[3], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_3", indexType=WorkItem.TYPE_POSLIST,
        filterTable="part", filterColumn="p_partkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_14", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=15, dependsOn=[11], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_11", innerType=WorkItem.TYPE_INTEGER,
        outerTable="lineorder", outerColumn="lo_suppkey", outerType=WorkItem.TYPE_INTEGER, outerIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_15", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=16, dependsOn=[15], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_15_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_revenue", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_16", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=17, dependsOn=[15], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_15_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_custkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_17", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=18, dependsOn=[15], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_15_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_supplycost", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_18", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=19, dependsOn=[15], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_15_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_partkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_19", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=20, dependsOn=[15], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_15_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_orderdate", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_20", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=21, dependsOn=[15, 12], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_15_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_12", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_21", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=22, dependsOn=[17], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable="customer", innerColumn="c_custkey", innerType=WorkItem.TYPE_INTEGER, innerIsBase=True,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_17", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_22", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=23, dependsOn=[22, 20], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_22_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_20", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_23", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=24, dependsOn=[22, 16], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_22_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_16", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_24", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=25, dependsOn=[22, 18], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_22_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_18", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_25", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=26, dependsOn=[22, 19], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_22_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_19", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_26", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=27, dependsOn=[22, 21], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_22_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_21", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_27", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=28, dependsOn=[9, 23], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_9", innerType=WorkItem.TYPE_INTEGER,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_23", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_28", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=29, dependsOn=[28, 7], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_28_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_7", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_29", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=30, dependsOn=[28, 24], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_28_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_24", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_30", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=31, dependsOn=[28, 27], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_28_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_27", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_31", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=32, dependsOn=[28, 25], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_28_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_25", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_32", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=33, dependsOn=[28, 26], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_28_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_26", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_33", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=34, dependsOn=[14, 33], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_14", innerType=WorkItem.TYPE_INTEGER,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_33", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_34", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=35, dependsOn=[34, 13], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_34_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_13", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_35", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=36, dependsOn=[34, 29], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_34_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_29", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_36", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=37, dependsOn=[34, 30], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_34_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_30", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_37", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=38, dependsOn=[34, 32], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_34_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_32", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_38", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=39, dependsOn=[34, 31], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_34_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_31", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_39", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="map",
        planId=planId, itemId=40, dependsOn=[37, 38], operatorId=WorkItem.OP_MAP, operatorType=WorkItem.ARITH_SUB, extendedResult=extendedResult,
        inputTable=inter_tab_name, inputColumn=f"{name_prefix}_it_37", inputType=WorkItem.TYPE_INTEGER,
        partnerTable=inter_tab_name, partnerColumn=f"{name_prefix}_it_38", partnerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_40", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="multigroup",
        planId=planId, itemId=41, dependsOn=[35, 36, 39, 40], operatorId = WorkItem.OP_GROUPBY, extendedResult=extendedResult,
        tables=[inter_tab_name, inter_tab_name,inter_tab_name], 
        columns=[f"{name_prefix}_it_36", f"{name_prefix}_it_39", f"{name_prefix}_it_35"], 
        columntypes=[WorkItem.TYPE_INTEGER,WorkItem.TYPE_INTEGER,WorkItem.TYPE_INTEGER],
        outputIndexTable=inter_tab_name, outputIndexColumn=f"{name_prefix}_it_41_idx", 
        outputClustersTable=inter_tab_name, outputClustersColumn=f"{name_prefix}_it_41_cluster",
        aggregationTable=inter_tab_name, aggregationColumn=f"{name_prefix}_it_40", agregationColumnType=WorkItem.TYPE_INTEGER,
        aggregationResultTable=inter_tab_name, aggregationResultColumn=f"{name_prefix}_it_41", agregationResultColumnType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=42, dependsOn=[41, 36], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_41_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_36", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_42", outputType=WorkItem.TYPE_INTEGER))
            
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=43, dependsOn=[41, 39], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_41_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_39", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_43", outputType=WorkItem.TYPE_INTEGER))
            
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=44, dependsOn=[35, 41], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_41_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_35", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_44", outputType=WorkItem.TYPE_INTEGER))
    
    workItems.append(util.create_work_item(itemType="result",
        planId=planId, itemId=45, dependsOn=[41, 42, 43, 44], operatorId=WorkItem.OP_RESULT, extendedResult=extendedResult,
        resultTables=[inter_tab_name,inter_tab_name,inter_tab_name,inter_tab_name], 
        resultColumns=[f"{name_prefix}_it_42",f"{name_prefix}_it_43",f"{name_prefix}_it_44",f"{name_prefix}_it_41"],
        resultHeader=["d_year","s_city","p_brand","profit"],
        resultName=f"sf{scale_factor}_{name_prefix}_result"))
    
    return util.create_query_plan(planId=planId, workItems=workItems, source_uuid=src_uuid, target_uuid=target_uuid)


def q_4_3_vai(planId: int = 13, src_uuid: int = 0, target_uuid: int = 0, scale_factor: int = 1, extendedResult: bool = False) -> msg.TCPMessage:
    name_prefix: str = f"{planId}_{q_4_3.__name__}"
    inter_tab_name: str = f"{planId}_inter"

    workItems = []

    # === FILTERS ===
    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=1, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="supplier", inputColumn="s_nation", inputType=WorkItem.TYPE_STRING, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_1_su_i", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_EQ, filterArgVals=["UNITED STATES"]))

    workItems.append(util.create_work_item(itemType="string_filter",
        planId=planId, itemId=3, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="part", inputColumn="p_category", inputType=WorkItem.TYPE_INTEGER, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_3_pa_i", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_EQ, filterArgVals=["MFGR#14"]))

    workItems.append(util.create_work_item(itemType="int_filter",
        planId=planId, itemId=5, operatorId=WorkItem.OP_FILTER, extendedResult=extendedResult,
        inputTable="date", inputColumn="d_year", inputType=WorkItem.TYPE_INTEGER, inputIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_5_da_i", outputType=WorkItem.TYPE_POSLIST,
        filterType=WorkItem.COMP_BETWEEN, filterArgVals=[1997, 1998]))

    # === MATERIALIZE JOIN KEYS ONLY ===
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=6, dependsOn=[1], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_1_su_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="supplier", filterColumn="s_suppkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_6_su_m", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=8, dependsOn=[3], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_3_pa_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="part", filterColumn="p_partkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_8_pa_m", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=7, dependsOn=[5], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_5_da_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="date", filterColumn="d_datekey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_7_da_m", outputType=WorkItem.TYPE_INTEGER))

    # === JOIN 1: supplier ⋈ lineorder (NOT semi — need s_city) ===
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=10, dependsOn=[6], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_6_su_m", innerType=WorkItem.TYPE_INTEGER,
        outerTable="lineorder", outerColumn="lo_suppkey", outerType=WorkItem.TYPE_INTEGER, outerIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_10", outputType=WorkItem.TYPE_INTEGER))

    # Materialize lo_partkey for join 2
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=14, dependsOn=[10], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_partkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_14_lo_m", outputType=WorkItem.TYPE_INTEGER))

    # === JOIN 2: part ⋈ ... (NOT semi — need p_brand) ===
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=16, dependsOn=[8, 14], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_8_pa_m", innerType=WorkItem.TYPE_INTEGER,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_14_lo_m", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_16", outputType=WorkItem.TYPE_INTEGER))

    # Update running lineorder index
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=17, dependsOn=[16, 10], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_16_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_10_o", filterType=WorkItem.TYPE_POSLIST,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_17_lo_i", outputType=WorkItem.TYPE_INTEGER))

    # Materialize lo_custkey for join 3
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=19, dependsOn=[17], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_17_lo_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_custkey", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_19_lo_mat", outputType=WorkItem.TYPE_INTEGER))

    # === JOIN 3: customer ⋈ ... (SEMI join — no filter, no output columns) ===
    # Join against full customer base table
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=21, dependsOn=[19], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable="customer", innerColumn="c_custkey", innerType=WorkItem.TYPE_INTEGER, innerIsBase=True,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_19_lo_mat", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_21", outputType=WorkItem.TYPE_INTEGER))

    # Update running lineorder index
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=22, dependsOn=[21, 17], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_21_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_17_lo_i", filterType=WorkItem.TYPE_POSLIST,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_22_lo_i", outputType=WorkItem.TYPE_INTEGER))

    # Materialize lo_orderdate for join 4
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=23, dependsOn=[22], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_22_lo_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_orderdate", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_23_lo_mat", outputType=WorkItem.TYPE_INTEGER))

    # === JOIN 4: date ⋈ ... (NOT semi — need d_year) ===
    workItems.append(util.create_work_item(itemType="join",
        planId=planId, itemId=26, dependsOn=[7, 23], operatorId=WorkItem.OP_HASHJOIN, extendedResult=extendedResult,
        innerTable=inter_tab_name, innerColumn=f"{name_prefix}_it_7_da_m", innerType=WorkItem.TYPE_INTEGER,
        outerTable=inter_tab_name, outerColumn=f"{name_prefix}_it_23_lo_mat", outerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_26", outputType=WorkItem.TYPE_INTEGER))

    # Final running lineorder index
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=27, dependsOn=[22, 26], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_26_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_22_lo_i", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_27_lo_i", outputType=WorkItem.TYPE_INTEGER))

    # === CHAIN SUPPLIER INNER POSITIONS (join 1) through joins 2, 3, 4 ===
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=25, dependsOn=[1, 10], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_10_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_1_su_i", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_25_su_i", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=28, dependsOn=[25, 16], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_16_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_25_su_i", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_28_su_i", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=29, dependsOn=[28, 21], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_21_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_28_su_i", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_29_su_i", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=290, dependsOn=[29, 26], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_26_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_29_su_i", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_290_su_i", outputType=WorkItem.TYPE_INTEGER))

    # Materialize s_city from supplier base
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=291, dependsOn=[290], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_290_su_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="supplier", filterColumn="s_city", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_291_su_m", outputType=WorkItem.TYPE_INTEGER))

    # === CHAIN PART INNER POSITIONS (join 2) through joins 3, 4 ===
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=40, dependsOn=[3, 16], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_16_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_3_pa_i", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_40_pa_i", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=41, dependsOn=[40, 21], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_21_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_40_pa_i", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_41_pa_i", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=42, dependsOn=[41, 26], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_26_o", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_41_pa_i", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_42_pa_i", outputType=WorkItem.TYPE_INTEGER))

    # Materialize p_brand from part base
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=43, dependsOn=[42], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_42_pa_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="part", filterColumn="p_brand", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_43_pa_m", outputType=WorkItem.TYPE_INTEGER))

    # === DATE: d_year from join 4 inner positions ===
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=30, dependsOn=[5, 26], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_26_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_5_da_i", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_30_da_i", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=301, dependsOn=[30], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_30_da_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="date", filterColumn="d_year", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_301_da_m", outputType=WorkItem.TYPE_INTEGER))

    # === MATERIALIZE lo_revenue and lo_supplycost using final running index ===
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=31, dependsOn=[27], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_27_lo_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_revenue", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_31_lo_m", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=32, dependsOn=[27], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_27_lo_i", indexType=WorkItem.TYPE_POSLIST,
        filterTable="lineorder", filterColumn="lo_supplycost", filterType=WorkItem.TYPE_INTEGER, filterIsBase=True,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_32_lo_m", outputType=WorkItem.TYPE_INTEGER))

    # === PROFIT = lo_revenue - lo_supplycost ===
    workItems.append(util.create_work_item(itemType="map",
        planId=planId, itemId=310, dependsOn=[31, 32], operatorId=WorkItem.OP_MAP, operatorType=WorkItem.ARITH_SUB, extendedResult=extendedResult,
        inputTable=inter_tab_name, inputColumn=f"{name_prefix}_it_31_lo_m", inputType=WorkItem.TYPE_INTEGER,
        partnerTable=inter_tab_name, partnerColumn=f"{name_prefix}_it_32_lo_m", partnerType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_310", outputType=WorkItem.TYPE_INTEGER))

    # === GROUP BY d_year, s_city, p_brand; SUM(profit) ===
    workItems.append(util.create_work_item(itemType="multigroup",
        planId=planId, itemId=33, dependsOn=[301, 291, 43, 310], operatorId=WorkItem.OP_GROUPBY, extendedResult=extendedResult,
        tables=[inter_tab_name, inter_tab_name, inter_tab_name],
        columns=[f"{name_prefix}_it_301_da_m", f"{name_prefix}_it_291_su_m", f"{name_prefix}_it_43_pa_m"],
        columntypes=[WorkItem.TYPE_INTEGER, WorkItem.TYPE_INTEGER, WorkItem.TYPE_INTEGER],
        outputIndexTable=inter_tab_name, outputIndexColumn=f"{name_prefix}_it_33_idx",
        outputClustersTable=inter_tab_name, outputClustersColumn=f"{name_prefix}_it_33_cluster",
        aggregationTable=inter_tab_name, aggregationColumn=f"{name_prefix}_it_310", agregationColumnType=WorkItem.TYPE_INTEGER,
        aggregationResultTable=inter_tab_name, aggregationResultColumn=f"{name_prefix}_it_33", agregationResultColumnType=WorkItem.TYPE_INTEGER))

    # === RESULT MATERIALIZATIONS ===
    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=34, dependsOn=[33, 301], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_33_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_301_da_m", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_34", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=35, dependsOn=[33, 291], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_33_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_291_su_m", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_35", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="materialize",
        planId=planId, itemId=36, dependsOn=[33, 43], operatorId=WorkItem.OP_MATERIALIZE, extendedResult=extendedResult,
        indexTable=inter_tab_name, indexColumn=f"{name_prefix}_it_33_idx", indexType=WorkItem.TYPE_POSLIST,
        filterTable=inter_tab_name, filterColumn=f"{name_prefix}_it_43_pa_m", filterType=WorkItem.TYPE_INTEGER,
        outputTable=inter_tab_name, outputColumn=f"{name_prefix}_it_36", outputType=WorkItem.TYPE_INTEGER))

    workItems.append(util.create_work_item(itemType="result",
        planId=planId, itemId=37, dependsOn=[33, 34, 35, 36], operatorId=WorkItem.OP_RESULT, extendedResult=extendedResult,
        resultTables=[inter_tab_name, inter_tab_name, inter_tab_name, inter_tab_name],
        resultColumns=[f"{name_prefix}_it_34", f"{name_prefix}_it_35", f"{name_prefix}_it_36", f"{name_prefix}_it_33"],
        resultHeader=["d_year", "s_city", "p_brand", "profit"],
        resultName=f"sf{scale_factor}_{name_prefix}_result"))

    return util.create_query_plan(planId=planId, workItems=workItems, source_uuid=src_uuid, target_uuid=target_uuid)
