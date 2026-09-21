param(
    [string]$Database = $(if ($env:ODOO_DB) { $env:ODOO_DB } else { 'thirdcode_accounting' })
)

$ErrorActionPreference = 'Stop'

docker compose up -d db
$deadline = (Get-Date).AddSeconds(60)
$dbContainer = $null
do {
    Start-Sleep -Seconds 2
    $dbContainer = docker compose ps -q db
    if ($dbContainer) {
        $health = docker inspect --format '{{.State.Health.Status}}' $dbContainer 2>$null
        if ($health -eq 'healthy') { break }
    }
} while ((Get-Date) -lt $deadline)

if (-not $dbContainer -or $health -ne 'healthy') {
    throw 'PostgreSQL did not become healthy within 60 seconds.'
}

docker compose build odoo
docker compose run --rm odoo odoo -c /etc/odoo/odoo.conf -d $Database -i base,account,account_payment,contacts,hr_expense,auditlog,date_range,report_xlsx,report_xlsx_helper,account_financial_report,partner_statement,account_statement_base,account_reconcile_model_oca,account_reconcile_oca,account_statement_reconcile_status,thirdcode_accounting --without-demo=all --stop-after-init
if ($LASTEXITCODE -ne 0) {
    throw "Odoo database initialization failed with exit code $LASTEXITCODE."
}
docker compose up -d odoo

$deadline = (Get-Date).AddSeconds(60)
do {
    Start-Sleep -Seconds 2
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri 'http://localhost:8069/web/login' -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            Write-Output "Odoo is available at http://localhost:8069/web/login using database '$Database'."
            exit 0
        }
    } catch {
        # The service is still starting.
    }
} while ((Get-Date) -lt $deadline)

throw 'Odoo did not become available within 60 seconds.'
