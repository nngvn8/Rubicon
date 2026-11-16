
#include <operators/SortOperator.hpp>
#include <infrastructure/MemTracker.hpp>
#include <numeric>

WorkResponse SortOperator::run() {
    WorkResponse response;
    response.set_planid(m_work_item.planid());
    response.set_itemid(m_work_item.itemid());
    response.set_success(true);

    if (m_work_item.returnextendedresult()) {
        response.mutable_extendedresult()->set_itemid(m_work_item.itemid());
        using namespace std::chrono;
        const uint64_t startTime = duration_cast<nanoseconds>(high_resolution_clock::now().time_since_epoch()).count();
        response.mutable_extendedresult()->set_start(startTime);
    }

    const auto coldata = m_work_item.sortdata().inputcolumns();
    // Create a vector of all requried columns. We could also greedily sort them as they are fetched, but if one column is not present, we conduct unnecessary work.
    std::vector<std::shared_ptr<Column>> sort_columns;
    for (auto& col : coldata) {
        LOG_DEBUG1("[SortOperator] Trying to fetch Column " << col.tabname() << "." << col.colname() << std::endl;)
        sort_columns.emplace_back(DataCatalog::getInstance().getColumnByName(col.tabname(), col.colname()));
        // Abort if one of the columns is unavailable
        if (!sort_columns.back()) {
            LOG_ERROR("[SortOperator] Could not fetch Column " << col.tabname() << "." << col.colname() << ", aborting group execution." << std::endl;)
            response.set_info("Could not fetch Column " + col.tabname() + "." + col.colname() + ", aborting group execution.");
            response.set_success(false);
            return response;
        }
    }

    tsl::executor<tsl::runtime::cpu> exec;
    const size_t idx_count = sort_columns[0]->elements;
    size_t* sort_idx = memtrack::tracked_allocate<size_t>(exec, idx_count, 64);
    tuddbs::InMemoryColumn<size_t> idx_col(sort_idx, idx_count);
    if (m_work_item.sortdata().has_existingindex()) {
        const auto idxinfo = m_work_item.sortdata().existingindex();
        LOG_DEBUG1("[SortOperator] Trying to fetch Index Column " << idxinfo.tabname() << "." << idxinfo.colname() << std::endl;)
        auto catalog_idx = DataCatalog::getInstance().getColumnByName(idxinfo.tabname(), idxinfo.colname());
        memcpy(sort_idx, catalog_idx->data, idx_count * sizeof(size_t));
    } else {
        std::iota(sort_idx, sort_idx + idx_count, 0);
    }

    // The first column is sorted to get a list of clusters, i.e. groups of equal consecutive elements
    LOG_DEBUG1("Sorting first column..." << std::endl;)
    std::deque<tuddbs::Cluster> clusters;
    if (m_work_item.sortdata().sortorder().at(0)) {
        clusters = select_datatype_first<tuddbs::TSL_SORT_ORDER::ASC>(sort_columns.front(), idx_col, response);
    } else {
        clusters = select_datatype_first<tuddbs::TSL_SORT_ORDER::DESC>(sort_columns.front(), idx_col, response);
    }

    // Using the pre-sorted index that we just created and the clusters from the first column, the cluster list is refined on each
    // subsequent column. That is, only cluster ranges are sub-sorted according to the value in the currently observed column.
    for (int i = 1; i < coldata.size(); ++i) {
        LOG_DEBUG1("Sorting column " << i + 1 << "..." << std::endl;)
        if (m_work_item.sortdata().sortorder().at(i)) {
            select_datatype_consecutive<tuddbs::TSL_SORT_ORDER::ASC>(sort_columns[i], idx_col, clusters, response);
        } else {
            select_datatype_consecutive<tuddbs::TSL_SORT_ORDER::DESC>(sort_columns[i], idx_col, clusters, response);
        }
    }

    std::shared_ptr<Column> catalog_column = std::make_shared<Column>(0, DataType::position_list, idx_count * sizeof(size_t), idx_count, false, true);
    catalog_column->setDataPtr(sort_idx);
    const std::string& table_ident = m_work_item.sortdata().indexoutput().tabname();
    const std::string& column_ident = m_work_item.sortdata().indexoutput().colname();
    auto res = DataCatalog::getInstance().addColumn(table_ident, column_ident, catalog_column);

    if (m_work_item.returnextendedresult()) {
        response.mutable_extendedresult()->set_rowcount(idx_count);
        using namespace std::chrono;
        const uint64_t endTime = duration_cast<nanoseconds>(high_resolution_clock::now().time_since_epoch()).count();
        response.mutable_extendedresult()->set_end(endTime);
    }

    return response;
}