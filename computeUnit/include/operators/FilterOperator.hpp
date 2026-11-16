#pragma once

#include <algorithms/dbops/filter/filter.hpp>
#include <algorithms/utils/hinting.hpp>  // SIMDOps
#include <datastructures/column.hpp>     // SIMDOps
#include <infrastructure/DataCatalog.hpp>
#include <infrastructure/MemTracker.hpp>
#include <operators/AbstractOperator.hpp>

/**
 * @brief Iterate over a column and check the values against one or two filter predicates.
 *
 */
class FilterOperator : public AbstractOperator {
   public:
    FilterOperator(WorkItem p_witem) : AbstractOperator(p_witem){};
    virtual WorkResponse run() override;

   private:
    uint64_t doBetweenFilterOnEnc(std::shared_ptr<Column> column, const uint64_t chunkElements = 1024 * 1024 * 4);
    uint64_t doInFilterOnEnc(std::shared_ptr<Column> column, const uint64_t chunkElements = 1024 * 1024 * 4);
    uint64_t doLikeFilterOnEnc(std::shared_ptr<Column> column, const uint64_t chunkElements = 1024 * 1024 * 4);

    template <typename base_t, class FilterImpl, typename CtorType = typename FilterImpl::CTorParamTupleT>
    uint64_t doFilter(std::shared_ptr<Column> column, const uint64_t chunkElements = 1024 * 1024 * 4, std::enable_if_t<(std::tuple_size_v<CtorType> == 1), CtorType> = {}) {
        static_assert(std::is_arithmetic_v<base_t>, "[FilterOperator] Could not deduce base_t for WorkItem");
        auto filterData = m_work_item.filterdata();

        using intermediate_t = FilterImpl::ResultType;
        using cpu_executor = tsl::executor<tsl::runtime::cpu>;
        cpu_executor exec;
        intermediate_t* res_ptr = memtrack::tracked_allocate<intermediate_t>(exec, column->elements, 64);
        tuddbs::InMemoryColumn<intermediate_t> res_col(res_ptr, column->elements);

        column->wait_data_allocated();
        View chunk = View<base_t>(static_cast<base_t*>(column->data), chunkElements, column);

        uint64_t offset = 0;

        base_t filterPredicate;

        if constexpr (std::is_integral_v<base_t>) {
            filterPredicate = static_cast<base_t>(filterData.filtervalue().Get(0).intval().value());
        } else {  // if constexpr (std::is_floating_point_v<base_t>) {
            filterPredicate = static_cast<base_t>(filterData.filtervalue().Get(0).floatval().value());
        }

        LOG_DEBUG1("[FilterOperator] My filter Value: " << filterPredicate << std::endl;)
        FilterImpl simdops_scan(filterPredicate);

        uint64_t pos_list_offset = 0;

        while (true) {
            tuddbs::InMemoryColumn<base_t> data_col(chunk.begin(), chunk.getNumberOfElements());
            auto res_start = res_col.begin() + offset;
            if constexpr (FilterImpl::ProducesBitmask) {
                auto res_end = simdops_scan(res_start, data_col.cbegin(), data_col.cend());
                offset += res_end - res_start;
            } else {
                auto res_end = simdops_scan(res_start, data_col.cbegin(), data_col.cend(), pos_list_offset);
                offset += res_end - res_start;
            }

            if (chunk.isLastChunk()) {
                break;
            }

            pos_list_offset += chunk.getNumberOfElements();
            chunk++;
        }

        const uint64_t size_in_bytes = offset * sizeof(intermediate_t);

        std::shared_ptr<Column> resColumn = std::make_shared<Column>(0, DataType::unknown, size_in_bytes, offset, false, true);

        if constexpr (FilterImpl::ProducesBitmask) {
            LOG_DEBUG1("[FilterOperator::doFilter] Producing Bitmask" << std::endl;)
            resColumn->datatype = DataType::bitmask;
        } else {
            LOG_DEBUG1("[FilterOperator::doFilter] Producing PositionList with " << offset << " elements and " << size_in_bytes << " Bytes." << std::endl;)
            resColumn->datatype = DataType::position_list;

            // Shrink the worst-case buffer to the actual result (also books the shrink)
            res_ptr = memtrack::tracked_shrink(res_ptr, size_in_bytes);
        }
        
        resColumn->setDataPtr(static_cast<void*>(res_ptr));

        LOG_DEBUG1("[FilterOperator] My result has " << resColumn->elements << " elements." << std::endl;)
        DataCatalog::getInstance().addColumn(filterData.outputcolumn().tabname(), filterData.outputcolumn().colname(), resColumn);

        return offset;
    }

