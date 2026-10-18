from proto import WorkRequest_pb2 as WorkRequest
from proto import WorkItem_pb2 as WorkItem
from proto import NetworkRequests_pb2 as NetworkRequests
from proto import ConfigurationRequests_pb2 as ConfigurationRequests
from proto import QueryPlan_pb2 as QueryPlan
from utils import msg

from proto.UnitDefinition_pb2 import TcpPackageType
from proto.UnitDefinition_pb2 import UnitType

def create_query_plan(**kwargs) -> msg.TCPMessage:
    plan = msg.TCPMessage(unit_type=UnitType.QUERY_PLANER, package_type=kwargs.get("package_type", TcpPackageType.QUERY_PLAN), src_uuid=kwargs.get("source_uuid", 0), tgt_uuid=kwargs.get("target_uuid", 0))
    qplan = QueryPlan.QueryPlan()
    qplan.planid = kwargs["planId"]
    for item in kwargs["workItems"]:
        qplan.planitems.append(item)
    request = WorkRequest.WorkRequest()
    request.queryPlan.CopyFrom(qplan)
    plan.payload = request.SerializeToString()
    return plan, qplan
    

def create_work_item(**kwargs) -> WorkItem.WorkItem:
    witem = WorkItem.WorkItem()
    witem.planId = kwargs["planId"]
    witem.itemId = kwargs["itemId"]
    if "operatorId" in kwargs:
        # leave unset if not needed
        witem.operatorId = kwargs["operatorId"]
    witem.printDebug = kwargs["printDebug"] if "printDebug" in kwargs else False
    if "simdExt" in kwargs:
        witem.simdExt = kwargs["simdExt"]
    if "dependsOn" in kwargs:
        witem.dependsOn.extend(kwargs["dependsOn"])
    
    witem.returnExtendedResult = kwargs.get("extendedResult", False)

    item = None
    if "itemType" in kwargs:
        itemType = kwargs["itemType"]
        if itemType == "int_filter":
            item = create_int_filter_item(**kwargs)
            witem.filterData.CopyFrom(item)
        elif itemType == "string_filter":
            item = create_string_filter_item(**kwargs)
            witem.filterData.CopyFrom(item)
        elif itemType == "set_operation":
            item = create_set_operation_item(**kwargs)
            witem.setData.CopyFrom(item)
        elif itemType == "materialize":
            item = create_materialize_item(**kwargs)
            witem.materializeData.CopyFrom(item)
        elif itemType == "join":
            item = create_join_item(**kwargs)
            witem.joinData.CopyFrom(item)
        elif itemType == "map":
            item = create_map(**kwargs)
            witem.mapData.CopyFrom(item)    
        elif itemType == "aggregate":
            item = create_aggregate_item(**kwargs)
            witem.aggData.CopyFrom(item)
        elif itemType == "fetch":
            item = create_fetch_item(**kwargs)
            witem.fetchData.CopyFrom(item)
        elif itemType == "result":
            item = create_result_item(**kwargs)
            witem.resultData.CopyFrom(item)
        elif itemType == "sort":
            item = create_sort_item(**kwargs)
            witem.sortData.CopyFrom(item)
        elif itemType == "multigroup":
            item = create_multigroup_item(**kwargs)
            witem.multiGroupData.CopyFrom(item)
    else:
        raise ValueError("itemType must be specified for create_work_item")

    return witem
    
    
def create_work_request(**kwargs) -> WorkRequest.WorkRequest:
    witem = create_work_item(**kwargs)
    request = WorkRequest.WorkRequest()
    request.workItem.CopyFrom(witem)
    return request

    
def create_tcp_message(**kwargs) -> msg.TCPMessage:
    work = msg.TCPMessage(unit_type=UnitType.QUERY_PLANER, package_type=TcpPackageType.WORK, src_uuid=kwargs.get("source_uuid", 0), tgt_uuid=kwargs.get("target_uuid", 0))
    request = create_work_request(**kwargs)
    work.payload = request.SerializeToString()

    return work
    
    
