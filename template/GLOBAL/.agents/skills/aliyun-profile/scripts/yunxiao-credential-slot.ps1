[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('connect', 'status', 'verify', 'run', 'remove', 'self-test')]
    [string]$Action,

    [string]$SlotName = '<云效逻辑 Profile>',
    [string]$OrganizationId,
    [string]$AliyunPath,
    [string]$StoreRoot,
    [string]$DevopsCommand,
    [string[]]$DevopsArguments = @(),
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-Windows {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw 'Persistent Yunxiao credential slots currently require Windows DPAPI. Use hidden one-session injection on other hosts.'
    }
}

function Get-DefaultStoreRoot {
    if (-not [string]::IsNullOrWhiteSpace($StoreRoot)) {
        return [IO.Path]::GetFullPath($StoreRoot)
    }
    if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        throw 'LOCALAPPDATA is unavailable.'
    }
    return (Join-Path $env:LOCALAPPDATA 'DongLi\AgentFoundation\credentials\aliyun-yunxiao')
}

function Get-SlotFile {
    param([Parameter(Mandatory = $true)][string]$Name)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($Name)
        $hash = ([BitConverter]::ToString($sha.ComputeHash($bytes)) -replace '-', '').ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
    return (Join-Path (Get-DefaultStoreRoot) ("slot-{0}.json" -f $hash))
}

function Get-EntropyBytes {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$OrgId
    )
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return $sha.ComputeHash([Text.Encoding]::UTF8.GetBytes("aliyun-profile|$Name|$OrgId"))
    }
    finally {
        $sha.Dispose()
    }
}

function Protect-SecureSecret {
    param(
        [Parameter(Mandatory = $true)][Security.SecureString]$Secret,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$OrgId
    )
    Add-Type -AssemblyName System.Security -ErrorAction SilentlyContinue
    $bstr = [IntPtr]::Zero
    $plainBytes = $null
    $entropy = $null
    $protectedBytes = $null
    try {
        $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secret)
        $plainBytes = New-Object byte[] ($Secret.Length * 2)
        [Runtime.InteropServices.Marshal]::Copy($bstr, $plainBytes, 0, $plainBytes.Length)
        $entropy = Get-EntropyBytes -Name $Name -OrgId $OrgId
        $protectedBytes = [System.Security.Cryptography.ProtectedData]::Protect(
            $plainBytes,
            $entropy,
            [System.Security.Cryptography.DataProtectionScope]::CurrentUser
        )
        return [Convert]::ToBase64String($protectedBytes)
    }
    finally {
        if ($bstr -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }
        if ($null -ne $plainBytes) { [Array]::Clear($plainBytes, 0, $plainBytes.Length) }
        if ($null -ne $entropy) { [Array]::Clear($entropy, 0, $entropy.Length) }
        if ($null -ne $protectedBytes) { [Array]::Clear($protectedBytes, 0, $protectedBytes.Length) }
    }
}

function Unprotect-SecureSecret {
    param(
        [Parameter(Mandatory = $true)][string]$Ciphertext,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$OrgId
    )
    Add-Type -AssemblyName System.Security -ErrorAction SilentlyContinue
    $protectedBytes = $null
    $entropy = $null
    $plainBytes = $null
    try {
        $protectedBytes = [Convert]::FromBase64String($Ciphertext)
        $entropy = Get-EntropyBytes -Name $Name -OrgId $OrgId
        $plainBytes = [System.Security.Cryptography.ProtectedData]::Unprotect(
            $protectedBytes,
            $entropy,
            [System.Security.Cryptography.DataProtectionScope]::CurrentUser
        )
        if (($plainBytes.Length % 2) -ne 0) {
            throw 'Credential slot plaintext has an invalid UTF-16 byte length.'
        }
        $secure = New-Object Security.SecureString
        for ($index = 0; $index -lt $plainBytes.Length; $index += 2) {
            $character = [char]([int]$plainBytes[$index] -bor ([int]$plainBytes[$index + 1] -shl 8))
            $secure.AppendChar($character)
        }
        $secure.MakeReadOnly()
        return $secure
    }
    finally {
        if ($null -ne $protectedBytes) { [Array]::Clear($protectedBytes, 0, $protectedBytes.Length) }
        if ($null -ne $entropy) { [Array]::Clear($entropy, 0, $entropy.Length) }
        if ($null -ne $plainBytes) { [Array]::Clear($plainBytes, 0, $plainBytes.Length) }
    }
}

