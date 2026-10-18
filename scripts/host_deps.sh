#!/bin/sh
# Install TariffTrail's Python dependencies into the Decider venv on a GPU host.
set -e
/home/ubuntu/.local/bin/uv pip install --python /home/ubuntu/decider-venv/bin/python boto3 numpy "strands-agents>=1.0" fastapi uvicorn
/home/ubuntu/decider-venv/bin/python -c "import boto3, numpy, strands; print('deps ok')"
