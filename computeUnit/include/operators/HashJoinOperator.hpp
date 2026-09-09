#pragma once

#include <algorithm>
#include <set>
#include <algorithms/dbops/dbops_hints.hpp>           //SIMDOps
#include <algorithms/dbops/join/hash_join.hpp>        //SIMDOps
#include <algorithms/dbops/join/hash_join_hints.hpp>  //SIMDOps
#include <algorithms/utils/hashing.hpp>               //SIMDOps
#include <datastructures/column.hpp>                  // SIMDOps
#include <infrastructure/DataCatalog.hpp>
#include <operators/AbstractOperator.hpp>

template <typename BaseT, typename PosT = size_t>
struct hash_join_column_set_t {
    tuddbs::InMemoryColumn<BaseT> key_sink;
    tuddbs::InMemoryColumn<PosT> value_sink;
    tuddbs::InMemoryColumn<BaseT> used_sink;

    explicit hash_join_column_set_t(const size_t map_count, auto key_allocator, auto value_allocator, auto deleter)
        : key_sink(map_count, key_allocator, deleter),
          value_sink(map_count, value_allocator, deleter),
          used_sink(map_count, key_allocator, deleter) {}

    ~hash_join_column_set_t() {}
};

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

        /**
         * TODO: Implement the TSL intrinsics to support ARM Neon, Intel SSE and Intel AVX512.
         */
        // using ps = tsl::simd<base_t, typename tsl::runtime::cpu::max_width_extension_t>;

        /**
         * TODO: Current limitation: Only AVX2 works with most types; i.e. except float/double.
         */
        using ps = tsl::simd<base_t, tsl::avx2>;

        // using hs = tuddbs::OperatorHintSet<tuddbs::hints::hashing::linear_displacement, tuddbs::hints::hashing::size_exp_2, tuddbs::hints::hash_join::keys_may_contain_empty_indicator, tuddbs::hints::hash_join::global_first_occurence_required>;
        using hs = tuddbs::OperatorHintSet<tuddbs::hints::hashing::linear_displacement, tuddbs::hints::hashing::size_exp_2, tuddbs::hints::hash_join::global_first_occurence_required>;
        using HashJoinImpl = tuddbs::Hash_Join<ps, size_t, hs>;
        using hash_join_state_t = hash_join_column_set_t<base_t>;

        auto join_deleter = []<typename T>(T *ptr) {
            tsl::executor<tsl::runtime::cpu> exec;
            exec.deallocate(ptr);
        };

        tsl::executor<tsl::runtime::cpu> exec;
        size_t *join_result_id_a = exec.allocate<size_t>(outerColumn->elements);
        size_t *join_result_id_b = exec.allocate<size_t>(outerColumn->elements);

        // const size_t resultSize = 1 << 21;  // this is basically taken and adapted from join_test.cpp --> don't know why this size
        const size_t resultSize = tuddbs::determine_bucket_count<hs>(innerColumn->elements);
        LOG_DEBUG1("[HashJoinOperator] Determined Bucket Size: " << resultSize << " for " << innerColumn->elements << std::endl;)

        // hash_join_state_t hash_join_columns(resultSize, join_allocator<base_t>, join_allocator<size_t>, join_deleter);

        auto key_sink_ptr = exec.allocate<base_t>(resultSize, 64);
        auto value_sink_ptr = exec.allocate<size_t>(resultSize, 64);
        auto used_sink_ptr = exec.allocate<base_t>(resultSize, 64);
        tuddbs::InMemoryColumn<base_t> key_sink(std::move(key_sink_ptr), resultSize, join_deleter);
        tuddbs::InMemoryColumn<size_t> value_sink(std::move(value_sink_ptr), resultSize, join_deleter);
        tuddbs::InMemoryColumn<base_t> used_sink(std::move(used_sink_ptr), resultSize, join_deleter);

        typename HashJoinImpl::builder_t builder(key_sink.begin(), used_sink.begin(), value_sink.begin(), resultSize);
        typename HashJoinImpl::prober_t prober(key_sink.begin(), used_sink.begin(), value_sink.begin(), resultSize);

        View innerChunk = View<base_t>(static_cast<base_t *>(innerColumn->data), innerColumn->elements, innerColumn);

        tuddbs::InMemoryColumn<base_t> innerCol(innerChunk.begin(), innerChunk.getNumberOfElements());

        LOG_DEBUG2("[HashJoinOperator] Starting Hash-Phase." << std::endl;)
        builder(innerCol.cbegin(), innerCol.cend());
        LOG_DEBUG2("[HashJoinOperator] Finished Hash-Phase." << std::endl;)

        View outerChunk = View<base_t>(static_cast<base_t *>(outerColumn->data), chunkElements, outerColumn);

        size_t join_result = 0;

        LOG_DEBUG2("[HashJoinOperator] Starting Probe-Phase." << std::endl;)
        size_t position_offset = 0;
        while (true) {
            tuddbs::InMemoryColumn<base_t> outerCol(outerChunk.begin(), outerChunk.getNumberOfElements());

            join_result += prober(join_result_id_a + join_result, join_result_id_b + join_result, outerCol.cbegin(), outerCol.cend(), position_offset);
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

        resColumnInner->setDataPtr(static_cast<void *>(join_result_id_a));
        resColumnOuter->setDataPtr(static_cast<void *>(join_result_id_b));

        LOG_DEBUG1("[HashJoinOperator] My result has " << join_result << " elements." << std::endl;)
        DataCatalog::getInstance().addColumn(joinData.ioutputcolumn().tabname(), joinData.ioutputcolumn().colname(), resColumnInner);
        DataCatalog::getInstance().addColumn(joinData.ooutputcolumn().tabname(), joinData.ooutputcolumn().colname(), resColumnOuter);

        return join_result;
    }
};