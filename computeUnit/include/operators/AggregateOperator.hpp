#pragma once

#include <algorithm>
#include <numeric>
#include <algorithms/utils/hinting.hpp>  // SIMDOps
#include <datastructures/column.hpp>     // SIMDOps
#include <infrastructure/DataCatalog.hpp>
#include <operators/AbstractOperator.hpp>


/**
 * @brief Iterate over a column and aggregate it.
 *
 */
class AggregateOperator : public AbstractOperator {
   public:
    AggregateOperator(WorkItem p_witem) : AbstractOperator(p_witem) {};
    virtual WorkResponse run() override;

   private:
    template <typename base_t>
    uint64_t calcCount(std::shared_ptr<Column> column, const uint64_t chunkElements = 1024 * 1024 * 4) {
        static_assert(std::is_arithmetic_v<base_t>, "[AggregateOperator] Could not deduce base_t for WorkItem");
        auto aggregateData = m_work_item.aggdata();

        using cpu_executor = tsl::executor<tsl::runtime::cpu>;
        cpu_executor exec;
        size_t* res_ptr = memtrack::tracked_allocate<size_t>(exec, 1, 64);

        *res_ptr = column->elements;

        std::shared_ptr<Column> resColumn = std::make_shared<Column>(0, DataType::uint64, sizeof(size_t), 1, false, true);

        resColumn->setDataPtr(static_cast<void*>(res_ptr));

        LOG_DEBUG1("[AggregateOperator] The count is " << *res_ptr << "." << std::endl;)
        DataCatalog::getInstance().addColumn(aggregateData.outputcolumn().tabname(), aggregateData.outputcolumn().colname(), resColumn);

        return 1;
    }

    template <typename base_t>
    uint64_t calcSum(std::shared_ptr<Column> column, const uint64_t chunkElements = 1024 * 1024 * 4) {
        static_assert(std::is_arithmetic_v<base_t>, "[AggregateOperator] Could not deduce base_t for WorkItem");
        auto aggregateData = m_work_item.aggdata();

        using cpu_executor = tsl::executor<tsl::runtime::cpu>;
        cpu_executor exec;
        base_t* res_ptr = memtrack::tracked_allocate<base_t>(exec, 1, 64);

        column->wait_data_allocated();
        View chunk = View<base_t>(static_cast<base_t*>(column->data), column->elements, column);  // even though we process all data at once, the chunk is needed for the data transfer protection logic to be sure the needed data is available

        *res_ptr = std::accumulate(static_cast<base_t*>(chunk.begin()), static_cast<base_t*>(chunk.end()), base_t{});

        std::shared_ptr<Column> resColumn = std::make_shared<Column>(0, column->datatype, sizeof(base_t), 1, false, true);

        resColumn->setDataPtr(static_cast<void*>(res_ptr));

        LOG_DEBUG1("[AggregateOperator] The sum is " << *res_ptr << "." << std::endl;)
        DataCatalog::getInstance().addColumn(aggregateData.outputcolumn().tabname(), aggregateData.outputcolumn().colname(), resColumn);

        return 1;
    }

    template <typename base_t>
    uint64_t calcMin(std::shared_ptr<Column> column, const uint64_t chunkElements = 1024 * 1024 * 4) {
        static_assert(std::is_arithmetic_v<base_t>, "[AggregateOperator] Could not deduce base_t for WorkItem");
        auto aggregateData = m_work_item.aggdata();

        using cpu_executor = tsl::executor<tsl::runtime::cpu>;
        cpu_executor exec;

        base_t* res_ptr = memtrack::tracked_allocate<base_t>(exec, 1, 64);

        column->wait_data_allocated();
        View chunk = View<base_t>(static_cast<base_t*>(column->data), column->elements, column);  // even though we process all data at once, the chunk is needed for the data transfer protection logic to be sure the needed data is available

        res_ptr = std::min_element(static_cast<base_t*>(chunk.begin()), static_cast<base_t*>(chunk.end()));

        std::shared_ptr<Column> resColumn = std::make_shared<Column>(0, column->datatype, sizeof(base_t), 1, false, true);

        resColumn->setDataPtr(static_cast<void*>(res_ptr));

        LOG_DEBUG1("[AggregateOperator] The min value is " << *res_ptr << "." << std::endl;)
        DataCatalog::getInstance().addColumn(aggregateData.outputcolumn().tabname(), aggregateData.outputcolumn().colname(), resColumn);

        return 1;
    }