def create_int_filter_item(**kwargs) -> WorkItem.FilterItem:
    filterItem = WorkItem.FilterItem()
    
    filterItem.inputColumn.tabName = kwargs["inputTable"]
    filterItem.inputColumn.colName = kwargs["inputColumn"]
    filterItem.inputColumn.colType = kwargs["inputType"]
    filterItem.inputColumn.isBase = kwargs.get("inputIsBase", False)

    filterItem.outputColumn.tabName = kwargs["outputTable"]
    filterItem.outputColumn.colName = kwargs["outputColumn"]
    filterItem.outputColumn.colType = kwargs["outputType"]

    filterItem.filterType = kwargs["filterType"]
    filterValArray = []
    filterArgVals = kwargs["filterArgVals"]
    for i in range(0, len(filterArgVals)):
        intValue = WorkItem.IntValue()
        intValue.value = filterArgVals[i]
        filterValue = WorkItem.ScalarValue()
        filterValue.intVal.CopyFrom(intValue)
        filterValArray.append(filterValue)
    filterItem.filterValue.extend(filterValArray)
    return filterItem


def create_string_filter_item(**kwargs) -> WorkItem.FilterItem:
    filterItem = WorkItem.FilterItem()
    
    filterItem.inputColumn.tabName = kwargs["inputTable"]
    filterItem.inputColumn.colName = kwargs["inputColumn"]
    filterItem.inputColumn.colType = kwargs["inputType"]
    filterItem.inputColumn.isBase = kwargs.get("inputIsBase", False)

    filterItem.outputColumn.tabName = kwargs["outputTable"]
    filterItem.outputColumn.colName = kwargs["outputColumn"]
    filterItem.outputColumn.colType = kwargs["outputType"]

    filterItem.filterType = kwargs["filterType"]
    filterValArray = []
    filterArgVals = kwargs["filterArgVals"]
    for i in range(0, len(filterArgVals)):
        stringValue = WorkItem.StringValue()
        stringValue.value = filterArgVals[i]
        filterValue = WorkItem.ScalarValue()
        filterValue.stringVal.CopyFrom(stringValue)
        filterValArray.append(filterValue)
    filterItem.filterValue.extend(filterValArray)
    return filterItem

def create_set_operation_item(**kwargs) -> WorkItem.SetOperationItem:
    setopItem = WorkItem.SetOperationItem()
    setopItem.operation = kwargs["operation"]

    setopItem.innerColumn.tabName = kwargs["innerTable"]
    setopItem.innerColumn.colName = kwargs["innerColumn"]
    setopItem.innerColumn.colType = kwargs["innerType"]
    setopItem.innerColumn.isBase = kwargs.get("innerIsBase", False)

    setopItem.outerColumn.tabName = kwargs["outerTable"]
    setopItem.outerColumn.colName = kwargs["outerColumn"]
    setopItem.outerColumn.colType = kwargs["outerType"]
    setopItem.outerColumn.isBase = kwargs.get("outerIsBase", False)

    setopItem.outputColumn.tabName = kwargs["outputTable"]
    setopItem.outputColumn.colName = kwargs["outputColumn"]
    setopItem.outputColumn.colType = kwargs["outputType"]

    return setopItem

def create_materialize_item(**kwargs) -> WorkItem.MaterializeItem:
    materializeItem = WorkItem.MaterializeItem()

    materializeItem.indexColumn.tabName = kwargs["indexTable"]
    materializeItem.indexColumn.colName = kwargs["indexColumn"]
    materializeItem.indexColumn.colType = kwargs["indexType"]

    materializeItem.filterColumn.tabName = kwargs["filterTable"]
    materializeItem.filterColumn.colName = kwargs["filterColumn"]
    materializeItem.filterColumn.colType = kwargs["filterType"]
    materializeItem.filterColumn.isBase = kwargs.get("filterIsBase", False)

    materializeItem.outputColumn.tabName = kwargs["outputTable"]
    materializeItem.outputColumn.colName = kwargs["outputColumn"]
    materializeItem.outputColumn.colType = kwargs["outputType"]

    return materializeItem

