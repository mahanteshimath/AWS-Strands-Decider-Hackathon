<#
.SYNOPSIS
  Serve Strands Decider on this laptop's CPU at 127.0.0.1:8099 (where the demo looks), fully offline.

.DESCRIPTION
  Hugging Face is blocked on this network, so the weights come from ModelScope mirrors, verified by
  sha256 (scripts/verify_decider_download.py) into ~/.cache/strands-decider:
    strands-decider-2B-qwen3.5-v1-2610   LoRA adapter + decision head (the published Decider)
    Qwen3.5-2B-Base                      the base model it was trained on
  The checkpoint config names the base model by Hub id, so this script makes a copy whose
  base_model points at the local folder (the verified original is left untouched) and serves it
  with the Hub disabled. Leave it running; Ctrl+C to stop. Free: nothing runs in the cloud.

.EXAMPLE
  ./infra/decider_local.ps1
  # then: uvicorn tariff_trail.web.app:app --port 8010   (the page shows "Decider live")
#>
param([int]$Port = 8099, [string]$Device = "cpu")
$ErrorActionPreference = "Stop"
$cache = Join-Path $env:USERPROFILE ".cache\strands-decider"
$decider = Join-Path $cache "strands-decider-2B-qwen3.5-v1-2610"
$base = Join-Path $cache "Qwen3.5-2B-Base"
$local = Join-Path $cache "decider-local"
$venv = Join-Path $env:LOCALAPPDATA "tariff-trail\decider-venv"
$py = Join-Path $venv "Scripts\python.exe"

foreach ($need in @($py, (Join-Path $decider "head.safetensors"), (Join-Path $base "config.json"))) {
    if (-not (Test-Path $need)) { throw "missing $need - run the local Decider setup first (see README, 'Run Decider on a laptop')" }
}

if (-not (Test-Path (Join-Path $local "strands_decider_config.json"))) {
    Write-Host "making local checkpoint copy at $local"
    New-Item -ItemType Directory -Force $local | Out-Null
    Copy-Item -Recurse -Force (Join-Path $decider "*") $local
    & $py -c @"
import json, sys
path = sys.argv[1] + r'\strands_decider_config.json'
cfg = json.load(open(path, encoding='utf-8'))
cfg['base_model'] = sys.argv[2]
json.dump(cfg, open(path, 'w', encoding='utf-8'), indent=2)
print('base_model ->', cfg['base_model'])
"@ $local $base
}

$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
Write-Host "serving Decider on http://127.0.0.1:$Port ($Device)"
& $py -m strands_decider.cli serve $local --host 127.0.0.1 --port $Port --device $Device --model-name strands-decider-2B-qwen3.5-v1-2610