    template <typename base_t>
    uint64_t calcMax(std::shared_ptr<Column> column, const uint64_t chunkElements = 1024 * 1024 * 4) {
        static_assert(std::is_arithmetic_v<base_t>, "[AggregateOperator] Could not deduce base_t for WorkItem");
        auto aggregateData = m_work_item.aggdata();

        using cpu_executor = tsl::executor<tsl::runtime::cpu>;
        cpu_executor exec;

        base_t* res_ptr = memtrack::tracked_allocate<base_t>(exec, 1, 64);

        column->wait_data_allocated();
        View chunk = View<base_t>(static_cast<base_t*>(column->data), column->elements, column);  // even though we process all data at once, the chunk is needed for the data transfer protection logic to be sure the needed data is available

        res_ptr = std::max_element(static_cast<base_t*>(chunk.begin()), static_cast<base_t*>(chunk.end()));

        std::shared_ptr<Column> resColumn = std::make_shared<Column>(0, column->datatype, sizeof(base_t), 1, false, true);

        resColumn->setDataPtr(static_cast<void*>(res_ptr));

        LOG_DEBUG1("[AggregateOperator] The min value is " << *res_ptr << "." << std::endl;)
        DataCatalog::getInstance().addColumn(aggregateData.outputcolumn().tabname(), aggregateData.outputcolumn().colname(), resColumn);

        return 1;
    }

    template <typename base_t>
    uint64_t calcAverage(std::shared_ptr<Column> column, const uint64_t chunkElements = 1024 * 1024 * 4) {
        static_assert(std::is_arithmetic_v<base_t>, "[AggregateOperator] Could not deduce base_t for WorkItem");
        auto aggregateData = m_work_item.aggdata();

        using cpu_executor = tsl::executor<tsl::runtime::cpu>;
        cpu_executor exec;
        double* res_ptr = memtrack::tracked_allocate<double>(exec, 1, 64);

        column->wait_data_allocated();
        View chunk = View<base_t>(static_cast<base_t*>(column->data), column->elements, column);  // even though we process all data at once, the chunk is needed for the data transfer protection logic to be sure the needed data is available

        base_t sum = std::accumulate(static_cast<base_t*>(chunk.begin()), static_cast<base_t*>(chunk.end()), base_t{});

        *res_ptr = sum / static_cast<double>(column->elements);

        std::shared_ptr<Column> resColumn = std::make_shared<Column>(0, DataType::f64, sizeof(double), 1, false, true);

        resColumn->setDataPtr(static_cast<void*>(res_ptr));

        LOG_DEBUG1("[AggregateOperator] The average is " << *res_ptr << "." << std::endl;)
        DataCatalog::getInstance().addColumn(aggregateData.outputcolumn().tabname(), aggregateData.outputcolumn().colname(), resColumn);

        return 1;
    }

    template <typename base_t>
    uint64_t selectAggregate(std::shared_ptr<Column> column, const uint64_t chunkElements = 1024 * 1024 * 4) {
        switch (m_work_item.aggdata().aggfunc()) {
            case AggFunc::AGG_COUNT: {
                return calcCount<base_t>(column, chunkElements);
            }; break;
            case AggFunc::AGG_SUM: {
                return calcSum<base_t>(column, chunkElements);
            } break;
            case AggFunc::AGG_MIN: {
                return calcMin<base_t>(column, chunkElements);
            } break;
            case AggFunc::AGG_MAX: {
                return calcMax<base_t>(column, chunkElements);
            } break;
            case AggFunc::AGG_AVG: {
                return calcAverage<base_t>(column, chunkElements);
            } break;
            default: {
                LOG_ERROR("[AggregateOperator] Error - Could not deduce Aggregate Function. I got: " << AggFunc_Name(m_work_item.aggdata().aggfunc()) << std::endl;)
                exit(-2);
            }
        }
    }
};