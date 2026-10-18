<#
.SYNOPSIS
  Show the TariffTrail AWS resources: instance state, SSM registration, setup progress, quota requests.
#>
param([string]$Profile = "hackathon", [string]$Region = "us-east-1", [switch]$SetupLog)
$env:AWS_PAGER = ""
$aws = @("--profile", $Profile, "--region", $Region, "--output", "text", "--no-cli-pager")
$inst = aws ec2 describe-instances @aws --filters "Name=tag:Name,Values=tariff-trail-decider" "Name=instance-state-name,Values=pending,running,stopping,stopped" --query "Reservations[].Instances[].[InstanceId,InstanceType,State.Name,LaunchTime]"
Write-Output "instance:  $inst"
$id = ($inst -split "\s+")[0]
if ($id) {
    $ping = aws ssm describe-instance-information @aws --filters "Key=InstanceIds,Values=$id" --query "InstanceInformationList[].[PingStatus,PlatformName,AgentVersion]"
    Write-Output "ssm:       $ping"
}
$role = aws iam get-role --profile $Profile --output text --no-cli-pager --role-name TariffTrailDecider --query "Role.Arn" 2>$null
Write-Output "role:      $role"
$account = aws sts get-caller-identity --profile $Profile --output text --no-cli-pager --query Account
aws s3api head-bucket --profile $Profile --bucket "tariff-trail-$account-$Region" 2>$null
Write-Output ("bucket:    tariff-trail-$account-$Region " + $(if ($LASTEXITCODE -eq 0) { "exists" } else { "missing" }))
$quotas = aws service-quotas list-requested-service-quota-change-history @aws --service-code ec2 --query "RequestedQuotas[].[QuotaName,DesiredValue,Status]"
Write-Output "gpu quota requests:`n$quotas"
if ($SetupLog -and $id) {
    $cmd = aws ssm send-command @aws --instance-ids $id --document-name AWS-RunShellScript `
        --parameters 'commands=["tail -n 15 /var/log/tariff-trail-setup.log","systemctl is-active strands-decider || true","curl -s -m 5 127.0.0.1:8099/health || echo no-health"]' `
        --query "Command.CommandId"
    Start-Sleep -Seconds 6
    aws ssm get-command-invocation @aws --command-id $cmd --instance-id $id --query "StandardOutputContent"
}
