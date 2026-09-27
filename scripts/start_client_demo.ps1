param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8077
)

$ErrorActionPreference = 'Stop'
$repository = Split-Path -Parent $PSScriptRoot
$credentials = Join-Path (Split-Path -Parent $repository) 'private-demo-access\credentials.json'
$databaseContainer = 'tcsi-client-demo-db-1'
$odooContainer = 'tcsi-client-demo-odoo'

foreach ($container in @($databaseContainer, $odooContainer)) {
    $exists = docker container inspect --format '{{.Id}}' $container 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $exists) {
        throw "Isolated demo container '$container' is missing. Provision the demo before starting it."
    }
    $running = docker container inspect --format '{{.State.Running}}' $container
    if ($running -ne 'true') {
        docker start $container | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Could not start '$container'." }
    }
    if ($container -eq $databaseContainer) {
        $databaseDeadline = (Get-Date).AddSeconds(60)
        do {
            $databaseHealth = docker container inspect --format '{{.State.Health.Status}}' $databaseContainer
            if ($databaseHealth -eq 'healthy') { break }
            Start-Sleep -Seconds 2
        } while ((Get-Date) -lt $databaseDeadline)
        if ($databaseHealth -ne 'healthy') { throw 'The isolated demo database is not healthy.' }
    }
}

$deadline = (Get-Date).AddSeconds(90)
do {
    Start-Sleep -Seconds 2
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:$Port/web/login" -TimeoutSec 5
        if ($response.StatusCode -eq 200) { break }
    } catch {
        # Odoo is still starting.
    }
} while ((Get-Date) -lt $deadline)

if (-not $response -or $response.StatusCode -ne 200) {
    throw "The isolated demo did not answer at http://localhost:$Port/web/login."
}
if (-not (Test-Path -LiteralPath $credentials)) {
    throw "The private demo credentials are missing at '$credentials'."
}
python (Join-Path $PSScriptRoot 'check_client_demo.py') --credentials-file $credentials
if ($LASTEXITCODE -ne 0) { throw 'The isolated demo acceptance check failed.' }
Write-Output "Isolated client demo is available at http://localhost:$Port/web/login."
