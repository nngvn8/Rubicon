#pragma once

#include <algorithms/dbops/union/union.hpp>
#include <algorithms/utils/hinting.hpp>  // SIMDOps
#include <datastructures/column.hpp>     // SIMDOps
#include <infrastructure/DataCatalog.hpp>
#include <operators/AbstractOperator.hpp>

/**
 * @brief Given two input columns, it returns all elements, that exist in either column.
 *
 */
class SetUnionOperator : public AbstractOperator {
   public:
    SetUnionOperator(WorkItem p_witem) : AbstractOperator(p_witem) {};

    virtual WorkResponse run() override;

   private:
    template <class IdxListType>
    uint64_t select_ise(std::shared_ptr<Column> col1_struct, std::shared_ptr<Column> col2_struct) {
        std::cout << "[SetUnionOperator] My SIMD Ext: " << m_work_item.simdext() << std::endl;
        switch (m_work_item.simdext()) {
#ifdef TSL_CONTAINS_SSE
            case SIMDISE::SIMD_SSE: {
                std::cout << "[SetUnionOperator] Choosing SSE." << std::endl;
                using ps = tsl::simd<uint8_t, tsl::sse>;
                return do_union<ps, IdxListType>(col1_struct, col2_struct);
            } break;
#endif
#ifdef TSL_CONTAINS_AVX2
            case SIMDISE::SIMD_AVX2: {
                std::cout << "[SetUnionOperator] Choosing AVX2." << std::endl;
                using ps = tsl::simd<uint8_t, tsl::avx2>;
                return do_union<ps, IdxListType>(col1_struct, col2_struct);
            } break;
#endif
#ifdef TSL_CONTAINS_AVX512
            case SIMDISE::SIMD_AVX512: {
                std::cout << "[SetUnionOperator] Choosing AVX512." << std::endl;
                using ps = tsl::simd<uint8_t, tsl::avx512>;
                return do_union<ps, IdxListType>(col1_struct, col2_struct);
            } break;
#endif
#ifdef TSL_CONTAINS_NEON
            case SIMDISE::SIMD_ARMNEON: {
                std::cout << "[SetUnionOperator] Choosing ARM_NEON." << std::endl;
                using ps = tsl::simd<uint8_t, tsl::neon>;
                return do_union<ps, IdxListType>(col1_struct, col2_struct);
            } break;
#endif
            case SIMDISE::SIMD_SCALAR: {
                std::cout << "[SetUnionOperator] Choosing Scalar." << std::endl;
                using ps = tsl::simd<uint8_t, tsl::scalar>;
                return do_union<ps, IdxListType>(col1_struct, col2_struct);
            } break;
            default: {
                std::cout << "[SetUnionOperator] Choosing executor style." << std::endl;
                using cpu_executor = tsl::executor<tsl::runtime::cpu>;
                using ps = tsl::simd<uint8_t, typename tsl::runtime::cpu::max_width_extension_t>;
                return do_union<ps, IdxListType>(col1_struct, col2_struct);
            }
        }
    }

