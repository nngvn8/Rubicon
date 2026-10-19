#pragma once

#include <algorithm>
#include <infrastructure/DataCatalog.hpp>
#include <operators/AbstractOperator.hpp>
#include <operators/HashJoinProber.hpp>
#include <stdexcept>
#include <vector>

/**
 * @brief Join two columns via HashJoin.
 *
 */
class HashJoinOperatorMat : public AbstractOperator {
   public:
    HashJoinOperatorMat(WorkItem p_witem) : AbstractOperator(p_witem) {};
    virtual WorkResponse run() override;

   private:
    template <typename base_t>
    static void waitForPosition(std::shared_ptr<Column> column, size_t position) {
        if (position >= column->elements) {
            throw std::out_of_range("[HashJoinOperator] Position list contains an out-of-range position.");
        }

        // Waiting for this prefix guarantees that the indirectly referenced
        // value has arrived without waiting for the complete source column.
        View<base_t> availablePrefix(static_cast<base_t*>(column->data), position + 1, column);
        availablePrefix.begin(); // actual waiting
    }

    template <typename base_t>
    static void materializePositionChunk(std::shared_ptr<Column> column, const size_t* positions, size_t positionCount, base_t* result) {
        if (positionCount == 0) return;

        // find max element in position list and wait until that much data has arrived
        const size_t largestPosition = *std::max_element(positions, positions + positionCount);
        waitForPosition<base_t>(column, largestPosition);

        // Materialize: Iteate over poslist and retrieve data from the column at poslist value
        const auto* values = static_cast<const base_t*>(column->data);
        for (size_t position = 0; position < positionCount; ++position) {
            result[position] = values[positions[position]];
        }
    }

    template <typename base_t>
    uint64_t doHashJoin(std::shared_ptr<Column> innerColumn, std::shared_ptr<Column> outerColumn,
                        const uint64_t chunkElements = 1024 * 1024 * 4) {
        return doHashJoin<base_t>(innerColumn, outerColumn, nullptr, nullptr, chunkElements);
    }

    template <typename base_t>
    uint64_t doHashJoin(std::shared_ptr<Column> innerColumn, std::shared_ptr<Column> outerColumn,
                        std::shared_ptr<Column> innerPositions, std::shared_ptr<Column> outerPositions,
                        const uint64_t chunkElements = 1024 * 1024 * 4) {
        static_assert(std::is_arithmetic_v<base_t>, "[HashJoinOperator] Could not deduce base_t for WorkItem");
        auto joinData = m_work_item.joinmatdata();
        
        // Check if position lists have type Datatype position lists
        if ((innerPositions && innerPositions->datatype != DataType::position_list) ||
            (outerPositions && outerPositions->datatype != DataType::position_list)) {
            throw std::invalid_argument("[HashJoinOperator] Internal materialization only supports position lists.");
        }

        // Set inner and outer element count based on position list or column data
        const size_t innerElements = innerPositions ? innerPositions->elements : innerColumn->elements;
        const size_t outerElements = outerPositions ? outerPositions->elements : outerColumn->elements;

        // Allocating result data for the join
        tsl::executor<tsl::runtime::cpu> exec;
        size_t* join_result_id_a = exec.allocate<size_t>(outerElements);
        size_t* join_result_id_b = exec.allocate<size_t>(outerElements);

        LOG_DEBUG2("[HashJoinOperator] Starting Hash-Phase." << std::endl;)
        innerColumn->wait_data_allocated();

        std::vector<base_t> materializedInner;
        const base_t* innerKeys = nullptr;

        // If position list for inner column has been provided
        if (innerPositions) {
            innerPositions->wait_data_allocated();
            materializedInner.resize(innerElements);

            if (innerElements != 0) {
                View<size_t> positionChunk(static_cast<size_t*>(innerPositions->data), chunkElements, innerPositions);
                size_t materialized = 0;
                while (true) {
                    
                    // Materialize one chunk of the inner column
                    const size_t positionCount = positionChunk.getNumberOfElements();
                    materializePositionChunk<base_t>(innerColumn, positionChunk.begin(), positionCount, materializedInner.data() + materialized);
                    materialized += positionCount;

                    if (positionChunk.isLastChunk()) break;
                    ++positionChunk;
                }
            }
            innerKeys = materializedInner.data();
        
        // Build the hash table directly from data provided
        } else if (innerElements != 0) {
            // Wait for the data to be available
            View<base_t> completeInner(static_cast<base_t*>(innerColumn->data), innerElements, innerColumn);
            innerKeys = completeInner.begin();
        }

        const auto hash_table = hash_join::build_hash_table(innerKeys, innerElements);
        LOG_DEBUG2("[HashJoinOperator] Finished Hash-Phase." << std::endl;)

        size_t join_result = 0;

        LOG_DEBUG2("[HashJoinOperator] Starting Probe-Phase." << std::endl;)
        size_t position_offset = 0;

        outerColumn->wait_data_allocated();
        // If position list for outer column has been provided
        if (outerPositions) {
            outerPositions->wait_data_allocated();
            std::vector<base_t> materializedOuter(std::min<size_t>(chunkElements, outerElements));

            if (outerElements != 0) {
                View<size_t> positionChunk(static_cast<size_t*>(outerPositions->data), chunkElements, outerPositions);
                while (true) {
                    
                    // One chunk at a time materialize and probe outer column
                    const size_t positionCount = positionChunk.getNumberOfElements();
                    materializePositionChunk<base_t>(outerColumn, positionChunk.begin(), positionCount, materializedOuter.data());
                    join_result += hash_join::probe_hash_table(hash_table, materializedOuter.data(), positionCount, position_offset,
                                                                join_result_id_a + join_result, join_result_id_b + join_result);
                    position_offset += positionCount;

                    if (positionChunk.isLastChunk()) break;
                    ++positionChunk;
                }
            }
        
            // Do probing based on column data directly
        } else if (outerElements != 0) {
            View<base_t> outerChunk(static_cast<base_t*>(outerColumn->data), chunkElements, outerColumn);
            while (true) {
                
                // Probe one chunk at a time
                const size_t elementCount = outerChunk.getNumberOfElements();
                join_result += hash_join::probe_hash_table(hash_table, outerChunk.begin(), elementCount, position_offset,
                                                            join_result_id_a + join_result, join_result_id_b + join_result);
                position_offset += elementCount;

                if (outerChunk.isLastChunk()) break;
                ++outerChunk;
            }
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
