#!/bin/bash
set -e

# ==============================================================================
# generate_duckdb.sh
# Translates existing columnar binary SSB data in data/binary/sf2 into a .duckdb file.
#
# Usage:
#   ./scripts/generate_duckdb.sh [INPUT_DIR] [OUTPUT_FILE]
# Defaults:
#   INPUT_DIR:   data/binary/sf2
#   OUTPUT_FILE: data/binary/sf2/sf2.duckdb
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

INPUT_DIR="${1:-$ROOT_DIR/data/binary/sf2}"
OUTPUT_FILE="${2:-$ROOT_DIR/data/binary/sf2/sf2.duckdb}"

echo "=== Translating SSB Binary Data to DuckDB ==="
echo "Input Directory:  $INPUT_DIR"
echo "Output DuckDB:    $OUTPUT_FILE"

if [ ! -d "$INPUT_DIR" ]; then
    echo "Error: Input directory not found at $INPUT_DIR"
    exit 1
fi

mkdir -p "$(dirname "$OUTPUT_FILE")"

# Execute translation via Python (using uv if installed, otherwise python3)
if command -v uv &> /dev/null; then
    PY_RUN="uv run --with duckdb --with numpy --with pandas python3"
else
    PY_RUN="python3"
fi

$PY_RUN - "$INPUT_DIR" "$OUTPUT_FILE" << 'EOF'
import os
import re
import sys
import gc
import numpy as np
import pandas as pd
import duckdb

input_dir = sys.argv[1]
output_file = sys.argv[2]
schema_path = os.path.join(input_dir, "schema.txt")

if not os.path.isfile(schema_path):
    print(f"Error: schema file not found at {schema_path}", file=sys.stderr)
    sys.exit(1)

schema = {}
with open(schema_path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        table, col_spec = line.split(":", 1)
        table = table.strip()
        schema[table] = []
        for match in re.finditer(r"([a-zA-Z0-9_]+)\(([a-zA-Z0-9_]+)\)", col_spec):
            col_name, col_type = match.group(1), match.group(2)
            if col_name == "dummy":
                continue
            schema[table].append((col_name, col_type))

# Connect to target DuckDB database file
con = duckdb.connect(output_file)

for table_name, columns in schema.items():
    table_dir = os.path.join(input_dir, table_name)
    if not os.path.isdir(table_dir):
        print(f"Warning: Directory {table_dir} not found, skipping table {table_name}", file=sys.stderr)
        continue

    table_data = {}
    for col_name, col_type in columns:
        bin_path = os.path.join(table_dir, f"{col_name}.bin")
        if not os.path.isfile(bin_path):
            print(f"Warning: File {bin_path} not found, skipping column {col_name}", file=sys.stderr)
            continue

        if col_type == "int":
            table_data[col_name] = np.fromfile(bin_path, dtype="<i8")
        elif col_type == "bool":
            table_data[col_name] = np.fromfile(bin_path, dtype="<i1").astype(bool)
        elif col_type == "date":
            # Timestamp in seconds since Unix epoch
            raw_sec = np.fromfile(bin_path, dtype="<i8")
            dt = pd.to_datetime(raw_sec, unit="s")
            # Convert back to standard SSB integer date key YYYYMMDD
            table_data[col_name] = np.asarray(dt.year * 10000 + dt.month * 100 + dt.day, dtype="<i8")
        elif col_type == "str":
            raw_codes = np.fromfile(bin_path, dtype="<i8")
            dict_path = os.path.join(table_dir, f"{col_name}_dict.tsv")
            code_to_str = {}
            if os.path.isfile(dict_path):
                with open(dict_path, "r", encoding="utf-8") as df_in:
                    for d_line in df_in:
                        d_line = d_line.rstrip("\r\n")
                        if not d_line:
                            continue
                        parts = d_line.rsplit("\t", 1)
                        if len(parts) == 2:
                            code_to_str[int(parts[1])] = parts[0]
            max_code = max(code_to_str.keys()) if code_to_str else 0
            lookup = np.empty(max_code + 1, dtype=object)
            for code, val in code_to_str.items():
                lookup[code] = val
            table_data[col_name] = lookup[raw_codes]
        else:
            table_data[col_name] = np.fromfile(bin_path, dtype="<i8")

    df = pd.DataFrame(table_data)
    con.register("tmp_table", df)
    con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM tmp_table")
    con.unregister("tmp_table")
    print(f"Loaded table '{table_name}' ({len(df)} rows)")
    del df, table_data
    gc.collect()

con.close()
print(f"Translation complete! DuckDB file created at: {output_file}")
EOF