    template <typename base_t, class FilterImpl, typename CtorType = typename FilterImpl::CTorParamTupleT>
    uint64_t doFilter(std::shared_ptr<Column> column, const uint64_t chunkElements = 1024 * 1024 * 4, std::enable_if_t<(std::tuple_size_v<CtorType> == 2), CtorType> = {}) {
        static_assert(std::is_arithmetic_v<base_t>, "[FilterOperator] Could not deduce base_t for WorkItem");
        auto filterData = m_work_item.filterdata();

        using intermediate_t = FilterImpl::ResultType;
        using cpu_executor = tsl::executor<tsl::runtime::cpu>;
        cpu_executor exec;
        intermediate_t* res_ptr = memtrack::tracked_allocate<intermediate_t>(exec, column->elements, 64);
        tuddbs::InMemoryColumn<intermediate_t> res_col(res_ptr, column->elements);

        column->wait_data_allocated();
        View chunk = View<base_t>(static_cast<base_t*>(column->data), chunkElements, column);

        uint64_t offset = 0;

        base_t filterPredicate_lower, filterPredicate_upper;

        if constexpr (std::is_integral_v<base_t>) {
            filterPredicate_lower = static_cast<base_t>(filterData.filtervalue().Get(0).intval().value());
            filterPredicate_upper = static_cast<base_t>(filterData.filtervalue().Get(1).intval().value());
        } else {  // if constexpr (std::is_floating_point_v<base_t>) {
            filterPredicate_lower = static_cast<base_t>(filterData.filtervalue().Get(0).floatval().value());
            filterPredicate_upper = static_cast<base_t>(filterData.filtervalue().Get(1).floatval().value());
        }

        LOG_DEBUG1("[FilterOperator] My filter Value: " << filterPredicate_lower << " " << filterPredicate_upper << std::endl;)
        FilterImpl simdops_scan(filterPredicate_lower, filterPredicate_upper);

        uint64_t pos_list_offset = 0;

        while (true) {
            tuddbs::InMemoryColumn<base_t> data_col(chunk.begin(), chunk.getNumberOfElements());
            auto res_start = res_col.begin() + offset;
            if constexpr (FilterImpl::ProducesBitmask) {
                auto res_end = simdops_scan(res_start, data_col.cbegin(), data_col.cend());
                offset += res_end - res_start;
            } else {
                auto res_end = simdops_scan(res_start, data_col.cbegin(), data_col.cend(), pos_list_offset);
                offset += res_end - res_start;
            }

            if (chunk.isLastChunk()) {
                break;
            }

            pos_list_offset += chunk.getNumberOfElements();
            chunk++;
        }

        const uint64_t size_in_bytes = offset * sizeof(intermediate_t);

        std::shared_ptr<Column> resColumn = std::make_shared<Column>(0, DataType::unknown, size_in_bytes, offset, false, true);

        if constexpr (FilterImpl::ProducesBitmask) {
            LOG_DEBUG1("[FilterOperator::doFilter] Producing Bitmask" << std::endl;)
            resColumn->datatype = DataType::bitmask;
        } else {
            LOG_DEBUG1("[FilterOperator::doFilter] Producing PositionList with " << offset << " elements and " << size_in_bytes << " Bytes." << std::endl;)
            resColumn->datatype = DataType::position_list;

            // Shrink the worst-case buffer to the actual result (also books the shrink)
            res_ptr = memtrack::tracked_shrink(res_ptr, size_in_bytes);
        }

        resColumn->setDataPtr(static_cast<void*>(res_ptr));

        LOG_DEBUG1("[FilterOperator] My result has " << resColumn->elements << " elements." << std::endl;)
        DataCatalog::getInstance().addColumn(filterData.outputcolumn().tabname(), filterData.outputcolumn().colname(), resColumn);

        return offset;
    }

