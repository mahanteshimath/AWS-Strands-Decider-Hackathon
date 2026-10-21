<#
.SYNOPSIS
  Rebuild the replay-only demo site and deploy it to AWS Amplify Hosting (manual zip deploy).

.EXAMPLE
  ./infra/deploy_site.ps1                       # replay-only copy, app "tarifftrail-demo", branch main
  ./infra/deploy_site.ps1 -ApiUrl https://xxxx.lambda-url.us-east-1.on.aws   # plus Classify hosted, Simulate, New product (see infra/deploy_api.ps1)
#>
param(
    [string]$Profile = "hackathon",
    [string]$Region = "us-east-1",
    [string]$AppName = "tarifftrail-demo",
    [string]$Branch = "main",
    [string]$ApiUrl = "",
    [string]$Python = "python"
)
$ErrorActionPreference = "Continue"
$env:AWS_PAGER = ""
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$common = @("--profile", $Profile, "--region", $Region)
Set-Location $root

$exportArgs = @(); if ($ApiUrl) { $exportArgs = @("--api", $ApiUrl) }
& $Python scripts\export_static.py @exportArgs
& $Python -c "import zipfile,pathlib; r=pathlib.Path('site'); z=zipfile.ZipFile('site.zip','w',zipfile.ZIP_DEFLATED); [z.write(p,p.relative_to(r).as_posix()) for p in r.rglob('*') if p.is_file()]; z.close()"

$id = aws.exe amplify list-apps @common --query "apps[?name=='$AppName'].appId | [0]" --output text
if (-not $id -or $id -eq "None") {
    $id = aws.exe amplify create-app --name $AppName --platform WEB @common --query app.appId --output text
    aws.exe amplify create-branch --app-id $id --branch-name $Branch --stage PRODUCTION @common | Out-Null
}
$dep = aws.exe amplify create-deployment --app-id $id --branch-name $Branch @common --output json | ConvertFrom-Json
curl.exe -s -S -T site.zip -H "Content-Type: application/zip" $dep.zipUploadUrl -o NUL
aws.exe amplify start-deployment --app-id $id --branch-name $Branch --job-id $dep.jobId @common | Out-Null
do {
    Start-Sleep -Seconds 5
    $status = aws.exe amplify get-job --app-id $id --branch-name $Branch --job-id $dep.jobId @common --query job.summary.status --output text
} while ($status -in @("PENDING", "PROVISIONING", "RUNNING"))
Remove-Item site.zip -ErrorAction SilentlyContinue
Write-Output "$status  https://$Branch.$id.amplifyapp.com/"
