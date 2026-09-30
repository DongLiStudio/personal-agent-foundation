[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('save', 'probe', 'search', 'download', 'remove')]
    [string]$Action,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$Profile,

    [string]$HostName,
    [int]$Port = 993,
    [string]$Username,
    [string]$Mailbox = 'INBOX',
    [string]$Query = 'ALL',
    [int]$Limit = 50,
    [string]$Uids,
    [string]$Output,
    [switch]$AllowSelectFallback
)

$ErrorActionPreference = 'Stop'
$slotRoot = Join-Path $env:LOCALAPPDATA 'Codex\mail-profiles'
$credentialPath = Join-Path $slotRoot "$Profile.credential.clixml"
$metadataPath = Join-Path $slotRoot "$Profile.metadata.json"
$imapScript = Join-Path $PSScriptRoot 'imap_readonly.py'

function Write-Result([hashtable]$Value) {
    $Value | ConvertTo-Json -Depth 6
}

function Read-Metadata {
    if (-not (Test-Path -LiteralPath $metadataPath)) {
        throw "mail profile metadata not found: $Profile"
    }
    Get-Content -LiteralPath $metadataPath -Raw -Encoding UTF8 | ConvertFrom-Json
}

switch ($Action) {
    'save' {
        if (-not $HostName -or -not $Username) {
            throw 'save requires -HostName and -Username'
        }
        New-Item -ItemType Directory -Path $slotRoot -Force | Out-Null
        $secret = Read-Host '请输入邮箱客户端授权码（输入内容会被隐藏）' -AsSecureString
        if ($secret.Length -eq 0) {
            throw 'empty authorization code'
        }
        $credential = [System.Management.Automation.PSCredential]::new($Username, $secret)
        $credential | Export-Clixml -LiteralPath $credentialPath -Force
        @{
            profile = $Profile
            host = $HostName
            port = $Port
            username = $Username
            provider = 'imap'
            saved_at = (Get-Date).ToString('o')
        } | ConvertTo-Json | Set-Content -LiteralPath $metadataPath -Encoding UTF8
        Write-Result @{ ok = $true; profile = $Profile; username = $Username; storage = 'Windows CurrentUser DPAPI' }
    }
    'probe' {
        $metadata = Read-Metadata
        if (-not (Test-Path -LiteralPath $credentialPath)) {
            throw "mail profile credential not found: $Profile"
        }
        $credential = Import-Clixml -LiteralPath $credentialPath
        $plain = $credential.GetNetworkCredential().Password
        try {
            $env:AGENT_MAIL_SECRET = $plain
            & python $imapScript --host $metadata.host --port ([int]$metadata.port) --username $metadata.username probe
            if ($LASTEXITCODE -ne 0) {
                throw "IMAP probe failed with exit code $LASTEXITCODE"
            }
        }
        finally {
            Remove-Item Env:AGENT_MAIL_SECRET -ErrorAction SilentlyContinue
            $plain = $null
        }
    }
    'search' {
        $metadata = Read-Metadata
        if (-not (Test-Path -LiteralPath $credentialPath)) {
            throw "mail profile credential not found: $Profile"
        }
        $credential = Import-Clixml -LiteralPath $credentialPath
        $plain = $credential.GetNetworkCredential().Password
        try {
            $env:AGENT_MAIL_SECRET = $plain
            if ($AllowSelectFallback) {
                & python $imapScript --host $metadata.host --port ([int]$metadata.port) --username $metadata.username search --mailbox $Mailbox --query $Query --limit $Limit --allow-select-fallback
            }
            else {
                & python $imapScript --host $metadata.host --port ([int]$metadata.port) --username $metadata.username search --mailbox $Mailbox --query $Query --limit $Limit
            }
            if ($LASTEXITCODE -ne 0) {
                throw "IMAP search failed with exit code $LASTEXITCODE"
            }
        }
        finally {
            Remove-Item Env:AGENT_MAIL_SECRET -ErrorAction SilentlyContinue
            $plain = $null
        }
    }
    'download' {
        if (-not $Uids -or -not $Output) {
            throw 'download requires -Uids and -Output'
        }
        $metadata = Read-Metadata
        if (-not (Test-Path -LiteralPath $credentialPath)) {
            throw "mail profile credential not found: $Profile"
        }
        $credential = Import-Clixml -LiteralPath $credentialPath
        $plain = $credential.GetNetworkCredential().Password
        try {
            $env:AGENT_MAIL_SECRET = $plain
            if ($AllowSelectFallback) {
                & python $imapScript --host $metadata.host --port ([int]$metadata.port) --username $metadata.username download --mailbox $Mailbox --uids $Uids --output $Output --allow-select-fallback
            }
            else {
                & python $imapScript --host $metadata.host --port ([int]$metadata.port) --username $metadata.username download --mailbox $Mailbox --uids $Uids --output $Output
            }
            if ($LASTEXITCODE -ne 0) {
                throw "IMAP download failed with exit code $LASTEXITCODE"
            }
        }
        finally {
            Remove-Item Env:AGENT_MAIL_SECRET -ErrorAction SilentlyContinue
            $plain = $null
        }
    }
    'remove' {
        Remove-Item -LiteralPath $credentialPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $metadataPath -Force -ErrorAction SilentlyContinue
        Write-Result @{ ok = $true; profile = $Profile; removed = $true }
    }
}
