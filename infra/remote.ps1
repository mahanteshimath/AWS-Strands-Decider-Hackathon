<#
.SYNOPSIS
  Run TariffTrail commands on the Decider host over SSM (no SSH, no open ports, no local plugin).

.DESCRIPTION
  push    zip the code and data the host needs, upload to s3://tariff-trail-<acct>-<region>/code/
  run     download the bundle on the host and run a shell command in ~/tariff-trail with the
          Decider venv; stdout/stderr go to s3://.../ssm/ and the tail is printed here
  pull    copy s3://.../results/ into eval/results/ on this machine

.EXAMPLE
  ./infra/remote.ps1 push
  ./infra/remote.ps1 run "python scripts/smoke.py"
  ./infra/remote.ps1 run "python eval/run_eval.py --system decider_only --split dev --workers 1" -Wait 3600
  ./infra/remote.ps1 pull
#>
param(
    [Parameter(Mandatory = $true, Position = 0)][ValidateSet("push", "run", "pull", "log")][string]$Action,
    [Parameter(Position = 1)][string]$Command = "",
    [int]$Wait = 900,
    [string]$Profile = "hackathon",
    [string]$Region = "us-east-1"
)
$ErrorActionPreference = "Continue"
$env:AWS_PAGER = ""
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$common = @("--profile", $Profile, "--region", $Region, "--no-cli-pager")
$account = aws.exe sts get-caller-identity @common --output text --query Account
$bucket = "tariff-trail-$account-$Region"

function InstanceId {
    $id = aws.exe ec2 describe-instances @common --output text `
        --filters "Name=tag:Name,Values=tariff-trail-decider" "Name=instance-state-name,Values=running" `
        --query "Reservations[0].Instances[0].InstanceId"
    if (-not $id -or $id -eq "None") { throw "no running tariff-trail-decider instance; run infra/ec2_up.ps1" }
    return $id.Trim()
}

if ($Action -eq "push") {
    # Python's zipfile, because PowerShell 5.1's Compress-Archive writes backslash paths Linux cannot unpack.
    $zip = Join-Path $env:TEMP "tt-bundle.zip"
    if (Test-Path $zip) { Remove-Item $zip }
    python (Join-Path $root "scripts\bundle.py") $zip
    aws.exe s3 cp $zip "s3://$bucket/code/tt-bundle.zip" @common | Out-Null
    Write-Output ("pushed {0:N1} MB to s3://$bucket/code/tt-bundle.zip" -f ((Get-Item $zip).Length / 1MB))
    exit 0
}

if ($Action -eq "pull") {
    aws.exe s3 sync "s3://$bucket/results/" (Join-Path $root "eval\results") @common
    exit 0
}

$id = InstanceId
if ($Action -eq "log") {
    $Command = "tail -n 40 /var/log/tariff-trail-setup.log; systemctl is-active strands-decider; curl -s -m 5 127.0.0.1:8099/health || echo no-health"
    $script = $Command
} else {
    # Each run refreshes the code from the bundle; eval results live outside the bundle and are synced to S3.
    $script = @"
set -e
export HOME=/home/ubuntu
cd /home/ubuntu
aws s3 cp s3://$bucket/code/tt-bundle.zip /tmp/tt-bundle.zip --quiet --region $Region
mkdir -p tariff-trail && cd tariff-trail
python3 -c "import zipfile; zipfile.ZipFile('/tmp/tt-bundle.zip').extractall('.')"
mkdir -p eval/results
# Bring down results this host does not have yet, but never overwrite a local file: a running
# evaluation appends to its file, and replacing it would orphan every row written since.
rm -rf /tmp/tt-results-in && mkdir -p /tmp/tt-results-in
aws s3 sync s3://$bucket/results/ /tmp/tt-results-in/ --quiet --region $Region || true
cp -rn /tmp/tt-results-in/. eval/results/ || true
export AWS_REGION=$Region STRANDS_DECIDER_URL=http://127.0.0.1:8099 PYTHONUNBUFFERED=1
# SSM runs this with /bin/sh, so use "." rather than "source"; keep going after a failure to sync results.
. /home/ubuntu/decider-venv/bin/activate
set +e
$Command
status=`$?
aws s3 sync eval/results/ s3://$bucket/results/ --quiet --region $Region || true
chown -R ubuntu:ubuntu /home/ubuntu/tariff-trail
exit `$status
"@
}
$params = Join-Path $env:TEMP "tt-ssm.json"
@{ commands = @($script -split "`r?`n"); executionTimeout = @("$Wait") } | ConvertTo-Json -Depth 4 | Set-Content -Encoding ascii $params
$cmd = aws.exe ssm send-command @common --output text --instance-ids $id --document-name AWS-RunShellScript `
    --timeout-seconds 60 --parameters "file://$params" --output-s3-bucket-name $bucket --output-s3-key-prefix ssm `
    --query "Command.CommandId"
Write-Output "command $cmd on $id"
$deadline = (Get-Date).AddSeconds($Wait + 60)
do {
    Start-Sleep -Seconds 10
    $status = aws.exe ssm get-command-invocation @common --output text --command-id $cmd --instance-id $id --query "Status" 2>$null
} while ($status -in @("Pending", "InProgress", "Delayed") -and (Get-Date) -lt $deadline)
Write-Output "status: $status"
aws.exe ssm get-command-invocation @common --output text --command-id $cmd --instance-id $id --query "StandardOutputContent"
$err = aws.exe ssm get-command-invocation @common --output text --command-id $cmd --instance-id $id --query "StandardErrorContent"
if ($err -and $err.Trim()) { Write-Output "--- stderr (tail) ---"; Write-Output $err }