function Set-PrivateAcl {
    param([Parameter(Mandatory = $true)][string]$Path)
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    if ($null -eq $sid) {
        throw 'Cannot resolve the current Windows user SID.'
    }
    & icacls.exe $Path '/inheritance:r' '/grant:r' ("*{0}:(F)" -f $sid.Value) | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to restrict credential slot ACL: $Path"
    }
}

function Resolve-AliyunExecutable {
    if (-not [string]::IsNullOrWhiteSpace($AliyunPath)) {
        $resolved = [IO.Path]::GetFullPath($AliyunPath)
        if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
            throw "Aliyun CLI was not found at the requested path: $resolved"
        }
        return $resolved
    }
    $command = Get-Command aliyun -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }
    $fallback = Join-Path $env:LOCALAPPDATA 'AliyunCLI\aliyun.exe'
    if (Test-Path -LiteralPath $fallback -PathType Leaf) {
        return $fallback
    }
    throw 'Aliyun CLI was not found. Install it before connecting a Yunxiao credential slot.'
}

function Write-Slot {
    param(
        [Parameter(Mandatory = $true)][Security.SecureString]$Secret,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$OrgId
    )
    $slotFile = Get-SlotFile -Name $Name
    $directory = Split-Path -Parent $slotFile
    [IO.Directory]::CreateDirectory($directory) | Out-Null
    $now = [DateTimeOffset]::Now.ToString('o')
    $createdAt = $now
    if (Test-Path -LiteralPath $slotFile -PathType Leaf) {
        try {
            $existing = Get-Content -LiteralPath $slotFile -Raw -Encoding UTF8 | ConvertFrom-Json
            if (-not [string]::IsNullOrWhiteSpace([string]$existing.created_at)) {
                $createdAt = [string]$existing.created_at
            }
        }
        catch {
            throw 'The existing credential slot is malformed. Refusing to overwrite it.'
        }
    }
    $payload = [ordered]@{
        schema_version = 1
        slot_name = $Name
        organization_id = $OrgId
        protection = 'windows-dpapi-current-user'
        created_at = $createdAt
        updated_at = $now
        ciphertext = Protect-SecureSecret -Secret $Secret -Name $Name -OrgId $OrgId
    }
    $tempFile = "$slotFile.tmp-$([Guid]::NewGuid().ToString('N'))"
    try {
        $json = $payload | ConvertTo-Json -Depth 3
        [IO.File]::WriteAllText($tempFile, $json, [Text.UTF8Encoding]::new($false))
        Set-PrivateAcl -Path $tempFile
        Move-Item -LiteralPath $tempFile -Destination $slotFile -Force
        Set-PrivateAcl -Path $slotFile
    }
    finally {
        if (Test-Path -LiteralPath $tempFile) {
            Remove-Item -LiteralPath $tempFile -Force
        }
    }
    return $slotFile
}

function Read-Slot {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [string]$ExpectedOrganizationId
    )
    $slotFile = Get-SlotFile -Name $Name
    if (-not (Test-Path -LiteralPath $slotFile -PathType Leaf)) {
        throw "Credential slot '$Name' does not exist on this Windows host."
    }
    $payload = Get-Content -LiteralPath $slotFile -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([int]$payload.schema_version -ne 1 -or [string]$payload.slot_name -ne $Name) {
        throw 'Credential slot metadata does not match the requested logical slot.'
    }
    if (-not [string]::IsNullOrWhiteSpace($ExpectedOrganizationId) -and
        [string]$payload.organization_id -ne $ExpectedOrganizationId) {
        throw 'Credential slot organization ID does not match the requested organization.'
    }
    try {
        $secret = Unprotect-SecureSecret -Ciphertext ([string]$payload.ciphertext) -Name $Name -OrgId ([string]$payload.organization_id)
    }
    catch {
        throw 'Credential slot cannot be decrypted by the current Windows user. Reconnect this slot on this host.'
    }
    return [pscustomobject]@{
        Path = $slotFile
        SlotName = [string]$payload.slot_name
        OrganizationId = [string]$payload.organization_id
        UpdatedAt = [string]$payload.updated_at
        Secret = $secret
    }
}

