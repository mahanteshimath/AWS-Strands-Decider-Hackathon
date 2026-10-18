<#
.SYNOPSIS
  Create a monthly AWS Budget for the hackathon account that emails at 80% of the limit.
#>
param(
    [Parameter(Mandatory = $true)][string]$Email,
    [string]$Profile = "hackathon",
    [int]$LimitUsd = 50
)
$ErrorActionPreference = "Stop"
$account = aws sts get-caller-identity --profile $Profile --query Account --output text
$budget = Join-Path $env:TEMP "tt-budget.json"
$notify = Join-Path $env:TEMP "tt-notify.json"
"{`"BudgetName`":`"tariff-trail-hackathon`",`"BudgetLimit`":{`"Amount`":`"$LimitUsd`",`"Unit`":`"USD`"},`"TimeUnit`":`"MONTHLY`",`"BudgetType`":`"COST`"}" | Set-Content -Encoding ascii $budget
"[{`"Notification`":{`"NotificationType`":`"ACTUAL`",`"ComparisonOperator`":`"GREATER_THAN`",`"Threshold`":80,`"ThresholdType`":`"PERCENTAGE`"},`"Subscribers`":[{`"SubscriptionType`":`"EMAIL`",`"Address`":`"$Email`"}]}]" | Set-Content -Encoding ascii $notify
aws budgets create-budget --profile $Profile --account-id $account --budget "file://$budget" --notifications-with-subscribers "file://$notify"
if ($LASTEXITCODE -eq 0) { Write-Host "budget tariff-trail-hackathon: $LimitUsd USD/month, alert at 80% to $Email" }
