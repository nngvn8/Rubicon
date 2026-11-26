#pragma once

#include <infrastructure/DataCatalog.hpp>
#include <infrastructure/MemTracker.hpp>
#include <operators/AbstractOperator.hpp>
#include <operators/HashJoinProber.hpp>

/**
 * @brief Join two columns via HashJoin.
 *
 */
class HashJoinOperator : public AbstractOperator {
   public:
    HashJoinOperator(WorkItem p_witem) : AbstractOperator(p_witem) {};
    virtual WorkResponse run() override;

   private:
    template <typename base_t>
    uint64_t doHashJoin(std::shared_ptr<Column> innerColumn, std::shared_ptr<Column> outerColumn, const uint64_t chunkElements = 1024 * 1024 * 4) {
        static_assert(std::is_arithmetic_v<base_t>, "[HashJoinOperator] Could not deduce base_t for WorkItem");
        auto joinData = m_work_item.joindata();

        tsl::executor<tsl::runtime::cpu> exec;
        size_t* join_result_id_a = memtrack::tracked_allocate<size_t>(exec, outerColumn->elements);
        size_t* join_result_id_b = memtrack::tracked_allocate<size_t>(exec, outerColumn->elements);

        LOG_DEBUG2("[HashJoinOperator] Starting Hash-Phase." << std::endl;)

        // Build Hash table when inner column fully available
        auto hash_table = hash_join::allocate_hash_table<base_t>(innerColumn->elements);

        innerColumn->wait_data_allocated();
        View<base_t> innerChunk(static_cast<base_t*>(innerColumn->data), chunkElements, innerColumn);

        size_t inserted = 0;
        while (true) {
            const size_t chunkSize = innerChunk.getNumberOfElements();
            hash_join::insert_chunk(hash_table, innerChunk.begin(), chunkSize, inserted);
            inserted += chunkSize;

            if (innerChunk.isLastChunk()) break;
            ++innerChunk;
        }
        LOG_DEBUG2("[HashJoinOperator] Finished Hash-Phase." << std::endl;)

        outerColumn->wait_data_allocated();
        View outerChunk = View<base_t>(static_cast<base_t*>(outerColumn->data), chunkElements, outerColumn);

        size_t join_result = 0;

        LOG_DEBUG2("[HashJoinOperator] Starting Probe-Phase." << std::endl;)
        size_t position_offset = 0;
        while (true) {
            join_result += hash_join::probe_hash_table(hash_table, outerChunk.begin(), outerChunk.getNumberOfElements(), position_offset, join_result_id_a + join_result, join_result_id_b + join_result);

            if (outerChunk.isLastChunk()) break;
            position_offset += outerChunk.getNumberOfElements();
            ++outerChunk;
        }
        LOG_DEBUG2("[HashJoinOperator] Finished Probe-Phase." << std::endl;)

        const uint64_t size_in_bytes_a = join_result * sizeof(size_t);
        const uint64_t size_in_bytes_b = join_result * sizeof(size_t);

        std::shared_ptr<Column> resColumnInner = std::make_shared<Column>(0, DataType::position_list, size_in_bytes_a, join_result, false, true);
        std::shared_ptr<Column> resColumnOuter = std::make_shared<Column>(0, DataType::position_list, size_in_bytes_b, join_result, false, true);

        // Shrink both worst-case buffers to the number of matches (also books the shrinks)
        join_result_id_a = memtrack::tracked_shrink(join_result_id_a, size_in_bytes_a);
        join_result_id_b = memtrack::tracked_shrink(join_result_id_b, size_in_bytes_b);

        resColumnInner->setDataPtr(static_cast<void*>(join_result_id_a));
        resColumnOuter->setDataPtr(static_cast<void*>(join_result_id_b));

        LOG_DEBUG1("[HashJoinOperator] My result has " << join_result << " elements." << std::endl;)
        DataCatalog::getInstance().addColumn(joinData.ioutputcolumn().tabname(), joinData.ioutputcolumn().colname(), resColumnInner);
        DataCatalog::getInstance().addColumn(joinData.ooutputcolumn().tabname(), joinData.ooutputcolumn().colname(), resColumnOuter);

        return join_result;
    }
};
