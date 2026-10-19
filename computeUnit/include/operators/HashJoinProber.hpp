#pragma once

#include <cstddef>
#include <unordered_map>

namespace hash_join {

template <typename KeyT>
using HashTable = std::unordered_map<KeyT, size_t>;

/**
 * Build a hash table that retains the first position for every inner key.
 */
template <typename KeyT>
HashTable<KeyT> build_hash_table(const KeyT* keys, size_t key_count) {
    HashTable<KeyT> table;
    table.reserve(key_count);

    for (size_t position = 0; position < key_count; ++position) {
        table.try_emplace(keys[position], position);
    }

    return table;
}

/**
 * Probe an inner-key hash table with outer keys and append matching positions.
 * Result pairs are ordered by their outer-column position.
 */
template <typename KeyT>
size_t probe_hash_table(const HashTable<KeyT>& table, const KeyT* keys, size_t key_count, size_t outer_position_offset,
                        size_t* inner_positions, size_t* outer_positions) {
    size_t match_count = 0;

    for (size_t position = 0; position < key_count; ++position) {
        const auto match = table.find(keys[position]);
        if (match != table.end()) {
            inner_positions[match_count] = match->second;
            outer_positions[match_count] = outer_position_offset + position;
            ++match_count;
        }
    }

    return match_count;
}

}  // namespace hash_join
