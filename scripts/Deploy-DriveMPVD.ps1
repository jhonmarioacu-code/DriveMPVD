[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidatePattern('^[A-Za-z0-9.-]+$')]
    [string]$Server,

    [Parameter(Mandatory)]
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$User,

    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string]$IdentityFile,

    [Parameter(Mandatory)]
    [ValidatePattern('^(https://|ssh://|git@)[A-Za-z0-9._:/@-]+$')]
    [string]$Repository,

    [Parameter(Mandatory)]
    [ValidatePattern('^[A-Za-z0-9._/-]+$')]
    [string]$Release,

    [ValidateSet('validation', 'production')]
    [string]$Mode = 'validation',

    [ValidatePattern('^/[A-Za-z0-9._/-]+$')]
    [string]$InstallDir = '/srv/drivempvd',

    [ValidatePattern('^[A-Za-z0-9.-]+$')]
    [string]$Domain,

    [ValidatePattern('^[^\s@]+@[^\s@]+$')]
    [string]$Email,

    [ValidatePattern('^[A-Za-z0-9._-]{1,100}$')]
    [string]$AdminUser = 'admin',

    [switch]$SkipSmoke,
    [switch]$SkipSystemUpdate
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($Mode -eq 'production' -and ([string]::IsNullOrWhiteSpace($Domain) -or [string]::IsNullOrWhiteSpace($Email))) {
    throw 'Production requires -Domain and -Email for DNS/TLS validation.'
}
if (-not (Test-Path -LiteralPath $IdentityFile -PathType Leaf)) {
    throw "SSH identity file does not exist: $IdentityFile"
}
foreach ($command in @('git', 'ssh', 'scp')) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        throw "Required command is unavailable: $command"
    }
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$installer = Join-Path $projectRoot 'docker/install-vps.sh'
if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) {
    throw "Installer is missing: $installer"
}

$resolvedRelease = (& git -C $projectRoot rev-parse --verify "$Release^{commit}").Trim()
if ($LASTEXITCODE -ne 0 -or $resolvedRelease -notmatch '^[0-9a-f]{40}$') {
    throw 'Release must resolve locally to a full Git commit SHA.'
}
$head = (& git -C $projectRoot rev-parse --verify HEAD).Trim()
if ($head -ne $resolvedRelease) {
    throw 'Checkout HEAD must equal -Release; deploy the reviewed release, not a different working tree.'
}
$dirty = @(& git -C $projectRoot status --porcelain)
if ($LASTEXITCODE -ne 0 -or $dirty.Count -ne 0) {
    throw 'Refusing to upload an installer from a dirty checkout.'
}

$remoteInstaller = "/tmp/drivempvd-install-vps-$($resolvedRelease.Substring(0, 12)).sh"
$sshTarget = "$User@$Server"
$sshOptions = @('-i', $IdentityFile, '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=yes')
$scpDestination = $sshTarget + ':' + $remoteInstaller

& scp @sshOptions $installer $scpDestination
if ($LASTEXITCODE -ne 0) { throw 'Unable to upload the verified installer to the VPS.' }

$arguments = @(
    '--mode', $Mode,
    '--repository', $Repository,
    '--release', $Release,
    '--install-dir', $InstallDir,
    '--admin-user', $AdminUser
)
if ($Mode -eq 'production') {
    $arguments += @('--domain', $Domain, '--email', $Email)
}
if ($SkipSmoke) { $arguments += '--skip-smoke' }
if ($SkipSystemUpdate) { $arguments += '--skip-system-update' }

function ConvertTo-BashSingleQuoted([string]$Value) {
    if ($Value.Contains("'")) {
        throw 'Single quotes are not permitted in remote installer arguments.'
    }
    return "'" + $Value + "'"
}

$quotedArguments = ($arguments | ForEach-Object { ConvertTo-BashSingleQuoted $_ }) -join ' '
$quotedInstaller = ConvertTo-BashSingleQuoted $remoteInstaller
$remoteCommand = "set -eu; trap 'rm -f -- $remoteInstaller' EXIT; sudo bash $quotedInstaller $quotedArguments"
& ssh @sshOptions $sshTarget $remoteCommand
if ($LASTEXITCODE -ne 0) { throw 'The VPS installer failed; inspect the remote command output.' }
