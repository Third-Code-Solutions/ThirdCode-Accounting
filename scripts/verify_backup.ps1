param(
    [Parameter(Mandatory = $true)]
    [string]$BackupDirectory
)

$ErrorActionPreference = 'Stop'
$backupPath = [IO.Path]::GetFullPath($BackupDirectory)
$manifestPath = Join-Path $backupPath 'manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "Backup manifest not found: $manifestPath"
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
foreach ($file in $manifest.files) {
    $path = Join-Path $backupPath $file.name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Backup file is missing: $path"
    }
    $actual = Get-FileHash -LiteralPath $path -Algorithm SHA256
    if ($actual.Hash.ToLowerInvariant() -ne $file.sha256.ToLowerInvariant()) {
        throw "SHA-256 mismatch for $($file.name)"
    }
}

$dump = Join-Path $backupPath "database-$($manifest.database).dump"
$filestore = Join-Path $backupPath 'filestore.tar.gz'
if (-not (Test-Path -LiteralPath $dump -PathType Leaf)) { throw "Database dump is missing: $dump" }
if (-not (Test-Path -LiteralPath $filestore -PathType Leaf)) { throw "Filestore archive is missing: $filestore" }

$containerDump = "/tmp/verify-$([Guid]::NewGuid().ToString('N')).dump"
try {
    docker compose cp $dump "db:$containerDump"
    docker compose exec -T db pg_restore -l $containerDump | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "pg_restore archive listing failed with exit code $LASTEXITCODE" }
}
finally {
    docker compose exec -T db sh -lc "rm -f $containerDump" 2>$null | Out-Null
}

tar -tzf $filestore | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Filestore tar listing failed with exit code $LASTEXITCODE" }
Write-Output "Backup verified: $backupPath"