    template <typename base_t>
    uint64_t doInFilter(std::shared_ptr<Column> column, const uint64_t chunkElements = 1024 * 1024 * 4) {
        auto filterData = m_work_item.filterdata();
        std::unordered_set<base_t> keysInSet;
        for (const auto& val : filterData.filtervalue()) {
            if constexpr (std::is_integral_v<base_t>) {
                keysInSet.insert(static_cast<base_t>(val.intval().value()));
            } else {  // if constexpr (std::is_floating_point_v<base_t>)
                keysInSet.insert(static_cast<base_t>(val.floatval().value()));
            }
        }

        return doActualInFilter<base_t>(column, chunkElements, keysInSet);
    }

    template <typename base_t, typename set_t>
    uint64_t doActualInFilter(std::shared_ptr<Column> column, const uint64_t chunkElements, const std::unordered_set<set_t>& filterValuesSet) {
        auto filterData = m_work_item.filterdata();
        
        if (filterValuesSet.empty()) {
            LOG_WARNING("[FilterOperator::doActualInFilter] No entries match the filter predicates. Creating an empty column." << std::endl;)
            // TODO: How to handle empty result?
            std::shared_ptr<Column> resColumn = std::make_shared<Column>(0, DataType::unknown, 0, 0, false, true);
            DataCatalog::getInstance().addColumn(filterData.outputcolumn().tabname(), filterData.outputcolumn().colname(), resColumn);
            return 0;
        }

        std::vector<size_t, memtrack::TempAlloc<size_t>> result_vec;  // temporary, counted by the allocator
        result_vec.reserve(column->elements);

        column->wait_data_allocated();
        View chunk = View<base_t>(static_cast<base_t*>(column->data), chunkElements, column);

        size_t offset = 0;

        while (true) {
            auto data = chunk.begin();
            for (size_t i = 0; i < chunk.getNumberOfElements(); ++i) {
                if (filterValuesSet.contains(data[i])) {
                    result_vec.push_back(i + offset);
                }
            }

            offset += chunk.getNumberOfElements();

            if (chunk.isLastChunk()) {
                break;
            }

            chunk++;
        }

        std::shared_ptr<Column> resColumn = std::make_shared<Column>(0, DataType::position_list, result_vec.size() * sizeof(size_t), result_vec.size(), false, true);

        void* res_data = std::malloc(result_vec.size() * sizeof(size_t));
        if (!res_data) {
            std::cerr << "[FilterOperator::doActualInFilter] Wasn't able to allocate the requested memory!" << std::endl;
            exit(-1);
        }
        if (!res_data) throw std::bad_alloc{};
        std::memcpy(res_data, result_vec.data(), result_vec.size() * sizeof(size_t));
        memtrack::onAlloc(res_data, result_vec.size() * sizeof(size_t));  // output buffer, adopted by setDataPtr below
        resColumn->setDataPtr(res_data);

        LOG_DEBUG1("[FilterOperator::doActualInFilter] My result has " << resColumn->elements << " elements." << std::endl;)
        DataCatalog::getInstance().addColumn(filterData.outputcolumn().tabname(), filterData.outputcolumn().colname(), resColumn);

        return result_vec.size();
    }

