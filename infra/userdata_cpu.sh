#!/bin/bash
# EC2 user data (CPU host): serve Strands Decider 2B on 127.0.0.1:8099 as a systemd service.
# Runs once at first boot on Ubuntu 24.04. Uses the CPU wheel of torch (no CUDA download).
# Progress: /var/log/tariff-trail-setup.log ; service logs: journalctl -u strands-decider
set -euxo pipefail
exec > >(tee -a /var/log/tariff-trail-setup.log) 2>&1

MODEL="StrandsAgents/strands-decider-2B-qwen3.5-v1-2610"
APP_USER=ubuntu
HOME_DIR=/home/$APP_USER

apt-get update -y
apt-get install -y git python3-venv python3-dev build-essential unzip curl
snap install aws-cli --classic || true

sudo -u $APP_USER bash -lc '
  set -euxo pipefail
  cd ~
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
  [ -d strands-decider ] || git clone https://github.com/strands-labs/strands-decider
  cd strands-decider
  uv venv --python 3.12 ~/decider-venv
  source ~/decider-venv/bin/activate
  uv pip install torch --index-url https://download.pytorch.org/whl/cpu
  uv pip install -e .
  # TariffTrail runtime deps (evaluation runs on this host via SSM)
  uv pip install boto3 numpy "strands-agents>=1.0" fastapi uvicorn
  strands-decider info '"$MODEL"' || true
'

THREADS=$(nproc)
cat > /etc/systemd/system/strands-decider.service <<UNIT
[Unit]
Description=Strands Decider 2B on CPU (127.0.0.1:8099)
After=network-online.target
Wants=network-online.target

[Service]
User=$APP_USER
WorkingDirectory=$HOME_DIR/strands-decider
Environment=HF_HOME=$HOME_DIR/.cache/huggingface
Environment=OMP_NUM_THREADS=$THREADS
ExecStart=$HOME_DIR/decider-venv/bin/strands-decider serve $MODEL --device cpu --port 8099
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now strands-decider
echo "tariff-trail setup complete"
