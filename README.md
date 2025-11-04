# DuckDB TPC-H implementation

## Prerequisites

Install the required packages from `requirements.txt`:

```bash
pip install -r requirements.txt
```

Build the `dbgen`"

```bash
cd tpch_tools_3.0.1/dbgen
make
```

## Running the benchmark

Set the desired scale factor, e.g.:

```bash
export SF=100
```

To generate the data, run:

```bash
./generate.sh
```

Run the benchmark as follows:

```bash
python benchmark.py
```