    template <class FilterImpl, typename CtorType = typename FilterImpl::CTorParamTupleT>
    uint64_t doFilterOnEnc(std::shared_ptr<Column> column, const uint64_t chunkElements = 1024 * 1024 * 4) {
        auto filterData = m_work_item.filterdata();

        using intermediate_t = FilterImpl::ResultType;
        using cpu_executor = tsl::executor<tsl::runtime::cpu>;
        cpu_executor exec;
        intermediate_t* res_ptr = memtrack::tracked_allocate<intermediate_t>(exec, column->elements, 64);
        tuddbs::InMemoryColumn<intermediate_t> res_col(res_ptr, column->elements);

        column->wait_data_allocated();
        View chunk = View<uint64_t>(static_cast<uint64_t*>(column->data), chunkElements, column);

        uint64_t offset = 0;

        const std::string filterPredicateString = filterData.filtervalue().Get(0).stringval().value();

        column->dictionaryInitialized.wait(false);  // wait for the pointer to be set
        column->dictionaryEncoding->waitReady();    // wait for actual dictionary content ready

        if (column->dictionaryEncoding->isPresentInDictionary(filterPredicateString)) {
            const uint64_t filterPredicate = column->dictionaryEncoding->getDictionaryValue(filterPredicateString);

            LOG_DEBUG1("[FilterOperator] My filter Value for " << filterData.filtervalue().Get(0).stringval().value() << ": " << filterPredicate << std::endl;)
            FilterImpl simdops_scan(filterPredicate);

            uint64_t pos_list_offset = 0;

            while (true) {
                tuddbs::InMemoryColumn<uint64_t> data_col(chunk.begin(), chunk.getNumberOfElements());
                auto res_start = res_col.begin() + offset;
                if constexpr (FilterImpl::ProducesBitmask) {
                    auto res_end = simdops_scan(res_start, data_col.cbegin(), data_col.cend());
                    offset += res_end - res_start;
                } else {
                    auto res_end = simdops_scan(res_start, data_col.cbegin(), data_col.cend(), pos_list_offset);
                    offset += res_end - res_start;
                }

                if (chunk.isLastChunk()) {
                    break;
                }

                pos_list_offset += chunk.getNumberOfElements();
                chunk++;
            }

            const uint64_t size_in_bytes = offset * sizeof(intermediate_t);

            std::shared_ptr<Column> resColumn = std::make_shared<Column>(0, DataType::unknown, size_in_bytes, offset, false, true);

            if constexpr (FilterImpl::ProducesBitmask) {
                LOG_DEBUG1("[FilterOperator::doFilter] Producing Bitmask" << std::endl;)
                resColumn->datatype = DataType::bitmask;
            } else {
                LOG_DEBUG1("[FilterOperator::doFilter] Producing PositionList" << std::endl;)
                resColumn->datatype = DataType::position_list;

                // Shrink the worst-case buffer to the actual result (also books the shrink)
                res_ptr = memtrack::tracked_shrink(res_ptr, size_in_bytes);
            }

            resColumn->setDataPtr(static_cast<void*>(res_ptr));

            LOG_DEBUG1("[FilterOperator] My result has " << resColumn->elements << " elements." << std::endl;)
            DataCatalog::getInstance().addColumn(filterData.outputcolumn().tabname(), filterData.outputcolumn().colname(), resColumn);

            return offset;
        } else {
            if (filterData.filtertype() == CompType::COMP_EQ) {
                LOG_WARNING("[FilterOperator] No entries match the filter predicate. Creating an empty column." << std::endl;)
                // TODO: How to handle empty result?
                std::shared_ptr<Column> resColumn = std::make_shared<Column>(0, DataType::unknown, 0, 0, false, true);
                DataCatalog::getInstance().addColumn(filterData.outputcolumn().tabname(), filterData.outputcolumn().colname(), resColumn);
                return 0;
            } else if (filterData.filtertype() == CompType::COMP_NE) {
                LOG_WARNING("[FilterOperator] All entries match the filter predicate. Creating an alias column." << std::endl;)
                // TODO: How to handle when all entries match? -> Currently alias
                DataCatalog::getInstance().addColumn(filterData.outputcolumn().tabname(), filterData.outputcolumn().colname(), column);
                return column->elements;
            } else {
                LOG_ERROR("[FilterOperator] This case should not occur. It means an unequality filter was applied to a string column! This code should not be reachable!" << std::endl;)
                exit(-2);
            }
        }
    }

