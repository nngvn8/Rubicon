#pragma once

#include <infrastructure/DataCatalog.hpp>
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
        size_t* join_result_id_a = exec.allocate<size_t>(outerColumn->elements);
        size_t* join_result_id_b = exec.allocate<size_t>(outerColumn->elements);

        LOG_DEBUG2("[HashJoinOperator] Starting Hash-Phase." << std::endl;)
        innerColumn->wait_data_allocated();

        // Build Hash table when inner column fully available
        View<base_t> innerChunk(static_cast<base_t*>(innerColumn->data), innerColumn->elements, innerColumn);
        const auto* inner_keys = innerChunk.begin();
        const auto hash_table = hash_join::build_hash_table(inner_keys, innerChunk.getNumberOfElements());
        LOG_DEBUG2("[HashJoinOperator] Finished Hash-Phase." << std::endl;)

        View outerChunk = View<base_t>(static_cast<base_t*>(outerColumn->data), chunkElements, outerColumn);

        size_t join_result = 0;

        LOG_DEBUG2("[HashJoinOperator] Starting Probe-Phase." << std::endl;)
        size_t position_offset = 0;
        while (true) {
            join_result += hash_join::probe_hash_table(hash_table, outerChunk.begin(), outerChunk.getNumberOfElements(), position_offset, join_result_id_a + join_result, join_result_id_b + join_result);
            if (outerChunk.isLastChunk()) {
                break;
            }
            position_offset += outerChunk.getNumberOfElements();
            outerChunk++;
        }
        LOG_DEBUG2("[HashJoinOperator] Finished Probe-Phase." << std::endl;)

        const uint64_t size_in_bytes_a = join_result * sizeof(size_t);
        const uint64_t size_in_bytes_b = join_result * sizeof(size_t);

        std::shared_ptr<Column> resColumnInner = std::make_shared<Column>(0, DataType::position_list, size_in_bytes_a, join_result, false, true);
        std::shared_ptr<Column> resColumnOuter = std::make_shared<Column>(0, DataType::position_list, size_in_bytes_b, join_result, false, true);

        {
            void* q = std::realloc(join_result_id_a, size_in_bytes_a);
            // When shrinking, realloc failure is rare but *possible*.
            // If it fails, join_result_id_a is still valid and you keep the larger block.
            if (q) join_result_id_a = static_cast<size_t*>(q);
        }

        {
            void* q = std::realloc(join_result_id_b, size_in_bytes_b);
            // When shrinking, realloc failure is rare but *possible*.
            // If it fails, join_result_id_b is still valid and you keep the larger block.
            if (q) join_result_id_b = static_cast<size_t*>(q);
        }

        resColumnInner->setDataPtr(static_cast<void*>(join_result_id_a));
        resColumnOuter->setDataPtr(static_cast<void*>(join_result_id_b));

        LOG_DEBUG1("[HashJoinOperator] My result has " << join_result << " elements." << std::endl;)
        DataCatalog::getInstance().addColumn(joinData.ioutputcolumn().tabname(), joinData.ioutputcolumn().colname(), resColumnInner);
        DataCatalog::getInstance().addColumn(joinData.ooutputcolumn().tabname(), joinData.ooutputcolumn().colname(), resColumnOuter);

        return join_result;
    }
};
