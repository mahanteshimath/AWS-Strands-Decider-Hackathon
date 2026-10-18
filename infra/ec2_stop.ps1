<#
.SYNOPSIS
  Stop the TariffTrail GPU instance (keeps the disk, so the next start is warm). Use -Terminate to delete it.
#>
param(
    [string]$Profile = "hackathon",
    [string]$Region = "us-east-1",
    [switch]$Terminate
)
$ErrorActionPreference = "Stop"
$ids = aws ec2 describe-instances --profile $Profile --region $Region --output text `
    --filters "Name=tag:Name,Values=tariff-trail-decider" "Name=instance-state-name,Values=pending,running,stopping,stopped" `
    --query "Reservations[].Instances[].InstanceId"
if (-not $ids) { Write-Host "no tariff-trail-decider instance"; exit 0 }
if ($Terminate) {
    aws ec2 terminate-instances --profile $Profile --region $Region --instance-ids $ids | Out-Null
    Write-Host "terminating $ids"
} else {
    aws ec2 stop-instances --profile $Profile --region $Region --instance-ids $ids | Out-Null
    Write-Host "stopping $ids"
}
