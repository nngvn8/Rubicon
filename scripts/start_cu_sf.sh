#!/usr/bin/env bash
# CU launcher for test_plans.sh (via CU_SCRIPT); dataset selected with SF=sf2|sf50|sf100.
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1

# exec so the launcher PID is the computeUnit PID.
exec ./build/bin/computeUnit \
    -ip 127.0.0.1 \
    -port 23233 \
    -path "data/binary/${SF:-sf2}" \
    -basedata bin \
    -worker 48 \
    -node 0 \
    -cxl_node 1
