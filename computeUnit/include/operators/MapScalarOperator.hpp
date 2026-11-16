#pragma once

#include <infrastructure/DataCatalog.hpp>
#include <operators/AbstractOperator.hpp>

class MapScalarOperator : public AbstractOperator {
   public:
    MapScalarOperator(WorkItem p_witem) : AbstractOperator(p_witem) {};
    virtual WorkResponse run() override;

   private:
    template <typename base_t, uint8_t Operator>
    uint64_t doMap(std::shared_ptr<Column> column, base_t scalarValue, const uint64_t chunkElements = 1024 * 1024 * 4) {
        static_assert(std::is_arithmetic_v<base_t>, "[MapScalarOperator] Could not deduce base_t for WorkItem");
        auto mapData = m_work_item.mapdata();

        using cpu_executor = tsl::executor<tsl::runtime::cpu>;
        cpu_executor exec;
        base_t* res_ptr = memtrack::tracked_allocate<base_t>(exec, column->elements, 64);

        column->wait_data_allocated();
        View chunk = View<base_t>(static_cast<base_t*>(column->data), chunkElements, column);

        for (uint64_t i = 0; i < column->elements; ) {
            for (uint64_t j = 0; j < chunk.getNumberOfElements(); j++) {
                if (i + j >= column->elements) {
                    LOG_ERROR("[MapScalarOperator::doMap] This shouldn't happen!" << std::endl;)
                    break;
                }
                auto ptr = chunk.begin();

                switch (Operator) {
                    case 0: {
                        res_ptr[i + j] = ptr[j] + scalarValue;
                    } break;
                    case 1: {
                        res_ptr[i + j] = ptr[j] / scalarValue;
                    } break;
                    case 2: {
                        if constexpr (std::is_integral_v<base_t>) {
                            res_ptr[i + j] = ptr[j] % scalarValue;
                        } else {
                            LOG_ERROR("[MapScalarOperator] Error - Modulo Operator not supported for float values." << std::endl;)
                            exit(-2);
                        }
                    } break;
                    case 3: {
                        res_ptr[i + j] = ptr[j] * scalarValue;
                    } break;
                    case 4: {
                        res_ptr[i + j] = ptr[j] - scalarValue;
                    } break;
                    default: {
                        LOG_ERROR("[MapScalarOperator] Error - Could not deduce Scan Comparison type. I got: " << ArithOp_Name(m_work_item.mapdata().operatortype()) << std::endl;)
                        exit(-2);
                    }
                }
            }

            if (chunk.isLastChunk()) {
                break;
            }

            i += chunk.getNumberOfElements();

            chunk++;
        }

        std::shared_ptr<Column> resColumn = std::make_shared<Column>(0, column->datatype, column->elements * sizeof(base_t), column->elements, false, true);
        resColumn->setDataPtr(static_cast<void*>(res_ptr));

        LOG_DEBUG1("[MapScalarOperator] My result has " << resColumn->elements << " elements." << std::endl;)
        DataCatalog::getInstance().addColumn(mapData.outputcolumn().tabname(), mapData.outputcolumn().colname(), resColumn);

        return column->elements;
    }

    template <typename base_t>
    uint64_t selectMap(std::shared_ptr<Column> column, base_t scalarValue, const uint64_t chunkElements = 1024 * 1024 * 4) {
        switch (m_work_item.mapdata().operatortype()) {
            case ArithOp::ARITH_ADD: {
                return doMap<base_t, 0>(column, scalarValue, chunkElements);
            }; break;
            case ArithOp::ARITH_DIV: {
                return doMap<base_t, 1>(column, scalarValue, chunkElements);
            } break;
            case ArithOp::ARITH_MOD: {
                return doMap<base_t, 2>(column, scalarValue, chunkElements);
            } break;
            case ArithOp::ARITH_MUL: {
                return doMap<base_t, 3>(column, scalarValue, chunkElements);
            } break;
            case ArithOp::ARITH_SUB: {
                return doMap<base_t, 4>(column, scalarValue, chunkElements);
            } break;
            default: {
                LOG_ERROR("[MapOperator] Error - Could not deduce Scan Comparison type. I got: " << ArithOp_Name(m_work_item.mapdata().operatortype()) << std::endl;)
                exit(-2);
            }
        }
    }
};