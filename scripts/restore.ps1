param(
    [Parameter(Mandatory = $true)]
    [string]$BackupDirectory,
    [string]$TargetDatabase = 'thirdcode_accounting_restore',
    [switch]$AllowReplaceExisting,
    [string]$FilestoreTarget = (Join-Path $PSScriptRoot '..\restores'),
    [string]$ComposeProjectName = $(if ($env:COMPOSE_PROJECT_NAME) { $env:COMPOSE_PROJECT_NAME } else { 'thirdcode-accounting' })
)

$ErrorActionPreference = 'Stop'
if ($TargetDatabase -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') {
    throw "Target database name contains unsupported characters: $TargetDatabase"
}

$backupPath = [IO.Path]::GetFullPath($BackupDirectory)
& (Join-Path $PSScriptRoot 'verify_backup.ps1') -BackupDirectory $backupPath -ComposeProjectName $ComposeProjectName
$manifest = Get-Content -LiteralPath (Join-Path $backupPath 'manifest.json') -Raw | ConvertFrom-Json
$dump = Join-Path $backupPath "database-$($manifest.database).dump"
$filestore = Join-Path $backupPath 'filestore.tar.gz'

$existsOutput = docker compose -p $ComposeProjectName exec -T db psql -U odoo -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$TargetDatabase'"
$exists = (($existsOutput | Out-String).Trim())
if ($exists -eq '1') {
    if (-not $AllowReplaceExisting) {
        throw "Target database already exists. Choose a new target or pass -AllowReplaceExisting explicitly."
    }
    docker compose -p $ComposeProjectName exec -T db psql -U odoo -d postgres -c "DROP DATABASE $TargetDatabase" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Dropping the explicitly selected target database failed" }
}

docker compose -p $ComposeProjectName exec -T db createdb -U odoo $TargetDatabase | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Creating target database failed" }

$containerDump = "/tmp/restore-$([Guid]::NewGuid().ToString('N')).dump"
try {
    docker compose -p $ComposeProjectName cp $dump "db:$containerDump"
    docker compose -p $ComposeProjectName exec -T db pg_restore -U odoo -d $TargetDatabase $containerDump | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "pg_restore failed with exit code $LASTEXITCODE" }
}
finally {
    docker compose -p $ComposeProjectName exec -T db sh -lc "rm -f $containerDump" 2>$null | Out-Null
}

$restoreRoot = [IO.Path]::GetFullPath($FilestoreTarget)
New-Item -ItemType Directory -Path $restoreRoot -Force | Out-Null
$filestorePath = Join-Path $restoreRoot "$TargetDatabase-$([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))"
New-Item -ItemType Directory -Path $filestorePath -Force | Out-Null
tar -xzf $filestore -C $filestorePath
if ($LASTEXITCODE -ne 0) { throw "Filestore extraction failed with exit code $LASTEXITCODE" }

Write-Output "Database restored to disposable target: $TargetDatabase"
Write-Output "Filestore restored to explicit directory: $filestorePath"
Write-Output 'The restored target is not production-verified; run the application checks before cutover.'
