#pragma once

#include <algorithms/dbops/materialize/materialize.hpp>  // SIMDOps
#include <algorithms/utils/hinting.hpp>        // SIMDOps
#include <datastructures/column.hpp>           // SIMDOps
#include <infrastructure/DataCatalog.hpp>
#include <operators/AbstractOperator.hpp>

/**
 * @brief Reduce an input column, based on a given position list or bitmask. The result column contains only the values at matching positions.
 *
 */
class MaterializeOperator : public AbstractOperator {
   public:
    MaterializeOperator(WorkItem p_witem) : AbstractOperator(p_witem){};
    virtual WorkResponse run() override;

    template <class _SimdStyle, class HintSet, typename idx_type>
    uint64_t do_materialize_bm(std::shared_ptr<Column> column, std::shared_ptr<Column> idx, const uint64_t chunkElements = 1024 * 1024 * 4) {
        using MaterializeImpl = tuddbs::Materialize<_SimdStyle, HintSet>;
        using base_t = _SimdStyle::base_type;

        tsl::executor<tsl::runtime::cpu> exec;
        base_t* result_ptr = memtrack::tracked_allocate<base_t>(exec, column->elements, 64);
        tuddbs::InMemoryColumn<base_t> res_col(result_ptr, column->elements);

        const size_t elements_per_byte = _SimdStyle::vector_element_count() < CHAR_BIT ? _SimdStyle::vector_element_count() : CHAR_BIT;

        column->wait_data_allocated();
        idx->wait_data_allocated();
        View chunkCol = View<base_t>(static_cast<base_t*>(column->data), chunkElements, column);
        View chunkIdx = View<idx_type>(static_cast<idx_type*>(idx->data), chunkElements / elements_per_byte, idx);

        uint64_t offset = 0;

        MaterializeImpl simdops_materialize;

        LOG_DEBUG1("--- MaterializeOperator Result start" << std::endl;)
        LOG_DEBUG1("[MaterializeOperator] Column elements: " << column->elements << " Index elements: " << idx->elements << std::endl;)
        auto const res_start = res_col.begin();
        auto res_current = res_start;
        while (true) {
            tuddbs::InMemoryColumn<base_t> data_col(chunkCol.begin(), chunkCol.getNumberOfElements());
            tuddbs::InMemoryColumn<idx_type> idx_col(chunkIdx.begin(), chunkIdx.getNumberOfElements());

            res_current = simdops_materialize(res_current, data_col.begin(), data_col.end(), idx_col.begin(), idx_col.end());

            if (chunkCol.isLastChunk() && chunkIdx.isLastChunk()) {
                break;
            } else if (chunkCol.isLastChunk() || chunkIdx.isLastChunk()) {
                LOG_ERROR("[MaterializeOperator] ERROR - Chunk sizes do not match." << std::endl;)
            }

            chunkCol++;
            chunkIdx++;
        }
        offset = res_current - res_start;
        LOG_DEBUG1("--- MaterializeOperator Result End" << std::endl;)

        const uint64_t size_in_bytes = offset * sizeof(base_t);

        std::shared_ptr<Column> resColumn = std::make_shared<Column>(0, column->datatype, size_in_bytes, offset, false, true);

        // Shrink the worst-case buffer to the actual result (also books the shrink)
        result_ptr = memtrack::tracked_shrink(result_ptr, size_in_bytes);

        resColumn->setDataPtr(static_cast<void*>(result_ptr));
        if (column->datatype == DataType::string_enc) {
            resColumn->initDictionary(column->dictionaryEncoding);
        }

        LOG_DEBUG1("[MaterializeOperator] Result size for column <" << m_work_item.materializedata().outputcolumn().tabname() << "." << m_work_item.materializedata().outputcolumn().colname() << ">: " << resColumn->elements << " elements." << std::endl;)
        DataCatalog::getInstance().addColumn(m_work_item.materializedata().outputcolumn().tabname(), m_work_item.materializedata().outputcolumn().colname(), resColumn);

        return offset;
    }

    template <typename base_t>
    uint64_t do_materialize_pl(std::shared_ptr<Column> column, std::shared_ptr<Column> idx, const uint64_t chunkElements = 1024 * 1024 * 4) {
        static_assert(std::is_arithmetic_v<base_t>, "[HashJoinOperator] Could not deduce base_t for WorkItem");

        tsl::executor<tsl::runtime::cpu> exec;

        base_t* result_ptr = memtrack::tracked_allocate<base_t>(exec, idx->elements, 64);

        size_t* idx_ptr = static_cast<size_t*>(idx->data);

        column->wait_data_allocated();
        idx->wait_data_allocated();
        View chunkCol = View<base_t>(static_cast<base_t*>(column->data), column->elements, column);
        View chunkIdx = View<size_t>(static_cast<size_t*>(idx->data), idx->elements, idx);

        base_t* chunkColPtr = chunkCol.begin();

        size_t offset = 0;
        for(size_t* ptr = chunkIdx.begin(); ptr < chunkIdx.end(); ++ptr, ++offset) {
            result_ptr[offset] = chunkColPtr[*ptr];
        }

        std::shared_ptr<Column> resColumn = std::make_shared<Column>(0, column->datatype, idx->elements * sizeof(base_t), idx->elements, false, true);
        resColumn->setDataPtr(static_cast<void*>(result_ptr));
        if (column->datatype == DataType::string_enc) {
            resColumn->initDictionary(column->dictionaryEncoding);
        }

        LOG_DEBUG1("[MaterializeOperator] Result size for column <" << m_work_item.materializedata().outputcolumn().tabname() << "." << m_work_item.materializedata().outputcolumn().colname() << ">: " << resColumn->elements << " elements." << std::endl;)
        DataCatalog::getInstance().addColumn(m_work_item.materializedata().outputcolumn().tabname(), m_work_item.materializedata().outputcolumn().colname(), resColumn);

        return idx->elements;
    }

    template <typename base_t>
    uint64_t select_index_type(std::shared_ptr<Column> column, std::shared_ptr<Column> idx, const uint64_t chunkElements = 1024 * 1024 * 4) {
        using ps = tsl::simd<base_t, typename tsl::runtime::cpu::max_width_extension_t>;
        switch (idx->datatype) {
            case DataType::bitmask: {
                using idx_type = ps::imask_type;
                using HS = tuddbs::OperatorHintSet<tuddbs::hints::intermediate::bit_mask>;
                return do_materialize_bm<ps, HS, idx_type>(column, idx, chunkElements);
            } break;
            case DataType::position_list: {
                return do_materialize_pl<base_t>(column, idx, chunkElements);
            } break;
            default: {
                LOG_ERROR("[MaterializeOperator] ERROR - unkown index type given: " << static_cast<int>(idx->datatype) << std::endl;)
            }
        }
    }
};