function Invoke-WithYunxiaoSecret {
    param(
        [Parameter(Mandatory = $true)][Security.SecureString]$Secret,
        [Parameter(Mandatory = $true)][string]$OrgId,
        [Parameter(Mandatory = $true)][scriptblock]$Script
    )
    $bstr = [IntPtr]::Zero
    try {
        $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secret)
        $env:ALIBABA_CLOUD_YUNXIAO_ACCESS_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
        $env:ALIBABA_CLOUD_YUNXIAO_ORGANIZATION_ID = $OrgId
        & $Script
    }
    finally {
        Remove-Item Env:ALIBABA_CLOUD_YUNXIAO_ACCESS_TOKEN -ErrorAction SilentlyContinue
        Remove-Item Env:ALIBABA_CLOUD_YUNXIAO_ORGANIZATION_ID -ErrorAction SilentlyContinue
        if ($bstr -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }
    }
}

function Invoke-Verification {
    param(
        [Parameter(Mandatory = $true)][Security.SecureString]$Secret,
        [Parameter(Mandatory = $true)][string]$OrgId
    )
    $aliyun = Resolve-AliyunExecutable
    return Invoke-WithYunxiaoSecret -Secret $Secret -OrgId $OrgId -Script {
        $userOutput = & $aliyun devops base-get-user-by-token 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw 'Yunxiao user readback failed. The secret was not stored.'
        }
        $orgOutput = & $aliyun devops base-list-organizations 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw 'Yunxiao organization readback failed. The secret was not stored.'
        }
        $orgText = ($orgOutput | Out-String)
        if ($orgText -notmatch [Regex]::Escape($OrgId)) {
            throw 'The configured organization ID was not present in the organization readback. The secret was not stored.'
        }
        [pscustomobject]@{
            ok = $true
            user_readback = $true
            organization_readback = $true
            organization_id = $OrgId
        }
    }
}

function Invoke-SelfTest {
    $testRoot = Join-Path ([IO.Path]::GetTempPath()) ("yunxiao-slot-test-{0}" -f [Guid]::NewGuid().ToString('N'))
    $oldStoreRoot = $script:StoreRoot
    try {
        $script:StoreRoot = $testRoot
        $plain = "test-only-$([Guid]::NewGuid().ToString('N'))"
        $secure = New-Object Security.SecureString
        foreach ($character in $plain.ToCharArray()) {
            $secure.AppendChar($character)
        }
        $secure.MakeReadOnly()
        $slotPath = Write-Slot -Secret $secure -Name 'self-test' -OrgId 'test-org'
        $raw = Get-Content -LiteralPath $slotPath -Raw -Encoding UTF8
        if ($raw.Contains($plain)) {
            throw 'Self-test detected plaintext secret material in the slot file.'
        }
        $loaded = Read-Slot -Name 'self-test' -ExpectedOrganizationId 'test-org'
        $acl = Get-Acl -LiteralPath $slotPath
        if (-not $acl.AreAccessRulesProtected) {
            throw 'Self-test detected inherited ACLs on the credential slot.'
        }
        $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($loaded.Secret)
        try {
            $roundTrip = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
        }
        finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }
        if ($roundTrip -ne $plain) {
            throw 'Self-test DPAPI round trip failed.'
        }
        $injected = Invoke-WithYunxiaoSecret -Secret $loaded.Secret -OrgId 'test-org' -Script {
            [pscustomobject]@{
                token_present = -not [string]::IsNullOrWhiteSpace($env:ALIBABA_CLOUD_YUNXIAO_ACCESS_TOKEN)
                organization_id = $env:ALIBABA_CLOUD_YUNXIAO_ORGANIZATION_ID
            }
        }
        if (-not $injected.token_present -or $injected.organization_id -ne 'test-org') {
            throw 'Self-test process-scoped injection failed.'
        }
        if ((Test-Path Env:ALIBABA_CLOUD_YUNXIAO_ACCESS_TOKEN) -or
            (Test-Path Env:ALIBABA_CLOUD_YUNXIAO_ORGANIZATION_ID)) {
            throw 'Self-test detected credential environment residue after command completion.'
        }
        [pscustomobject]@{ ok = $true; test = 'windows-dpapi-slot-roundtrip' }
    }
    finally {
        $script:StoreRoot = $oldStoreRoot
        if (Test-Path -LiteralPath $testRoot) {
            Remove-Item -LiteralPath $testRoot -Recurse -Force
        }
    }
}

