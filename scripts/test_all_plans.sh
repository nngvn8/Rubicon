#!/usr/bin/env bash
set -uo pipefail

# ==============================================================================
# Script: test_all_plans.sh
# Purpose: Sequentially test all query plans in data/pb_plans against Rubicon,
#          optionally restarting ComputeUnit (CU) for each plan, and report
#          success/failure.
# ==============================================================================

RUBICON_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PB_PLANS_DIR="${RUBICON_ROOT}/data/pb_plans"
PLANS_DIR="${RUBICON_ROOT}/data/plans"
EXPERIMENTS_DIR="${RUBICON_ROOT}/experiments"

GRP_SCRIPT="${HOME}/start_rubi_grp.sh"
CU_SCRIPT="${HOME}/start_rubi_cu.sh"

TIMEOUT_SECONDS=20
VERBOSE=false
RESTART_CU=false
WRITE_BENCHMARK_RESULTS=false
RUNS=1
WARMUP_RUNS=0

# Formatting
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -v, --verbose       Print full output from run_query.py for every test"
    echo "  -t, --timeout <sec> Per-query timeout in seconds (default: 20)"
    echo "  -r, --restart-cu    Restart CU for every plan (default: reuse it)"
    echo "  -b, --benchmark     Write timestamped benchmark results under benchmarking/"
    echo "      --runs <count>   Measured full-batch rounds per benchmark (default: 1)"
    echo "      --warmup-runs <count>  Unmeasured full-batch warmup rounds (default: 0)"
    echo "  -h, --help          Show this help message"
    exit 0
}

# Parse command line options
while [[ $# -gt 0 ]]; do
    case "$1" in
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -t|--timeout)
            TIMEOUT_SECONDS="$2"
            shift 2
            ;;
        -r|--restart-cu)
            RESTART_CU=true
            shift
            ;;
        -b|--benchmark)
            WRITE_BENCHMARK_RESULTS=true
            shift
            ;;
        --runs)
            RUNS="$2"
            shift 2
            ;;
        --warmup-runs)
            WARMUP_RUNS="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

GRP_PID=""
CU_PID=""
GRP_LOG="/tmp/rubi_grp.log"
CU_LOG="/tmp/rubi_cu.log"

# Stop ComputeUnit
stop_cu() {
    if [[ -n "${CU_PID}" ]] && kill -0 "${CU_PID}" 2>/dev/null; then
        kill -TERM "${CU_PID}" 2>/dev/null || true
    fi
    pkill -f "build/bin/computeUnit" 2>/dev/null || true
    CU_PID=""
    sleep 0.5
}

# Stop Grouper
stop_grouper() {
    if [[ -n "${GRP_PID}" ]] && kill -0 "${GRP_PID}" 2>/dev/null; then
        kill -TERM "${GRP_PID}" 2>/dev/null || true
    fi
    pkill -f "build/bin/grouper" 2>/dev/null || true
    GRP_PID=""
    sleep 0.5
}

