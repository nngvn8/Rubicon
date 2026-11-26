#!/bin/bash

RUBICON_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${RUBICON_ROOT}/experiments/configs/benchmark_example.yaml"
cd "$RUBICON_ROOT"

PLAN_SOURCE=plans

sed -i -E "s/^plan_source:.*/plan_source: ${PLAN_SOURCE}/" "$CONFIG" || exit 1
sed -i -E "s/(materialize_into_join:).*/\1 true/" "$CONFIG"
sed -i -E "s|^(  reason: ).*|\1\"Test late-no-gco plans with materialization merged into joins\"|" "$CONFIG"
bash scripts/run_benchmark_batches.sh

PLAN_SOURCE=pb_plans

sed -i -E "s/^plan_source:.*/plan_source: ${PLAN_SOURCE}/" "$CONFIG" || exit 1
sed -i -E "s/(materialize_into_join:).*/\1 false/" "$CONFIG"
sed -i -E "s|^(  reason: ).*|\1\"Baseline late-no-gco plans without materialization merged into joins\"|" "$CONFIG"
bash scripts/run_benchmark_batches.sh