#pragma once

#include <infrastructure/DataCatalog.hpp>
#include <operators/AbstractOperator.hpp>

class MapColumnsOperator : public AbstractOperator {
   public:
    MapColumnsOperator(WorkItem p_witem) : AbstractOperator(p_witem) {};
    virtual WorkResponse run() override;

   private:
    template <typename base_t, uint8_t Operator>
    uint64_t doMap(std::shared_ptr<Column> inputColumn, std::shared_ptr<Column> partnerColumn, const uint64_t chunkElements = 1024 * 1024 * 4) {
        static_assert(std::is_arithmetic_v<base_t>, "[MapColumnsOperator] Could not deduce base_t for WorkItem");
        auto mapData = m_work_item.mapdata();

        using cpu_executor = tsl::executor<tsl::runtime::cpu>;
        cpu_executor exec;
        base_t* res_ptr = memtrack::tracked_allocate<base_t>(exec, inputColumn->elements, 64);

        inputColumn->wait_data_allocated();
        partnerColumn->wait_data_allocated();
        View chunk1 = View<base_t>(static_cast<base_t*>(inputColumn->data), chunkElements, inputColumn);
        View chunk2 = View<base_t>(static_cast<base_t*>(partnerColumn->data), chunkElements, partnerColumn);

        for (uint64_t i = 0; i < inputColumn->elements; ) {
            for (uint64_t j = 0; j < chunk1.getNumberOfElements(); j++) {
                if (i + j >= inputColumn->elements) {
                    LOG_ERROR("[MapColumnsOperator::doMap] This shouldn't happen!" << std::endl;)
                    break;
                }

                auto ptr1 = chunk1.begin();
                auto ptr2 = chunk2.begin();

                switch (Operator) {
                    case 0: {
                        res_ptr[i + j] = ptr1[j] + ptr2[j];
                    } break;
                    case 1: {
                        res_ptr[i + j] = ptr1[j] / ptr2[j];
                    } break;
                    case 2: {
                        if constexpr (std::is_integral_v<base_t>) {
                            res_ptr[i + j] = ptr1[j] % ptr2[j];
                        } else {
                            LOG_ERROR("[MapColumnsOperator] Error - Modulo Operator not supported for float values." << std::endl;)
                            exit(-2);
                        }
                    } break;
                    case 3: {
                        res_ptr[i + j] = ptr1[j] * ptr2[j];
                    } break;
                    case 4: {
                        res_ptr[i + j] = ptr1[j] - ptr2[j];
                    } break;
                    default: {
                        LOG_ERROR("[MapColumnsOperator] Error - Could not deduce Scan Comparison type. I got: " << ArithOp_Name(m_work_item.mapdata().operatortype()) << std::endl;)
                        exit(-2);
                    }
                }
            }

            if (chunk1.isLastChunk()) {
                break;
            }

            i += chunk1.getNumberOfElements();

            chunk1++;
            chunk2++;
        }

        std::shared_ptr<Column> resColumn = std::make_shared<Column>(0, inputColumn->datatype, inputColumn->elements * sizeof(base_t), inputColumn->elements, false, true);
        resColumn->setDataPtr(static_cast<void*>(res_ptr));

        LOG_DEBUG1("[MapColumnsOperator] My result has " << resColumn->elements << " elements." << std::endl;)
        DataCatalog::getInstance().addColumn(mapData.outputcolumn().tabname(), mapData.outputcolumn().colname(), resColumn);

        return inputColumn->elements;
    }

    template <typename base_t>
    uint64_t selectMap(std::shared_ptr<Column> inputColumn, std::shared_ptr<Column> partnerColumn, const uint64_t chunkElements = 1024 * 1024 * 4) {
        switch (m_work_item.mapdata().operatortype()) {
            case ArithOp::ARITH_ADD: {
                return doMap<base_t, 0>(inputColumn, partnerColumn, chunkElements);
            }; break;
            case ArithOp::ARITH_DIV: {
                return doMap<base_t, 1>(inputColumn, partnerColumn, chunkElements);
            } break;
            case ArithOp::ARITH_MOD: {
                return doMap<base_t, 2>(inputColumn, partnerColumn, chunkElements);
            } break;
            case ArithOp::ARITH_MUL: {
                return doMap<base_t, 3>(inputColumn, partnerColumn, chunkElements);
            } break;
            case ArithOp::ARITH_SUB: {
                return doMap<base_t, 4>(inputColumn, partnerColumn, chunkElements);
            } break;
            default: {
                LOG_ERROR("[MapOperator] Error - Could not deduce Scan Comparison type. I got: " << ArithOp_Name(m_work_item.mapdata().operatortype()) << std::endl;)
                exit(-2);
            }
        }
    }
};