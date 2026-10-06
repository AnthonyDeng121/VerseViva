param(
    [int]$Port = 8001,
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$webRoot = Join-Path $projectRoot "web"
$logRoot = Join-Path $projectRoot "data\preview"
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null

function Find-WinGetExecutable([string]$fileName) {
    $command = Get-Command $fileName -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    $match = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" `
        -Filter $fileName -Recurse -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
    if (-not $match) {
        throw "Cannot find $fileName. Install it with winget and reopen PowerShell."
    }
    return $match
}

$npm = Find-WinGetExecutable "npm.cmd"
$cloudflared = Find-WinGetExecutable "cloudflared.exe"
$wsl = (Get-Command wsl.exe -ErrorAction Stop).Source

if (-not $SkipBuild) {
    Write-Host "[1/3] Building the mobile H5..." -ForegroundColor Cyan
    Push-Location $webRoot
    try {
        & $npm run build
        if ($LASTEXITCODE -ne 0) {
            throw "Frontend build failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}

$existing = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    throw "Port $Port is already in use. Stop the old preview or choose another -Port."
}

Write-Host "[2/3] Starting the same-origin VerseViva service..." -ForegroundColor Cyan
$stdout = Join-Path $logRoot "uvicorn.stdout.log"
$stderr = Join-Path $logRoot "uvicorn.stderr.log"
$server = Start-Process -FilePath $wsl `
    -ArgumentList @("--cd", $projectRoot, ".venv/bin/python", "-m", "uvicorn", "server.main:app", "--host", "127.0.0.1", "--port", "$Port") `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -PassThru

try {
    $healthy = $false
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        Start-Sleep -Milliseconds 500
        try {
            $health = Invoke-RestMethod "http://127.0.0.1:$Port/api/v1/health" -TimeoutSec 2
            if ($health.status -eq "ok") {
                $healthy = $true
                break
            }
        }
        catch {
            if ($server.HasExited) {
                throw "VerseViva failed to start. See $stderr"
            }
        }
    }
    if (-not $healthy) {
        throw "VerseViva health check timed out. See $stderr"
    }

    Write-Host "[3/3] Creating a temporary public HTTPS address..." -ForegroundColor Cyan
    Write-Host "Keep this window open. Press Ctrl+C to stop the preview." -ForegroundColor Yellow
    Write-Host "The trycloudflare.com address below changes after every restart." -ForegroundColor Yellow
    # Campus networks often block QUIC/UDP 7844; HTTP/2 uses outbound TCP 443.
    & $cloudflared tunnel --no-autoupdate --protocol http2 --url "http://127.0.0.1:$Port"
}
finally {
    if ($server -and -not $server.HasExited) {
        Stop-Process -Id $server.Id -Force
    }
}
