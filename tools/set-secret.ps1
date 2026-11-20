# Sets one variable in the git-ignored .env without showing the value on screen, in the shell history or in a chat.
#   powershell -ExecutionPolicy Bypass -File tools\set-secret.ps1 AIRTABLE_TOKEN
param([Parameter(Mandatory = $true)][string]$Name)

$envFile = Join-Path (Split-Path $PSScriptRoot -Parent) '.env'
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path (Split-Path $PSScriptRoot -Parent) '.env.example') $envFile
}

$secure = Read-Host "Paste the value for $Name (input is hidden), then press Enter" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $value = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr).Trim()
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}
if ($value -eq '') {
    Write-Host "Nothing pasted; .env not changed."
    exit 1
}

$found = $false
$lines = foreach ($line in (Get-Content $envFile)) {
    if ($line.StartsWith("$Name=")) { $found = $true; "$Name=$value" } else { $line }
}
if (-not $found) { $lines = @($lines) + "$Name=$value" }

# UTF-8 without BOM and LF endings, like the rest of the repository.
[IO.File]::WriteAllText($envFile, (($lines -join "`n") + "`n"), (New-Object Text.UTF8Encoding($false)))
Write-Host "$Name set in .env ($($value.Length) characters). The value was not printed."
