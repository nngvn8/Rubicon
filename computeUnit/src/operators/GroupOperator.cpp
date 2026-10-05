
#include <fstream>
#include <numeric>
#include <operators/GroupOperator.hpp>

std::shared_ptr<Column> addResultToCatalog(void* data, size_t size_in_bytes, size_t elements, DataType type, std::string table_ident, std::string column_ident) {
    std::shared_ptr<Column> catalog_column = std::make_shared<Column>(0, type, size_in_bytes, elements, false, true);

    void* q = std::realloc(data, size_in_bytes);
    // When shrinking, realloc failure is rare but *possible*.
    // If it fails, data is still valid and you keep the larger block.
    if (q) data = q;

    catalog_column->setDataPtr(data);
    auto res = DataCatalog::getInstance().addColumn(table_ident, column_ident, catalog_column);
    if (!res) {
        return DataCatalog::getInstance().getColumnByName(table_ident, column_ident);
    }
    return catalog_column;
}

WorkResponse GroupOperator::run() {
    using idx_t = size_t;
    tsl::executor<tsl::runtime::cpu> exec;

    WorkResponse response;
    response.set_planid(m_work_item.planid());
    response.set_itemid(m_work_item.itemid());

    if (m_work_item.returnextendedresult()) {
        response.mutable_extendedresult()->set_itemid(m_work_item.itemid());
        using namespace std::chrono;
        const uint64_t startTime = duration_cast<nanoseconds>(high_resolution_clock::now().time_since_epoch()).count();
        response.mutable_extendedresult()->set_start(startTime);
    }

    const auto coldata = m_work_item.multigroupdata().groupcolumns();
    // Create a vector of all requried columns. We could also greedily sort them as they are fetched, but if one column is not present, we conduct unnecessary work.
    std::vector<std::shared_ptr<Column>> group_columns;
    for (auto& col : coldata) {
        LOG_DEBUG1("Trying to fetch Column " << col.tabname() << "." << col.colname() << std::endl;)
        group_columns.emplace_back(DataCatalog::getInstance().getColumnByName(col.tabname(), col.colname()));
        // Abort if one of the columns is unavailable
        if (!group_columns.back()) {
            LOG_ERROR("Could not fetch Column " << col.tabname() << "." << col.colname() << ", aborting group execution." << std::endl;)
            response.set_info("Could not fetch Column " + col.tabname() + "." + col.colname() + ", aborting group execution.");
            response.set_success(false);
            return response;
        }
    }

    // Create an index for the sorter. It corresponds to all columns of the table
    idx_t* intermediate_idx_ptr = exec.allocate<idx_t>(group_columns.front()->elements, 64);
    tuddbs::InMemoryColumn<size_t> idx_col(intermediate_idx_ptr, group_columns.front()->elements);
    std::iota(intermediate_idx_ptr, intermediate_idx_ptr + group_columns.front()->elements, 0);
    LOG_DEBUG1("[GroupOperator] Created dummy index with " << group_columns.front()->elements << " elements." << std::endl;)

    // The first column is sorted to get a list of clusters, i.e. groups of equal consecutive elements
    LOG_DEBUG1("Sorting first column..." << std::endl;)
    auto clusters = select_datatype_first(group_columns.front(), idx_col, response);

    // Using the pre-sorted index that we just created and the clusters from the first column, the cluster list is refined on each
    // subsequent column. That is, only cluster ranges are sub-sorted according to the value in the currently observed column.
    for (int i = 1; i < coldata.size(); ++i) {
        LOG_DEBUG1("Sorting column " << i + 1 << "..." << std::endl;)
        select_datatype_consecutive(group_columns[i], idx_col, clusters, response);
    }

    // This column will hold the lengths of the cluster, i.e. it run-length encodes on where to look in the sorted index
    // (intermediate_idx_ptr) for the corresponding elemnents
    size_t* intermediate_cluster_ptr = exec.allocate<size_t>(group_columns.front()->elements, 64);
    tuddbs::InMemoryColumn<size_t> cluster_col(intermediate_cluster_ptr, group_columns.front()->elements);

    // Write pointer to the RLE-cluster-length column
    auto cluster_write_ptr = cluster_col.begin();
    size_t current_cluster_idx = 0;
    // We do not know in advance, how many 1-clusters we have to correctly pre-allocate the cluster output column. Thus we have
    // to count them now and set the value in the DataCatalog column. This is a bit wasteful, since we do not reallocate for future
    // accelerator-compatibility.
    size_t cluster_entries = 0;
    while (!clusters.empty()) {
        auto cl = clusters.front();
        clusters.pop_front();
        // Since 1-length clusters are omitted during processing, we have to manually insert them here. I.e., *every* index before the current clusters' len are clusters of length 1
        cluster_entries += cl.start - current_cluster_idx;
        for (size_t i = current_cluster_idx; i < cl.start; ++i, ++current_cluster_idx) {
            // LOG_DEBUG2(current_cluster_idx << "\t1\t" << static_cast<uint64_t*>(group_columns.front()->data)[intermediate_idx_ptr[current_cluster_idx]] << std::endl;)
            *(cluster_write_ptr++) = 1;
        }
        *(cluster_write_ptr++) = cl.len;
        current_cluster_idx += cl.len;
        cluster_entries++;
        // LOG_DEBUG2(cl.start << "\t" << cl.len << "\t" << static_cast<uint64_t*>(group_columns.front()->data)[intermediate_idx_ptr[cl.start]] << std::endl;)
    }
    // Since 1-Clusters can also happen after the last stored Cluster, we have to fill the end as well
    cluster_entries += group_columns.front()->elements - current_cluster_idx;
    for (; current_cluster_idx < group_columns.front()->elements; ++current_cluster_idx) {
        // LOG_DEBUG2(current_cluster_idx << "\t1\t" << static_cast<uint64_t*>(group_columns.front()->data)[intermediate_idx_ptr[current_cluster_idx]] << std::endl;)
        *(cluster_write_ptr++) = 1;
    }

    // This is a position list, that contains the first occurrence of a group element
    idx_t* group_extends_ptr = exec.allocate<idx_t>(cluster_entries, 64);
    idx_t* group_extends_write_ptr = group_extends_ptr;
    size_t index_offset_accessor = 0;
    for ( auto it = cluster_col.cbegin(); it != cluster_col.cbegin() + cluster_entries; ++it, ++group_extends_write_ptr ) {
        *group_extends_write_ptr = intermediate_idx_ptr[index_offset_accessor];
        index_offset_accessor += *it;
    }

    /* Store the sorted index inside the DataCatalog (Backward Compatiblity) */
    LOG_DEBUG1("[GroupOperator] Trying to add the group extends index (Backward Compatiblity): " << m_work_item.multigroupdata().outputindex().tabname() << "." << m_work_item.multigroupdata().outputindex().colname() + "_ext" << std::endl;)
    addResultToCatalog(group_extends_ptr, cluster_entries * sizeof(idx_t), cluster_entries, DataType::position_list, m_work_item.multigroupdata().outputindex().tabname(), m_work_item.multigroupdata().outputindex().colname() + "_ext");
    
    /* Store the sorted index inside the DataCatalog (Optimizer Version) */
    LOG_DEBUG1("[GroupOperator] Trying to add the group extends index (Optimizer Version): " << m_work_item.multigroupdata().outputindex().tabname() << "." << m_work_item.multigroupdata().outputindex().colname() << std::endl;)
    addResultToCatalog(group_extends_ptr, cluster_entries * sizeof(idx_t), cluster_entries, DataType::position_list, m_work_item.multigroupdata().outputindex().tabname(), m_work_item.multigroupdata().outputindex().colname());

    /* Store the (full) sorted index inside the DataCatalog */
    LOG_DEBUG1("[GroupOperator] Trying to add the sorted index: " << m_work_item.multigroupdata().outputindex().tabname() << "." << m_work_item.multigroupdata().outputindex().colname() << std::endl;)
    auto idx_catalog_column = addResultToCatalog(idx_col.begin(), idx_col.count() * sizeof(idx_t), idx_col.count(), DataType::position_list, m_work_item.multigroupdata().outputindex().tabname(), m_work_item.multigroupdata().outputindex().colname() + "_full");

    /* Store the calculated clusters inside the DataCatalog */
    LOG_DEBUG1("[GroupOperator] Trying to add the clusters: " << m_work_item.multigroupdata().outputclusters().tabname() << "." << m_work_item.multigroupdata().outputclusters().colname() << std::endl;)
    auto cluster_catalog_column = addResultToCatalog(cluster_col.begin(), cluster_entries * sizeof(size_t), cluster_entries, DataType::position_list, m_work_item.multigroupdata().outputclusters().tabname(), m_work_item.multigroupdata().outputclusters().colname());

    /* Is an aggregation, i.e. sum, based on the clusters necessary? */
    if (m_work_item.multigroupdata().has_aggregationcolumn()) {
        uint64_t* aggregation_ptr = exec.allocate<uint64_t>(cluster_entries, 64);
        tuddbs::InMemoryColumn<uint64_t> cluster_aggregation_col(aggregation_ptr, cluster_entries);
        memset( aggregation_ptr, 0, cluster_entries * sizeof(uint64_t) );
        auto aggregation_column = DataCatalog::getInstance().getColumnByName(m_work_item.multigroupdata().aggregationcolumn().tabname(), m_work_item.multigroupdata().aggregationcolumn().colname());
        select_agregation_type(aggregation_column, idx_catalog_column, cluster_catalog_column, cluster_aggregation_col, response);
        LOG_DEBUG1("[GroupOperator] Trying to add the aggregated result (Backward Compatibility): " << m_work_item.multigroupdata().aggregationresultcolumn().tabname() << "." << m_work_item.multigroupdata().aggregationresultcolumn().colname() + "_agg" << std::endl;)
        addResultToCatalog(cluster_aggregation_col.begin(), cluster_entries * sizeof(uint64_t), cluster_entries, DataType::uint64, m_work_item.multigroupdata().aggregationresultcolumn().tabname(), m_work_item.multigroupdata().aggregationresultcolumn().colname() + "_agg");
        LOG_DEBUG1("[GroupOperator] Trying to add the aggregated result (Optimizer Version): " << m_work_item.multigroupdata().aggregationresultcolumn().tabname() << "." << m_work_item.multigroupdata().aggregationresultcolumn().colname() << std::endl;)
        addResultToCatalog(cluster_aggregation_col.begin(), cluster_entries * sizeof(uint64_t), cluster_entries, DataType::uint64, m_work_item.multigroupdata().aggregationresultcolumn().tabname(), m_work_item.multigroupdata().aggregationresultcolumn().colname());
    }

    response.set_info("[GroupOperator] You wanted me to group by " + std::to_string(coldata.size()) + " columns. I found " + std::to_string(cluster_entries) + " clusters.");
    response.set_success(true);

    if (m_work_item.returnextendedresult()) {
        response.mutable_extendedresult()->set_rowcount(cluster_entries);
        using namespace std::chrono;
        const uint64_t endTime = duration_cast<nanoseconds>(high_resolution_clock::now().time_since_epoch()).count();
        response.mutable_extendedresult()->set_end(endTime);
    }

    return response;
}