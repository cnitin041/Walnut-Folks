param(
    [Parameter(Position = 0)]
    [ValidateSet("init", "start", "stop", "status", "create", "reset")]
    [string]$Action = "status"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$PgBin = if ($env:PG_BIN) { $env:PG_BIN } else { "C:\Program Files\PostgreSQL\18\bin" }
$PgData = Join-Path $RepoRoot ".pgdata"
$LogFile = Join-Path $PgData "server.log"
$Port = if ($env:PG_PORT) { [int]$env:PG_PORT } else { 55432 }
$PgCtl = Join-Path $PgBin "pg_ctl.exe"
$InitDb = Join-Path $PgBin "initdb.exe"
$CreateDb = Join-Path $PgBin "createdb.exe"
$Psql = Join-Path $PgBin "psql.exe"

function Assert-Tooling {
    foreach ($tool in @($PgCtl, $InitDb, $CreateDb, $Psql)) {
        if (-not (Test-Path -LiteralPath $tool)) {
            throw "PostgreSQL tool not found: $tool. Set PG_BIN to the PostgreSQL bin directory."
        }
    }
}

function Test-Running {
    if (-not (Test-Path -LiteralPath $PgData)) { return $false }
    & $PgCtl -D $PgData status *> $null
    return $LASTEXITCODE -eq 0
}

function Initialize-Cluster {
    if (Test-Path -LiteralPath (Join-Path $PgData "PG_VERSION")) {
        Write-Host "Cluster already initialized at $PgData"
        return
    }
    if (Test-Path -LiteralPath $PgData) {
        $items = Get-ChildItem -LiteralPath $PgData -Force
        if ($items.Count -gt 0) {
            throw "$PgData exists but is not a PostgreSQL cluster. Remove it or choose another location."
        }
    } else {
        New-Item -ItemType Directory -Path $PgData -Force | Out-Null
    }
    Write-Host "Initializing PostgreSQL cluster at $PgData..."
    & $InitDb -D $PgData -U postgres -A trust -E UTF8 --locale=C
    if ($LASTEXITCODE -ne 0) { throw "initdb failed with exit code $LASTEXITCODE" }
    Write-Host "Cluster initialized."
}

function Start-Cluster {
    if (Test-Running) {
        Write-Host "PostgreSQL is already running on port $Port."
        return
    }
    if (-not (Test-Path -LiteralPath (Join-Path $PgData "PG_VERSION"))) {
        throw "Cluster not initialized. Run: .\scripts\db.ps1 init"
    }
    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($listener) {
        throw "Port $Port is already in use."
    }
    Write-Host "Starting PostgreSQL on port $Port..."
    & $PgCtl -D $PgData -l $LogFile -o "-p $Port" -w start
    if ($LASTEXITCODE -ne 0) { throw "pg_ctl start failed with exit code $LASTEXITCODE" }
    Write-Host "PostgreSQL started."
}

function Stop-Cluster {
    if (-not (Test-Running)) {
        Write-Host "PostgreSQL is not running."
        return
    }
    Write-Host "Stopping PostgreSQL..."
    & $PgCtl -D $PgData -m fast -w stop
    if ($LASTEXITCODE -ne 0) { throw "pg_ctl stop failed with exit code $LASTEXITCODE" }
    Write-Host "PostgreSQL stopped."
}

function Show-Status {
    if (Test-Running) {
        & $PgCtl -D $PgData status
    } else {
        Write-Host "PostgreSQL is not running. Data directory: $PgData"
    }
}

function New-Database([string]$Name) {
    $exists = (& $Psql -h 127.0.0.1 -p $Port -U postgres -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$Name'" | Out-String).Trim()
    if ($exists -eq "1") {
        Write-Host "Database '$Name' already exists."
        return
    }
    Write-Host "Creating database '$Name'..."
    & $CreateDb -h 127.0.0.1 -p $Port -U postgres $Name
    if ($LASTEXITCODE -ne 0) { throw "createdb failed for '$Name'" }
}

function Create-Databases {
    if (-not (Test-Running)) { throw "PostgreSQL is not running. Run: .\scripts\db.ps1 start" }
    New-Database "ledger"
    New-Database "ledger_test"
}

function Reset-Cluster {
    Stop-Cluster
    if (Test-Path -LiteralPath $PgData) {
        Remove-Item -LiteralPath $PgData -Recurse -Force
    }
    Initialize-Cluster
    Start-Cluster
    Create-Databases
}

Assert-Tooling

switch ($Action) {
    "init" { Initialize-Cluster; Start-Cluster; Create-Databases }
    "start" { Start-Cluster }
    "stop" { Stop-Cluster }
    "status" { Show-Status }
    "create" { Create-Databases }
    "reset" { Reset-Cluster }
}