Assert-Windows

switch ($Action) {
    'connect' {
        if ([string]::IsNullOrWhiteSpace($OrganizationId)) {
            throw 'OrganizationId is required for connect.'
        }
        $existingSlot = Get-SlotFile -Name $SlotName
        if ((Test-Path -LiteralPath $existingSlot -PathType Leaf) -and -not $Force) {
            throw "Credential slot '$SlotName' already exists. Reconnecting requires -Force after explicit user authorization."
        }
        $secret = Read-Host 'Paste the Yunxiao PAT (input is hidden)' -AsSecureString
        $verification = Invoke-Verification -Secret $secret -OrgId $OrganizationId
        $slotPath = Write-Slot -Secret $secret -Name $SlotName -OrgId $OrganizationId
        [pscustomobject]@{
            ok = $verification.ok
            slot_name = $SlotName
            organization_id = $OrganizationId
            protection = 'windows-dpapi-current-user'
            stored = $true
            slot_path = $slotPath
        } | ConvertTo-Json -Depth 3
    }
    'status' {
        $slotFile = Get-SlotFile -Name $SlotName
        if (-not (Test-Path -LiteralPath $slotFile -PathType Leaf)) {
            [pscustomobject]@{ ok = $true; slot_name = $SlotName; exists = $false } | ConvertTo-Json
            break
        }
        $loaded = Read-Slot -Name $SlotName -ExpectedOrganizationId $OrganizationId
        [pscustomobject]@{
            ok = $true
            slot_name = $loaded.SlotName
            organization_id = $loaded.OrganizationId
            exists = $true
            decryptable = $true
            updated_at = $loaded.UpdatedAt
            protection = 'windows-dpapi-current-user'
        } | ConvertTo-Json
    }
    'verify' {
        $loaded = Read-Slot -Name $SlotName -ExpectedOrganizationId $OrganizationId
        Invoke-Verification -Secret $loaded.Secret -OrgId $loaded.OrganizationId | ConvertTo-Json
    }
    'run' {
        if ([string]::IsNullOrWhiteSpace($DevopsCommand)) {
            throw 'DevopsCommand is required for run.'
        }
        if ($DevopsArguments -contains '--yunxiao-access-token' -or $DevopsArguments -contains '--organization-id') {
            throw 'Do not pass Yunxiao credentials or organization ID in command arguments.'
        }
        $loaded = Read-Slot -Name $SlotName -ExpectedOrganizationId $OrganizationId
        $aliyun = Resolve-AliyunExecutable
        Invoke-WithYunxiaoSecret -Secret $loaded.Secret -OrgId $loaded.OrganizationId -Script {
            & $aliyun devops $DevopsCommand @DevopsArguments
            if ($LASTEXITCODE -ne 0) {
                throw "Yunxiao command failed with exit code $LASTEXITCODE."
            }
        }
    }
    'remove' {
        if (-not $Force) {
            throw 'Removing a credential slot requires -Force after explicit user authorization.'
        }
        $slotFile = Get-SlotFile -Name $SlotName
        if (Test-Path -LiteralPath $slotFile -PathType Leaf) {
            Remove-Item -LiteralPath $slotFile -Force
        }
        [pscustomobject]@{ ok = $true; slot_name = $SlotName; removed = $true } | ConvertTo-Json
    }
    'self-test' {
        Invoke-SelfTest | ConvertTo-Json
    }
}
