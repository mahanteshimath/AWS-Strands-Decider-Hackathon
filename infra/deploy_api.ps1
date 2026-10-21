<#
.SYNOPSIS
  Build the TariffTrail API and deploy it to AWS Lambda behind a streaming Function URL.

.DESCRIPTION
  Creates (or updates) the IAM role, the function, its public Function URL (CORS limited to the demo origins),
  and a reserved-concurrency ceiling. The hosted Decider key is read from .env (aws_strands_decider_key or
  DECIDER_API_KEY) and set as the function's DECIDER_API_KEY; it is never printed or written to the repo.

.EXAMPLE
  ./infra/deploy_api.ps1
#>
param(
    [string]$Profile = "hackathon",
    [string]$Region = "us-east-1",
    [string]$FunctionName = "tarifftrail-api",
    [string]$RoleName = "TariffTrailApi",
    [string]$Bucket = "tariff-trail-686112930486-us-east-1",
    [string[]]$Origins = @("https://main.d3o5ktn9yc15oj.amplifyapp.com", "http://127.0.0.1:8000", "http://localhost:8000"),
    [int]$ReservedConcurrency = 4,
    [int]$MemoryMb = 2048,
    [string]$ReasonerModel = "us.amazon.nova-pro-v1:0",
    [string]$Python = "python"
)
$ErrorActionPreference = "Continue"
$env:AWS_PAGER = ""
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$common = @("--profile", $Profile, "--region", $Region)
$tmp = Join-Path $env:TEMP "tt_api_deploy"
New-Item -ItemType Directory -Force $tmp | Out-Null
Set-Location $root

function Step($text) { Write-Output "`n== $text" }

Step "build package"
& $Python infra\build_lambda.py
if ($LASTEXITCODE -ne 0) { throw "build failed" }

Step "upload to s3://$Bucket/lambda/"
aws.exe s3 cp build\lambda\tarifftrail-api.zip "s3://$Bucket/lambda/tarifftrail-api.zip" @common --only-show-errors

Step "IAM role $RoleName"
$account = aws.exe sts get-caller-identity @common --query Account --output text
$roleArn = "arn:aws:iam::${account}:role/$RoleName"
aws.exe iam get-role --role-name $RoleName @common 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Set-Content -Encoding ascii "$tmp\trust.json" '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
    aws.exe iam create-role --role-name $RoleName --assume-role-policy-document "file://$tmp/trust.json" @common --query Role.Arn --output text
    aws.exe iam attach-role-policy --role-name $RoleName --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole @common
    Start-Sleep -Seconds 10
}
Set-Content -Encoding ascii "$tmp\policy.json" '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["bedrock:InvokeModel","bedrock:Converse"],"Resource":"*"}]}'
aws.exe iam put-role-policy --role-name $RoleName --policy-name bedrock-invoke --policy-document "file://$tmp/policy.json" @common

Step "environment"
$key = ""
foreach ($line in Get-Content (Join-Path $root ".env") -ErrorAction SilentlyContinue) {
    if ($line -match '^\s*(aws_strands_decider_key|DECIDER_API_KEY)\s*=\s*(.+?)\s*$') { $key = $Matches[2].Trim('"', "'"); break }
}
if (-not $key) { Write-Output "WARNING: no hosted Decider key in .env; Classify hosted will be unavailable" }
$vars = [ordered]@{
    AWS_LAMBDA_EXEC_WRAPPER = "/opt/bootstrap"
    AWS_LWA_INVOKE_MODE     = "response_stream"
    AWS_LWA_ASYNC_INIT      = "true"
    PORT                    = "8080"
    TT_PUBLIC               = "1"
    TT_DISABLE_LOCAL        = "1"
    TT_REASONER_MODEL       = $ReasonerModel
}
if ($key) { $vars["DECIDER_API_KEY"] = $key }
@{ Variables = $vars } | ConvertTo-Json -Depth 4 | Set-Content -Encoding ascii "$tmp\env.json"

Step "function $FunctionName"
$layer = "arn:aws:lambda:${Region}:753240598075:layer:LambdaAdapterLayerX86:30"
aws.exe lambda get-function --function-name $FunctionName @common 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    for ($i = 0; $i -lt 6; $i++) {
        aws.exe lambda create-function --function-name $FunctionName --runtime python3.12 --handler run.sh --architectures x86_64 `
            --role $roleArn --code "S3Bucket=$Bucket,S3Key=lambda/tarifftrail-api.zip" --timeout 900 --memory-size $MemoryMb `
            --layers $layer --environment "file://$tmp/env.json" @common --query FunctionArn --output text
        if ($LASTEXITCODE -eq 0) { break }
        Start-Sleep -Seconds 8   # a new role can take a moment to become assumable
    }
} else {
    aws.exe lambda update-function-code --function-name $FunctionName --s3-bucket $Bucket --s3-key lambda/tarifftrail-api.zip @common --query LastUpdateStatus --output text
    aws.exe lambda wait function-updated --function-name $FunctionName @common
    aws.exe lambda update-function-configuration --function-name $FunctionName --runtime python3.12 --handler run.sh `
        --timeout 900 --memory-size $MemoryMb --layers $layer --environment "file://$tmp/env.json" @common --query LastUpdateStatus --output text
}
aws.exe lambda wait function-updated --function-name $FunctionName @common
aws.exe lambda wait function-active --function-name $FunctionName @common

Step "reserved concurrency $ReservedConcurrency"
aws.exe lambda put-function-concurrency --function-name $FunctionName --reserved-concurrent-executions $ReservedConcurrency @common --query ReservedConcurrentExecutions --output text

Step "function URL"
@{ AllowOrigins = $Origins; AllowMethods = @("GET", "POST"); AllowHeaders = @("content-type"); MaxAge = 86400 } | ConvertTo-Json -Depth 4 | Set-Content -Encoding ascii "$tmp\cors.json"
aws.exe lambda get-function-url-config --function-name $FunctionName @common 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    aws.exe lambda create-function-url-config --function-name $FunctionName --auth-type NONE --invoke-mode RESPONSE_STREAM --cors "file://$tmp/cors.json" @common --query FunctionUrl --output text
    aws.exe lambda add-permission --function-name $FunctionName --statement-id FunctionURLAllowPublicAccess --action lambda:InvokeFunctionUrl --principal "*" --function-url-auth-type NONE @common --query Statement --output text | Out-Null
    aws.exe lambda add-permission --function-name $FunctionName --statement-id FunctionURLAllowInvokeAction --action lambda:InvokeFunction --principal "*" --invoked-via-function-url @common --query Statement --output text | Out-Null
} else {
    aws.exe lambda update-function-url-config --function-name $FunctionName --auth-type NONE --invoke-mode RESPONSE_STREAM --cors "file://$tmp/cors.json" @common --query FunctionUrl --output text
}
$url = aws.exe lambda get-function-url-config --function-name $FunctionName @common --query FunctionUrl --output text
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
Write-Output "`nAPI URL: $url"
