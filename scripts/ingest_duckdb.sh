#!/bin/bash
set -e

# ==============================================================================
# ingest_duckdb.sh
# Minimal bash script that ingests the SSB data into DuckDB using a CLI command.
#
# Usage:
#   ./scripts/ingest_duckdb.sh [SOURCE_DUCKDB_FILE] [TARGET_DB_FILE]
# Defaults:
#   SOURCE_DUCKDB_FILE: data/binary/sf2/sf2.duckdb
#   TARGET_DB_FILE:     DuckDB/sf2.duckdb
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

SOURCE_DB="${1:-$ROOT_DIR/data/binary/sf2/sf2.duckdb}"
TARGET_DB="${2:-$ROOT_DIR/DuckDB/sf2.duckdb}"

if [ ! -f "$SOURCE_DB" ]; then
    echo "Error: Source DuckDB file not found at: $SOURCE_DB"
    exit 1
fi

mkdir -p "$(dirname "$TARGET_DB")"

echo "Ingesting '$SOURCE_DB' into '$TARGET_DB' using DuckDB CLI..."

# Minimal DuckDB CLI command: attaches the source database and copies all tables into target database
duckdb "$TARGET_DB" "ATTACH '$SOURCE_DB' AS src (READ_ONLY); COPY FROM DATABASE src TO main; DETACH src;"

echo "Ingestion completed: $TARGET_DB"
