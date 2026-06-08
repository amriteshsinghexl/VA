"""
Launch all VA standalone APIs concurrently.

Usage:
    cd C:\projects\VA
    python api/run_all.py

Services started:
    model_api        http://localhost:8011/docs
    policy_data_api  http://localhost:8012/docs
    assumptions_api  http://localhost:8013/docs
    outputs_api      http://localhost:8014/docs
"""

import subprocess
import sys
from pathlib import Path

API_DIR = Path(__file__).parent

apis = [
    ("model_api",       8011),
    ("policy_data_api", 8012),
    ("assumptions_api", 8013),
    ("outputs_api",     8014),
]

procs = []
for module, port in apis:
    p = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            f"{module}:app",
            "--host", "0.0.0.0",
            "--port", str(port),
            "--reload",
        ],
        cwd=str(API_DIR),
    )
    procs.append((module, port, p))
    print(f"  Started {module:20s}  http://localhost:{port}/docs")

print("\nAll VA APIs running. Press Ctrl+C to stop all.\n")

try:
    for _, _, p in procs:
        p.wait()
except KeyboardInterrupt:
    print("\nStopping all VA APIs...")
    for _, _, p in procs:
        p.terminate()
