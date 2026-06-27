"""Job entry points — one module per stage in the design.

Each job is a thin shell: open audit row, open MLflow run, claim work, call
the configured adapter, transition status, close audit. The skeleton stops at
the shell — no adapter wiring, no Spark.
"""