def create_join_item(**kwargs) -> WorkItem.JoinItem:
    joinItem = WorkItem.JoinItem()

    joinItem.innerColumn.tabName = kwargs["innerTable"]
    joinItem.innerColumn.colName = kwargs["innerColumn"]
    joinItem.innerColumn.colType = kwargs["innerType"]
    joinItem.innerColumn.isBase = kwargs.get("innerIsBase", False)

    joinItem.outerColumn.tabName = kwargs["outerTable"]
    joinItem.outerColumn.colName = kwargs["outerColumn"]
    joinItem.outerColumn.colType = kwargs["outerType"]
    joinItem.outerColumn.isBase = kwargs.get("outerIsBase", False)

    joinItem.outputColumn.tabName = kwargs["outputTable"]
    joinItem.outputColumn.colName = kwargs["outputColumn"]
    joinItem.outputColumn.colType = kwargs["outputType"]

    return joinItem

def create_map(**kwargs) -> WorkItem.MapItem:
    mapItem = WorkItem.MapItem()

    mapItem.inputColumn.tabName = kwargs["inputTable"]
    mapItem.inputColumn.colName = kwargs["inputColumn"]
    mapItem.inputColumn.colType = kwargs["inputType"]
    mapItem.inputColumn.isBase = kwargs.get("inputIsBase", False)

    mapItem.outputColumn.tabName = kwargs["outputTable"]
    mapItem.outputColumn.colName = kwargs["outputColumn"]
    mapItem.outputColumn.colType = kwargs["outputType"]

    mapItem.operatorType = kwargs["operatorType"]

    if "staticValue" in kwargs:
        mapItem.staticValue = kwargs["staticValue"]
    else:
        mapItem.partnerColumn.tabName = kwargs["partnerTable"]
        mapItem.partnerColumn.colName = kwargs["partnerColumn"]
        mapItem.partnerColumn.colType = kwargs["partnerType"]

    return mapItem

def create_aggregate_item(**kwargs) -> WorkItem.AggItem:
    aggregateItem = WorkItem.AggItem()

    aggregateItem.inputColumn.tabName = kwargs["inputTable"]
    aggregateItem.inputColumn.colName = kwargs["inputColumn"]
    aggregateItem.inputColumn.colType = kwargs["inputType"]
    aggregateItem.inputColumn.isBase = kwargs.get("inputIsBase", False)

    aggregateItem.outputColumn.tabName = kwargs["outputTable"]
    aggregateItem.outputColumn.colName = kwargs["outputColumn"]
    aggregateItem.outputColumn.colType = kwargs["outputType"]

    aggregateItem.aggFunc = kwargs["aggregationFunction"]

    return aggregateItem

def create_fetch_item(**kwargs) -> WorkItem.FetchItem:
    fetchItem = WorkItem.FetchItem()

    fetchItem.inputColumn.tabName = kwargs["tabName"]
    fetchItem.inputColumn.colName = kwargs["colName"]
    fetchItem.inputColumn.colType = kwargs["colType"]
    fetchItem.inputColumn.isBase = kwargs.get("inputIsBase", False)

    fetchItem.printToFile = kwargs["printToFile"] if "printToFile" in kwargs else False
    
    return fetchItem

def create_result_item(**kwargs) -> WorkItem.ResultItem:
    resultItem = WorkItem.ResultItem()
    
    resCols = []
    for tab, col in zip(kwargs["resultTables"],kwargs["resultColumns"]):
        colMsg = WorkItem.ColumnMessage()
        colMsg.tabName = tab
        colMsg.colName = col
        resCols.append(colMsg)
    resultItem.resultColumns.extend(resCols)
    
    if "resultHeader" in kwargs:
        resultItem.resultHeader.extend(kwargs["resultHeader"])
        
    if "resultIndexTable" in kwargs:
        resIdx = WorkItem.ColumnMessage()
        resIdx.tabName = kwargs["resultIndexTable"]
        resIdx.colName = kwargs["resultIndexColumn"]
        resultItem.resultIndex.CopyFrom(resIdx)
        
    resultItem.filename = kwargs["resultName"]
    
    return resultItem