# Cleanup on exit or interruption
cleanup() {
    echo -e "\n${YELLOW}[!] Cleaning up processes and active plan directory...${NC}"
    stop_cu
    stop_grouper
    rm -f "${PLANS_DIR}"/*.pb 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Start Grouper
start_grouper() {
    echo -e "${BLUE}[*] Starting Grouper (${GRP_SCRIPT})...${NC}"
    # Ensure any previous instances are cleared
    stop_grouper
    sleep 1

    # Keep stdin open using sleep infinity so cin does not EOF/busy-loop
    sleep infinity | bash "${GRP_SCRIPT}" > "${GRP_LOG}" 2>&1 &
    GRP_PID=$!
    sleep 1

    if ! pgrep -f "build/bin/grouper" >/dev/null; then
        echo -e "${RED}[ERROR] Grouper failed to start. Log output:${NC}"
        cat "${GRP_LOG}"
        exit 1
    fi
}

# Start ComputeUnit
start_cu() {
    # Ensure previous CU is completely stopped
    stop_cu

    bash "${CU_SCRIPT}" > "${CU_LOG}" 2>&1 &
    CU_PID=$!
    sleep 1

    if ! pgrep -f "build/bin/computeUnit" >/dev/null; then
        echo -e "${RED}[ERROR] ComputeUnit failed to start. Log output:${NC}"
        cat "${CU_LOG}"
        return 1
    fi
    return 0
}

# Main Execution Flow
echo -e "${BOLD}======================================================${NC}"
echo -e "${BOLD}          Rubicon Query Plan Test Suite              ${NC}"
echo -e "${BOLD}======================================================${NC}"

# Verify directories and scripts exist
if [[ ! -d "${PB_PLANS_DIR}" ]]; then
    echo -e "${RED}[ERROR] Source plans directory not found: ${PB_PLANS_DIR}${NC}"
    exit 1
fi

if [[ ! -f "${GRP_SCRIPT}" ]]; then
    echo -e "${RED}[ERROR] Grouper script not found: ${GRP_SCRIPT}${NC}"
    exit 1
fi

if [[ ! -f "${CU_SCRIPT}" ]]; then
    echo -e "${RED}[ERROR] ComputeUnit script not found: ${CU_SCRIPT}${NC}"
    exit 1
fi

# Ensure clean state before starting
stop_cu
stop_grouper
mkdir -p "${PLANS_DIR}"
mkdir -p "${RUBICON_ROOT}/benchmarking"
rm -f "${PLANS_DIR}"/*.pb 2>/dev/null || true

# Gather plan files in natural sort order
mapfile -t PLAN_FILES < <(find "${PB_PLANS_DIR}" -maxdepth 1 -name "*.pb" | sort -V)
TOTAL_PLANS=${#PLAN_FILES[@]}

if [[ ${TOTAL_PLANS} -eq 0 ]]; then
    echo -e "${YELLOW}No .pb plan files found in ${PB_PLANS_DIR}.${NC}"
    exit 0
fi

echo -e "Found ${CYAN}${TOTAL_PLANS}${NC} plan file(s) to test.\n"

SUCCESSFUL_PLANS=()
FAILED_PLANS=()

# Grouper retains its original lifecycle: it runs throughout all tests.
start_grouper
if [[ "${RESTART_CU}" == "true" ]]; then
    echo -e "${BLUE}[*] ComputeUnit will restart for each plan.${NC}"
else
    echo -e "${BLUE}[*] ComputeUnit will start with the first plan and remain running.${NC}"
fi
CU_STARTED=false

INDEX=0
for PLAN_PATH in "${PLAN_FILES[@]}"; do
    INDEX=$((INDEX + 1))
    PLAN_NAME="$(basename "${PLAN_PATH}")"

    echo -e "\n${BOLD}[${INDEX}/${TOTAL_PLANS}] Testing plan: ${CYAN}${PLAN_NAME}${NC}"

    # Check if Grouper is still alive; restart if it crashed.
    if ! pgrep -f "build/bin/grouper" >/dev/null; then
        echo -e "    ${YELLOW}[!] Grouper was not running. Restarting Grouper...${NC}"
        start_grouper
    fi

    # 1. Clean destination and copy single plan into data/plans
    rm -f "${PLANS_DIR}"/*.pb 2>/dev/null || true
    cp "${PLAN_PATH}" "${PLANS_DIR}/${PLAN_NAME}"

    # 2. Start CU once by default, or for every plan when requested.
    if [[ "${RESTART_CU}" == "true" || "${CU_STARTED}" == "false" ]]; then
        echo -e "    ${BLUE}==>${NC} Starting ComputeUnit..."
        if ! start_cu; then
            echo -e "    ${RED}[FAILED]${NC} Unable to start ComputeUnit."
            FAILED_PLANS+=("${PLAN_NAME} (CU start failure)")
            rm -f "${PLANS_DIR}/${PLAN_NAME}"
            continue
        fi
        CU_STARTED=true
    elif ! pgrep -f "build/bin/computeUnit" >/dev/null; then
        # Recover CU only if it crashed; normal plans reuse the same process.
        echo -e "    ${YELLOW}[!] ComputeUnit was not running. Restarting ComputeUnit...${NC}"
        if ! start_cu; then
            echo -e "    ${RED}[FAILED]${NC} Unable to start ComputeUnit."
            FAILED_PLANS+=("${PLAN_NAME} (CU start failure)")
            rm -f "${PLANS_DIR}/${PLAN_NAME}"
            continue
        fi
        CU_STARTED=true
    fi

    # 3. Execute run_query.py
    echo -e "    ${BLUE}==>${NC} Running query (timeout: ${TIMEOUT_SECONDS}s)..."
    CMD_OUTPUT=""
    EXIT_CODE=0
    RUN_QUERY_ARGS=(-f "${PLANS_DIR}" --runs "${RUNS}" --warmup-runs "${WARMUP_RUNS}")
    if [[ "${WRITE_BENCHMARK_RESULTS}" == "true" ]]; then
        RUN_QUERY_ARGS+=(--write-benchmark-results)
    fi
    CMD_OUTPUT=$(cd "${EXPERIMENTS_DIR}" && timeout "${TIMEOUT_SECONDS}" uv run run_query.py "${RUN_QUERY_ARGS[@]}" 2>&1) || EXIT_CODE=$?

    # 4. Check the canonical PlanResponse.info success marker and exit code.
    # ComputeUnit emits this exact line only for a fully completed plan.
    if [[ ${EXIT_CODE} -eq 124 ]]; then
        echo -e "    ${RED}[FAILED]${NC} Query timed out after ${TIMEOUT_SECONDS}s."
        FAILED_PLANS+=("${PLAN_NAME} (Timed out)")
    elif [[ ${EXIT_CODE} -eq 0 ]] && grep -Fxq "Plan completed successfully." <<< "${CMD_OUTPUT}"; then
        echo -e "    ${GREEN}[SUCCESS]${NC} Query completed successfully."
        SUCCESSFUL_PLANS+=("${PLAN_NAME}")
    else
        echo -e "    ${RED}[FAILED]${NC} Query did not succeed."
        FAILED_PLANS+=("${PLAN_NAME}")
    fi

    # Display output if verbose or if failed (for immediate insight)
    if [[ "${VERBOSE}" == "true" ]]; then
        echo -e "    --- Output ---"
        echo "${CMD_OUTPUT}" | sed 's/^/    /'
        echo -e "    --------------"
    elif ! grep -Fxq "Plan completed successfully." <<< "${CMD_OUTPUT}"; then
        echo -e "    --- Failure snippet ---"
        echo "${CMD_OUTPUT}" | tail -n 10 | sed 's/^/    /'
        echo -e "    -----------------------"
    fi

    # 5. Stop CU only in per-plan restart mode.
    if [[ "${RESTART_CU}" == "true" ]]; then
        echo -e "    ${BLUE}==>${NC} Stopping ComputeUnit..."
        stop_cu
        CU_STARTED=false
    fi

    # 6. Delete the copied plan file
    rm -f "${PLANS_DIR}/${PLAN_NAME}"
done

# Print Final Summary
echo -e "\n${BOLD}======================================================${NC}"
echo -e "${BOLD}                    FINAL SUMMARY                     ${NC}"
echo -e "${BOLD}======================================================${NC}"
echo -e "Total Plans Tested: ${TOTAL_PLANS}"
echo -e "${GREEN}Successful (${#SUCCESSFUL_PLANS[@]}):${NC}"
for P in "${SUCCESSFUL_PLANS[@]}"; do
    echo -e "  ${GREEN}✓${NC} ${P}"
done

if [[ ${#FAILED_PLANS[@]} -gt 0 ]]; then
    echo -e "\n${RED}Failed (${#FAILED_PLANS[@]}):${NC}"
    for P in "${FAILED_PLANS[@]}"; do
        echo -e "  ${RED}✗${NC} ${P}"
    done
else
    echo -e "\n${GREEN}All ${TOTAL_PLANS} plans executed successfully!${NC}"
fi
echo -e "${BOLD}======================================================${NC}"

# Exit with status 0 if all passed, 1 if any failed
if [[ ${#FAILED_PLANS[@]} -eq 0 ]]; then
    exit 0
else
    exit 1
fi
