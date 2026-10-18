<#
.SYNOPSIS
  Create (once) and start the TariffTrail GPU host: an SSM-managed g6.xlarge with no inbound ports.

.DESCRIPTION
  Idempotent. Creates, if missing:
    - IAM role + instance profile "TariffTrailDecider" (SSM core, Bedrock invoke, read of the code bucket)
    - S3 bucket "tariff-trail-<account>-<region>" for code and results (private, encrypted)
    - security group "tariff-trail-no-inbound" in the default VPC (egress only)
    - EC2 instance tagged Name=tariff-trail-decider from the latest DLAMI Base GPU (Ubuntu 22.04)
  If the instance exists and is stopped, starts it. Prints the instance id.

  The Decider server binds 127.0.0.1:8099 on the instance; reach it with infra/tunnel.ps1.

.EXAMPLE
  ./infra/ec2_up.ps1                      # profile "hackathon", us-east-1, g6.xlarge (GPU)
  ./infra/ec2_up.ps1 -Cpu                 # c7i.4xlarge on CPU, while the GPU quota is pending
#>
param(
    [string]$Profile = "hackathon",
    [string]$Region = "us-east-1",
    [string]$InstanceType = "",
    [switch]$Cpu,
    [int]$DiskGb = 100
)
if (-not $InstanceType) { $InstanceType = if ($Cpu) { "c7i.4xlarge" } else { "g6.xlarge" } }
$env:AWS_PAGER = ""
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$aws = @("--profile", $Profile, "--region", $Region, "--output", "text", "--no-cli-pager")
# PowerShell resolves names case-insensitively, so these helpers must call aws.exe, not "aws".
# Windows PowerShell 5.1 turns native stderr into a terminating error under "Stop", so the
# helpers relax it locally and check $LASTEXITCODE instead.
function Aws { $ErrorActionPreference = "Continue"; & aws.exe @args @aws; if ($LASTEXITCODE -ne 0) { throw "aws $($args -join ' ') failed" } }
function AwsQuiet { $ErrorActionPreference = "Continue"; $out = & aws.exe @args @aws 2>$null; if ($LASTEXITCODE -ne 0) { return $null }; return $out }

$account = Aws sts get-caller-identity --query Account
Write-Host "account $account, region $Region"

# ---- GPU quota (Running On-Demand G and VT instances, in vCPUs) ---------------------------
$quota = if ($Cpu) { $null } else { AwsQuiet service-quotas get-service-quota --service-code ec2 --quota-code L-DB2E81BA --query "Quota.Value" }
if (-not $Cpu) { Write-Host "G/VT on-demand vCPU quota: $quota" }
if ($quota -and [double]$quota -lt 4) {
    Write-Warning "Quota is below 4 vCPUs. Request it with: aws service-quotas request-service-quota-increase --service-code ec2 --quota-code L-DB2E81BA --desired-value 8 --profile $Profile --region $Region"
    exit 2
}

# ---- IAM role and instance profile ---------------------------------------------------------
$role = "TariffTrailDecider"
$bucket = "tariff-trail-$account-$Region"
if (-not (AwsQuiet iam get-role --role-name $role --query Role.Arn)) {
    $trust = Join-Path $env:TEMP "tt-trust.json"
    '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' | Set-Content -Encoding ascii $trust
    Aws iam create-role --role-name $role --assume-role-policy-document "file://$trust" | Out-Null
    Aws iam attach-role-policy --role-name $role --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
    Write-Host "created role $role"
}
$inline = Join-Path $env:TEMP "tt-inline.json"
@"
{"Version":"2012-10-17","Statement":[
 {"Effect":"Allow","Action":["bedrock:InvokeModel","bedrock:InvokeModelWithResponseStream","bedrock:Converse","bedrock:ConverseStream","bedrock:ListFoundationModels","bedrock:ListInferenceProfiles","bedrock:GetInferenceProfile"],"Resource":"*"},
 {"Effect":"Allow","Action":["s3:GetObject","s3:PutObject","s3:ListBucket"],"Resource":["arn:aws:s3:::$bucket","arn:aws:s3:::$bucket/*"]}
]}
"@ | Set-Content -Encoding ascii $inline
Aws iam put-role-policy --role-name $role --policy-name tariff-trail-access --policy-document "file://$inline"
if (-not (AwsQuiet iam get-instance-profile --instance-profile-name $role --query InstanceProfile.Arn)) {
    Aws iam create-instance-profile --instance-profile-name $role | Out-Null
    Aws iam add-role-to-instance-profile --instance-profile-name $role --role-name $role
    Write-Host "created instance profile; waiting for IAM propagation"
    Start-Sleep -Seconds 15
}

# ---- S3 bucket for code and results --------------------------------------------------------
if (-not (AwsQuiet s3api head-bucket --bucket $bucket)) {
    if ($Region -eq "us-east-1") { Aws s3api create-bucket --bucket $bucket | Out-Null }
    else { Aws s3api create-bucket --bucket $bucket --create-bucket-configuration "LocationConstraint=$Region" | Out-Null }
    Aws s3api put-public-access-block --bucket $bucket --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
    Write-Host "created bucket $bucket"
}

# ---- Existing instance? --------------------------------------------------------------------
$existing = AwsQuiet ec2 describe-instances --filters "Name=tag:Name,Values=tariff-trail-decider" "Name=instance-state-name,Values=pending,running,stopping,stopped" --query "Reservations[0].Instances[0].[InstanceId,State.Name]"
if ($existing -and $existing -notmatch "None") {
    $id, $state = $existing -split "\s+"
    if ($state -eq "stopped") { Aws ec2 start-instances --instance-ids $id | Out-Null; Write-Host "starting $id" }
    else { Write-Host "$id is $state" }
    Aws ec2 wait instance-running --instance-ids $id
    Write-Output $id
    exit 0
}

# ---- Network: default VPC, security group with no inbound rules ----------------------------
$vpc = Aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId"
$sg = AwsQuiet ec2 describe-security-groups --filters "Name=group-name,Values=tariff-trail-no-inbound" "Name=vpc-id,Values=$vpc" --query "SecurityGroups[0].GroupId"
if (-not $sg -or $sg -eq "None") {
    $sg = Aws ec2 create-security-group --group-name tariff-trail-no-inbound --description "TariffTrail: SSM only, no inbound" --vpc-id $vpc --query GroupId
}

# ---- AMI and launch ------------------------------------------------------------------------
if ($Cpu) {
    $ami = Aws ssm get-parameter --name /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id --query Parameter.Value
    $userData = Join-Path $here "userdata_cpu.sh"
} else {
    $ami = Aws ssm get-parameter --name /aws/service/deeplearning/ami/x86_64/base-oss-nvidia-driver-gpu-ubuntu-22.04/latest/ami-id --query Parameter.Value
    $userData = Join-Path $here "userdata.sh"
}
Write-Host "AMI $ami, type $InstanceType, sg $sg"
$id = Aws ec2 run-instances --image-id $ami --instance-type $InstanceType --iam-instance-profile "Name=$role" `
    --security-group-ids $sg --user-data "file://$userData" `
    --metadata-options "HttpTokens=required,HttpEndpoint=enabled" `
    --block-device-mappings "DeviceName=/dev/sda1,Ebs={VolumeSize=$DiskGb,VolumeType=gp3,Encrypted=true,DeleteOnTermination=true}" `
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=tariff-trail-decider},{Key=project,Value=tariff-trail}]" `
    --query "Instances[0].InstanceId"
Write-Host "launched $id; first boot installs the model (about 10-15 minutes)"
Aws ec2 wait instance-running --instance-ids $id
Write-Output $id
