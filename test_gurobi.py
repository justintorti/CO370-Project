#!/usr/bin/env python
import sys
print("Python works", flush=True)
sys.stdout.flush()

try:
    import gurobipy
    print("Gurobi imported successfully", flush=True)
    sys.stdout.flush()
except Exception as e:
    print(f"Error importing gurobi: {e}", flush=True)
    sys.stdout.flush()
