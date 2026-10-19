#include <operators/HashJoinOperatorMat.hpp>

WorkResponse HashJoinOperatorMat::run() {
    WorkResponse response;
    response.set_planid(m_work_item.planid());
    response.set_itemid(m_work_item.itemid());
    response.set_success(true);

    if (m_work_item.returnextendedresult()) {
        response.mutable_extendedresult()->set_itemid(m_work_item.itemid());
        using namespace std::chrono;
        response.mutable_extendedresult()->set_start(duration_cast<nanoseconds>(high_resolution_clock::now().time_since_epoch()).count());
    }

    const auto joinData = m_work_item.joinmatdata();
    auto& catalog = DataCatalog::getInstance();
    auto innerColumn = catalog.getColumnByName(joinData.innercolumn().tabname(), joinData.innercolumn().colname());
    auto outerColumn = catalog.getColumnByName(joinData.outercolumn().tabname(), joinData.outercolumn().colname());

    auto fail = [&](const std::string& message) {
        response.set_info("[HashJoinOperatorMat] ERROR - " + message);
        response.set_success(false);
        LOG_ERROR("[HashJoinOperatorMat] " << message << std::endl;)
    };

    if (!innerColumn || !outerColumn) {
        fail("Could not find one of the join-key columns.");
        return response;
    }

    std::shared_ptr<Column> innerPositions;
    std::shared_ptr<Column> outerPositions;
    if (joinData.has_innerpositioncolumn()) {
        innerPositions = catalog.getColumnByName(joinData.innerpositioncolumn().tabname(), joinData.innerpositioncolumn().colname());
        if (!innerPositions) {
            fail("Could not find the inner position-list column.");
            return response;
        }
    }
    if (joinData.has_outerpositioncolumn()) {
        outerPositions = catalog.getColumnByName(joinData.outerpositioncolumn().tabname(), joinData.outerpositioncolumn().colname());
        if (!outerPositions) {
            fail("Could not find the outer position-list column.");
            return response;
        }
    }

    if (innerColumn->datatype != outerColumn->datatype) {
        fail("Join-key data types do not match.");
        return response;
    }
    if ((innerPositions && innerPositions->datatype != DataType::position_list) ||
        (outerPositions && outerPositions->datatype != DataType::position_list)) {
        fail("Index columns must be position lists.");
        return response;
    }

    uint64_t rowCount = 0;
    try {
        switch (innerColumn->datatype) {
            case DataType::uint8:
                rowCount = doHashJoin<uint8_t>(innerColumn, outerColumn, innerPositions, outerPositions);
                break;
            case DataType::int8:
                rowCount = doHashJoin<int8_t>(innerColumn, outerColumn, innerPositions, outerPositions);
                break;
            case DataType::uint16:
                rowCount = doHashJoin<uint16_t>(innerColumn, outerColumn, innerPositions, outerPositions);
                break;
            case DataType::int16:
                rowCount = doHashJoin<int16_t>(innerColumn, outerColumn, innerPositions, outerPositions);
                break;
            case DataType::uint32:
                rowCount = doHashJoin<uint32_t>(innerColumn, outerColumn, innerPositions, outerPositions);
                break;
            case DataType::int32:
                rowCount = doHashJoin<int32_t>(innerColumn, outerColumn, innerPositions, outerPositions);
                break;
            case DataType::timestamp:
            case DataType::string_enc:
            case DataType::uint64:
                rowCount = doHashJoin<uint64_t>(innerColumn, outerColumn, innerPositions, outerPositions);
                break;
            case DataType::int64:
                rowCount = doHashJoin<int64_t>(innerColumn, outerColumn, innerPositions, outerPositions);
                break;
            case DataType::f32:
            case DataType::f64:
            case DataType::position_list:
            case DataType::bitmask:
            case DataType::unknown:
                fail("Unsupported join-key data type.");
                break;
        }
    } catch (const std::exception& exception) {
        fail(exception.what());
    }

    if (m_work_item.returnextendedresult()) {
        response.mutable_extendedresult()->set_rowcount(rowCount);
        using namespace std::chrono;
        response.mutable_extendedresult()->set_end(duration_cast<nanoseconds>(high_resolution_clock::now().time_since_epoch()).count());
    }

    return response;
}
