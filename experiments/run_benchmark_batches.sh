#!/usr/bin/env bash
# Run in tmux with no grouper or ComputeUnit already running.
cd "$(dirname "${BASH_SOURCE[0]}")/.."
logs="$(pwd)/benchmarking/in-batches-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$logs"
# Keep console input open; the grouper exits when it receives EOF.
mkfifo "$logs/grouper.stdin"
exec 3<> "$logs/grouper.stdin"
./build/bin/grouper -port 23233 <&3 > "$logs/grouper.log" 2>&1 &
grouper_pid=$!
sleep 2

for pair in "sequential 2" "sequential 50" "sequential 100" "concurrent 2" "concurrent 50" "concurrent 100"; do
    read -r execution_mode sf <<< "$pair"

    sed -i -E \
        -e "s/^(  scale_factor: )[0-9]+/\\1${sf}/" \
        -e "s/^(  execution_mode: )[a-z]+/\\1${execution_mode}/" \
        experiments/configs/benchmark_example.yaml

    ./build/bin/computeUnit -ip 127.0.0.1 -port 23233 \
        -path "data/binary/sf${sf}" -basedata bin -worker 48 -node 0 -cxl_node 1 \
        > "$logs/${execution_mode}-sf${sf}-cu.log" 2>&1 &
    cu_pid=$!

    # Wait for data loading and connection, then allow registration to finish.
    until ss -H -tnp state established '( dport = :23233 )' | grep -q "pid=$cu_pid,"; do
        sleep 1
    done
    sleep 2

    (cd experiments && uv run python -u run_query.py \
        --config configs/benchmark_example.yaml) \
        > "$logs/${execution_mode}-sf${sf}-queries.log" 2>&1

    kill "$cu_pid"
    wait "$cu_pid"
    sleep 2
done

kill "$grouper_pid"
wait "$grouper_pid"
exec 3>&-
rm "$logs/grouper.stdin"