    template <typename base_t>
    uint64_t selectFilter(std::shared_ptr<Column> column, const uint64_t chunkElements = 1024 * 1024 * 4) {
        using ps = tsl::simd<base_t, typename tsl::runtime::cpu::max_width_extension_t>;
        using HS = tuddbs::OperatorHintSet<tuddbs::hints::intermediate::position_list>;
        switch (m_work_item.filterdata().filtertype()) {
            case CompType::COMP_LT: {
                LOG_DEBUG1("[FilterOperator] Executing Filter with \"LessThan\" using largest vector width." << std::endl;)
                using FilterImpl = tuddbs::Filter_LT<ps, HS>;
                return doFilter<base_t, FilterImpl>(column, chunkElements);
            }; break;
            case CompType::COMP_LE: {
                using FilterImpl = tuddbs::Filter_LE<ps, HS>;
                return doFilter<base_t, FilterImpl>(column, chunkElements);
            } break;
            case CompType::COMP_EQ: {
                LOG_DEBUG1("[FilterOperator] Executing Filter with \"Equality\" using largest vector width." << std::endl;)
                using FilterImpl = tuddbs::Filter_EQ<ps, HS>;
                return doFilter<base_t, FilterImpl>(column, chunkElements);
            } break;
            case CompType::COMP_GE: {
                using FilterImpl = tuddbs::Filter_GE<ps, HS>;
                return doFilter<base_t, FilterImpl>(column, chunkElements);
            } break;
            case CompType::COMP_GT: {
                using FilterImpl = tuddbs::Filter_GT<ps, HS>;
                return doFilter<base_t, FilterImpl>(column, chunkElements);
            } break;
            case CompType::COMP_NE: {
                using FilterImpl = tuddbs::Filter_NEQ<ps, HS>;
                return doFilter<base_t, FilterImpl>(column, chunkElements);
            } break;
            case CompType::COMP_BETWEEN: {
                using FilterImpl = tuddbs::Filter_BWI<ps, HS>;
                return doFilter<base_t, FilterImpl>(column, chunkElements);
            } break;
            case CompType::COMP_IN: {
                return doInFilter<base_t>(column, chunkElements);
            } break;
            case CompType::COMP_LIKE: {
                LOG_ERROR("[FilterOperator] Error - 'LIKE' is not supported for numeric columns." << std::endl;)
                exit(-2);
            } break;
            default: {
                LOG_ERROR("[FilterOperator] Error - Could not deduce Filter Comparison type. I got: " << CompType_Name(m_work_item.filterdata().filtertype()) << std::endl;)
                exit(-2);
            }
        }
    }

    uint64_t selectEncFilter(std::shared_ptr<Column> column, const uint64_t chunkElements = 1024 * 1024 * 4) {
        using ps = tsl::simd<uint64_t, typename tsl::runtime::cpu::max_width_extension_t>;
        using HS = tuddbs::OperatorHintSet<tuddbs::hints::intermediate::position_list>;
        switch (m_work_item.filterdata().filtertype()) {
            case CompType::COMP_EQ: {
                LOG_DEBUG1("[FilterOperator] Executing Filter with \"Equality\" using largest vector width." << std::endl;)
                using FilterImpl = tuddbs::Filter_EQ<ps, HS>;
                return doFilterOnEnc<FilterImpl>(column, chunkElements);
            } break;
            case CompType::COMP_NE: {
                using FilterImpl = tuddbs::Filter_NEQ<ps, HS>;
                return doFilterOnEnc<FilterImpl>(column, chunkElements);
            } break;
            case CompType::COMP_BETWEEN: {
                return doBetweenFilterOnEnc(column, chunkElements);
            } break;
            case CompType::COMP_IN:{
                return doInFilterOnEnc(column, chunkElements);
            } break;
            case CompType::COMP_LIKE:{
                return doLikeFilterOnEnc(column, chunkElements);
            } break;
            case CompType::COMP_LT:
            case CompType::COMP_LE:
            case CompType::COMP_GE:
            case CompType::COMP_GT: {
                LOG_ERROR("[FilterOperator] Error - The chosen operator (" << CompType_Name(m_work_item.filterdata().filtertype()) << ") is not supported for string columns!" << std::endl;)
                exit(-2);
            } break;
            default: {
                LOG_ERROR("[FilterOperator] Error - Could not deduce Filter Comparison type. I got: " << CompType_Name(m_work_item.filterdata().filtertype()) << std::endl;)
                exit(-2);
            }
        }
    }
};