    template <class SimdStyle, class IdxListType>
    uint64_t do_union(std::shared_ptr<Column> col1_struct, std::shared_ptr<Column> col2_struct, const uint64_t chunkElements = 1024) {
        using HS = tuddbs::OperatorHintSet<IdxListType>;
        SetOperationItem setData = m_work_item.setdata();

        tuddbs::Union<SimdStyle, HS> set_union;

        using cpu_executor = tsl::executor<tsl::runtime::cpu>;
        cpu_executor exec;
        typename SimdStyle::base_type* res_ptr = memtrack::tracked_allocate<typename SimdStyle::base_type>(exec, col1_struct->elements, 64);

        tuddbs::InMemoryColumn<typename SimdStyle::base_type> res_col(res_ptr, col1_struct->elements);

        col1_struct->wait_data_allocated();
        col2_struct->wait_data_allocated();
        View chunk1 = View<typename SimdStyle::base_type>(static_cast<SimdStyle::base_type*>(col1_struct->data), chunkElements, col1_struct);
        View chunk2 = View<typename SimdStyle::base_type>(static_cast<SimdStyle::base_type*>(col2_struct->data), chunkElements, col2_struct);

        size_t offset = 0;

        LOG_DEBUG1("[SetUnionOperator] C1 Cnt: " << col1_struct->elements << " C2 Cnt: " << col2_struct->elements << std::endl;)
        while (true) {
            tuddbs::InMemoryColumn<typename SimdStyle::base_type> col1(chunk1.begin(), chunk1.getNumberOfElements());
            tuddbs::InMemoryColumn<typename SimdStyle::base_type> col2(chunk2.begin(), chunk2.getNumberOfElements());

            auto res_start = res_col.begin() + offset;

            auto res_end = set_union(res_start, col1.cbegin(), col1.cend(), col2.begin());
            offset += set_union.byte_count(res_start, res_end);

            if (chunk1.isLastChunk() && chunk2.isLastChunk()) {
                break;
            } else if (chunk1.isLastChunk() || chunk2.isLastChunk()) {
                LOG_ERROR("[SetUnionOperator] ERROR - Chunk sizes do not match." << std::endl;)
                return 0;
            }

            ++chunk1;
            ++chunk2;
        }

        std::shared_ptr<Column> resColumn = std::make_shared<Column>(0, DataType::bitmask, offset * sizeof(typename SimdStyle::base_type), offset, false, true);
        resColumn->setDataPtr(static_cast<void*>(res_ptr));

        LOG_DEBUG1("[SetUnionOperator] Result size: " << resColumn->elements << " elements." << std::endl;)
        DataCatalog::getInstance().addColumn(setData.outputcolumn().tabname(), setData.outputcolumn().colname(), resColumn);

        return offset;
    }

    uint64_t do_union_pl(std::shared_ptr<Column> col1_struct, std::shared_ptr<Column> col2_struct, const uint64_t chunkElements = 1024) {
        col1_struct->wait_data_allocated();
        col2_struct->wait_data_allocated();
        
        View chunk1 = View<uint64_t>(static_cast<uint64_t*>(col1_struct->data), chunkElements, col1_struct);
        View chunk2 = View<uint64_t>(static_cast<uint64_t*>(col2_struct->data), chunkElements, col2_struct);

        std::vector<uint64_t> out;
        out.reserve(col1_struct->elements + col2_struct->elements);

        auto it1 = chunk1.begin();
        auto it2 = chunk2.begin();

        while (true) {
            if (it1 == chunk1.end()) {
                if (chunk1.isLastChunk()) break;
                ++chunk1;
                it1 = chunk1.begin();
            }
            if (it2 == chunk2.end()) {
                if (chunk2.isLastChunk()) break;
                ++chunk2;
                it2 = chunk2.begin();
            }

            if (*it1 < *it2) {
                out.push_back(*it1);
                ++it1;
            } else if (*it2 < *it1) {
                out.push_back(*it2);
                ++it2;
            } else {
                // Equal - add once, advance both
                out.push_back(*it1);
                ++it1;
                ++it2;
            }
        }

        // Drain remaining elements from whichever column isn't exhausted
        while (true) {
            for (; it1 != chunk1.end(); ++it1) {
                out.push_back(*it1);
            }
            if (chunk1.isLastChunk()) break;
            ++chunk1;
            it1 = chunk1.begin();
        }

        while (true) {
            for (; it2 != chunk2.end(); ++it2) {
                out.push_back(*it2);
            }
            if (chunk2.isLastChunk()) break;
            ++chunk2;
            it2 = chunk2.begin();
        }

        using cpu_executor = tsl::executor<tsl::runtime::cpu>;
        cpu_executor exec;
        uint64_t* res_ptr = memtrack::tracked_allocate<uint64_t>(exec, out.size(), 64);
        std::memcpy(res_ptr, out.data(), out.size() * sizeof(uint64_t));
        std::shared_ptr<Column> resColumn = std::make_shared<Column>(0, DataType::position_list, out.size() * sizeof(uint64_t), out.size(), false, true);
        resColumn->setDataPtr(static_cast<void*>(res_ptr));

        LOG_DEBUG1("[SetUnionOperator] PositionList Result size: " << resColumn->elements << " elements." << std::endl;)
        SetOperationItem setData = m_work_item.setdata();
        DataCatalog::getInstance().addColumn(setData.outputcolumn().tabname(), setData.outputcolumn().colname(), resColumn);

        return out.size();
    }
};