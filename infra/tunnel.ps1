<#
.SYNOPSIS
  Forward the instance's 127.0.0.1:8099 (Strands Decider) to this machine's 127.0.0.1:8099 over SSM.
  Needs the Session Manager plugin for the AWS CLI. Leave it running; Ctrl+C to close.
#>
param(
    [string]$Profile = "hackathon",
    [string]$Region = "us-east-1",
    [int]$RemotePort = 8099,
    [int]$LocalPort = 8099
)
$ErrorActionPreference = "Stop"
$id = aws ec2 describe-instances --profile $Profile --region $Region --output text `
    --filters "Name=tag:Name,Values=tariff-trail-decider" "Name=instance-state-name,Values=running" `
    --query "Reservations[0].Instances[0].InstanceId"
if (-not $id -or $id -eq "None") { throw "no running tariff-trail-decider instance; run infra/ec2_up.ps1" }
Write-Host "forwarding localhost:$LocalPort -> $id:$RemotePort"
aws ssm start-session --profile $Profile --region $Region --target $id `
    --document-name AWS-StartPortForwardingSession `
    --parameters "portNumber=$RemotePort,localPortNumber=$LocalPort"