def create_sort_item(**kwargs) -> WorkItem.SortItem:
    item = WorkItem.SortItem()
    
    inputCols = []
    for tabname, colname in zip(kwargs["inputTables"], kwargs["inputColumns"]):
        col = WorkItem.ColumnMessage()
        col.tabName = tabname
        col.colName = colname
        inputCols.append(col)
    item.inputColumns.extend(inputCols)
    
    if "outputTables" in kwargs:
        outputCols = []
        for tabname, colname in zip(kwargs["outputTables"], kwargs["outputColumns"]):
            col = WorkItem.ColumnMessage()
            col.tabName = tabname
            col.colName = colname
            outputCols.append(col)
        item.outputColumns.extend(outputCols)
    
    if "indexColumn" in kwargs:
        col = WorkItem.ColumnMessage()
        col.tabName = kwargs["indexTable"]
        col.colName = kwargs["indexColumn"]
        item.existingIndex.CopyFrom(col)
    
    col = WorkItem.ColumnMessage()
    col.tabName = kwargs["indexOutputTable"]
    col.colName = kwargs["indexOutputColumn"]
    item.indexOutput.CopyFrom(col)
    
    item.sortOrder.extend([order for order in kwargs["sortOrder"]])
    
    return item
    
def create_multigroup_item(**kwargs) -> WorkItem.MultiGroupItem:
    item = WorkItem.MultiGroupItem()

    groupcols = []
    if "columns" in kwargs and "tables" in kwargs:
        cols = kwargs["columns"]
        tabs = kwargs["tables"]
        coltypes = kwargs["columntypes"]
        for tabname, colname, coltype in zip(tabs, cols, coltypes):
            col = WorkItem.ColumnMessage()
            col.tabName = tabname
            col.colName = colname
            col.colType = coltype
            groupcols.append(col)
    item.groupColumns.extend(groupcols)
    col = WorkItem.ColumnMessage()
    col.tabName = kwargs["outputIndexTable"]
    col.colName = kwargs["outputIndexColumn"]
    col.colType = WorkItem.TYPE_POSLIST
    item.outputIndex.CopyFrom(col)
    
    col = WorkItem.ColumnMessage()
    col.tabName = kwargs["outputClustersTable"]
    col.colName = kwargs["outputClustersColumn"]
    col.colType = WorkItem.TYPE_POSLIST
    item.outputClusters.CopyFrom(col)
    
    if "aggregationTable" in kwargs and "aggregationColumn" in kwargs:
        col = WorkItem.ColumnMessage()
        col.tabName = kwargs["aggregationTable"]
        col.colName = kwargs["aggregationColumn"]
        col.colType = kwargs["agregationColumnType"]
        col2 = WorkItem.ColumnMessage()
        col2.tabName = kwargs["aggregationResultTable"]
        col2.colName = kwargs["aggregationResultColumn"]
        col2.colType = kwargs["agregationResultColumnType"]
        
        item.aggregationColumn.CopyFrom(col)
        item.aggregationResultColumn.CopyFrom(col2)
        
    return item


def create_connect_item(**kwargs) -> msg.TCPMessage:
    work = msg.TCPMessage(unit_type=UnitType.QUERY_PLANER, package_type=TcpPackageType.CONNECT_ACTION, src_uuid=kwargs.get("source_uuid", 0), tgt_uuid=kwargs.get("target_uuid", 0))
    citem = NetworkRequests.ConnectItem()
    citem.destinationIp = kwargs["ip"]
    citem.port = int(kwargs["port"])
    citem.action = kwargs["action"]
    citem.connectionType = kwargs["connectionType"]
    work.payload = citem.SerializeToString()
    return work

def create_configuration_item(**kwargs) -> msg.TCPMessage:
    work = msg.TCPMessage(unit_type=UnitType.QUERY_PLANER, package_type=TcpPackageType.CONFIGURATION_ACTION , src_uuid=kwargs.get("source_uuid", 0), tgt_uuid=kwargs.get("target_uuid", 0))
    citem = ConfigurationRequests.ConfigurationItem()
    citem.type = kwargs["type"]
    if citem.type == ConfigurationRequests.ConfigType.SET_WORKER:
        citem.worker_count = kwargs["worker_count"]
        
    print(citem)
    work.payload = citem.SerializeToString()
    print(work)
    return work

def create_uuid_request_item(**kwargs) -> msg.TCPMessage:
    work = msg.TCPMessage(unit_type=UnitType.QUERY_PLANER, package_type=TcpPackageType.UUID_FOR_UNIT_REQUEST, src_uuid=kwargs.get("source_uuid", 0), tgt_uuid=kwargs.get("target_uuid", 0))
    ritem = NetworkRequests.UuidForUnitRequest()
    ritem.requestedUnitType = kwargs["type"]
    work.payload = ritem.SerializeToString()
    return work
