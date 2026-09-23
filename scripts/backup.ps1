param(
    [string]$Database = $(if ($env:ODOO_DB) { $env:ODOO_DB } else { 'thirdcode_accounting' }),
    [string]$OutputRoot = (Join-Path $PSScriptRoot '..\backups'),
    [string]$ComposeProjectName = $(if ($env:COMPOSE_PROJECT_NAME) { $env:COMPOSE_PROJECT_NAME } else { 'thirdcode-accounting' })
)

$ErrorActionPreference = 'Stop'

if ($Database -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') {
    throw "Database name contains unsupported characters: $Database"
}

$outputRootPath = [IO.Path]::GetFullPath($OutputRoot)
New-Item -ItemType Directory -Path $outputRootPath -Force | Out-Null
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$backupPath = Join-Path $outputRootPath "$Database-$stamp"
New-Item -ItemType Directory -Path $backupPath -Force | Out-Null

$dumpName = "database-$Database.dump"
$filestoreName = 'filestore.tar.gz'
$dumpPath = Join-Path $backupPath $dumpName
$filestorePath = Join-Path $backupPath $filestoreName
$containerDump = "/tmp/thirdcode-$stamp.dump"
$containerFilestore = "/tmp/thirdcode-$stamp-filestore.tar.gz"

try {
    docker compose -p $ComposeProjectName exec -T db sh -lc "pg_dump -U odoo -Fc -d $Database > $containerDump"
    if ($LASTEXITCODE -ne 0) { throw "pg_dump failed with exit code $LASTEXITCODE" }
    docker compose -p $ComposeProjectName cp "db:$containerDump" $dumpPath
    if ($LASTEXITCODE -ne 0) { throw "Copying the database dump failed with exit code $LASTEXITCODE" }

    docker compose -p $ComposeProjectName exec -T odoo sh -lc "tar -czf $containerFilestore -C /var/lib/odoo ."
    if ($LASTEXITCODE -ne 0) { throw "Filestore archive failed with exit code $LASTEXITCODE" }
    docker compose -p $ComposeProjectName cp "odoo:$containerFilestore" $filestorePath
    if ($LASTEXITCODE -ne 0) { throw "Copying the filestore archive failed with exit code $LASTEXITCODE" }

    $configPath = Join-Path $PSScriptRoot '..\config\odoo.conf'
    Copy-Item -LiteralPath $configPath -Destination (Join-Path $backupPath 'odoo.conf')

    $files = Get-ChildItem -LiteralPath $backupPath -File | ForEach-Object {
        $hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
        [ordered]@{
            name = $_.Name
            bytes = $_.Length
            sha256 = $hash.Hash.ToLowerInvariant()
        }
    }
    $imageInfo = (docker compose -p $ComposeProjectName images 2>$null | Out-String).Trim()
    $manifest = [ordered]@{
        format = 'thirdcode-accounting-backup-v1'
        created_at_utc = $stamp
        database = $Database
        files = @($files)
        docker_images = $imageInfo
        restore_notes = 'Restore into a disposable target first and verify before any cutover.'
    }
    $manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $backupPath 'manifest.json') -Encoding UTF8
    Write-Output "Backup created: $backupPath"
}
finally {
    docker compose -p $ComposeProjectName exec -T db sh -lc "rm -f $containerDump" 2>$null | Out-Null
    docker compose -p $ComposeProjectName exec -T odoo sh -lc "rm -f $containerFilestore" 2>$null | Out-Null
}
