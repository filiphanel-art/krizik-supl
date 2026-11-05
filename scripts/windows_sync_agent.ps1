<#
.SYNOPSIS
    Automatické odesílání suplprehtrid.html ze složky na Windows na server Suplování Viewer.
.DESCRIPTION
    Tento skript sleduje zadanou složku (např. na ploše zástupkyně) a jakmile Bakaláři
    uloží soubor suplprehtrid.html, odešle ho přes HTTP POST na skrytý URL endpoint.
    Pokud je počítač vypnutý, server si drží data v SQLite databázi.
    Při startu Windows (Task Scheduler) skript zkontroluje soubor a odešle ho znovu.
#>

param(
    [string]$WatchFolder = "$env:USERPROFILE\Desktop\SuplovaniExport",
    [string]$ServerUrl = "http://10.20.0.81:8080/api/upload/skola-tajny-klic-123",
    [string]$TargetFileName = "suplprehtrid.html"
)

Write-Host "=== Sledování exportu Bakalářů pro Suplování Viewer ===" -ForegroundColor Cyan
Write-Host "Sledovaná složka: $WatchFolder"
Write-Host "Cílový server:    $ServerUrl"
Write-Host "Hledaný soubor:   $TargetFileName"

if (-not (Test-Path $WatchFolder)) {
    New-Item -ItemType Directory -Path $WatchFolder -Force | Out-Null
    Write-Host "Vytvořena složka: $WatchFolder" -ForegroundColor Yellow
}

function Send-SuplovaniFile {
    param([string]$FilePath)

    if (-not (Test-Path $FilePath)) { return }

    $fileName = [System.IO.Path]::GetFileName($FilePath)
    if ($fileName.ToLower() -ne $TargetFileName.ToLower()) {
        Write-Host "Ignoruji soubor $fileName (očekáván je pouze $TargetFileName)" -ForegroundColor Gray
        return
    }

    # Počkej na dokončení zápisu programem Bakaláři (soubor nesmí být uzamčen)
    $maxRetries = 10
    $retry = 0
    $fileReady = $false
    while ($retry -lt $maxRetries -and -not $fileReady) {
        try {
            $stream = [System.IO.File]::Open($FilePath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::None)
            $stream.Close()
            $stream.Dispose()
            $fileReady = $true
        } catch {
            Start-Sleep -Seconds 1
            $retry++
        }
    }

    if (-not $fileReady) {
        Write-Host "Soubor $fileName je stále uzamčen jinou aplikací." -ForegroundColor Red
        return
    }

    try {
        Write-Host "Odesílám $fileName na server..." -ForegroundColor Cyan
        $response = Invoke-RestMethod -Uri $ServerUrl -Method Post -InFile $FilePath `
            -ContentType "text/html" -Headers @{ "X-Filename" = $TargetFileName }
        Write-Host "Úspěšně odesláno: $(ConvertTo-Json $response -Compress)" -ForegroundColor Green
    } catch {
        Write-Host "Chyba při odesílání: $($_.Exception.Message)" -ForegroundColor Red
    }
}

# 1. Kontrola při spuštění (pokud soubor již existuje)
$initialFile = Join-Path $WatchFolder $TargetFileName
if (Test-Path $initialFile) {
    Write-Host "Při startu nalezen soubor, odesílám..." -ForegroundColor Yellow
    Send-SuplovaniFile -FilePath $initialFile
}

# 2. Sledování změn v reálném čase přes FileSystemWatcher
$watcher = New-Object System.IO.FileSystemWatcher
$watcher.Path = $WatchFolder
$watcher.Filter = "*.*"
$watcher.IncludeSubdirectories = $false
$watcher.EnableRaisingEvents = $true

$action = {
    $path = $Event.SourceEventArgs.FullPath
    $changeType = $Event.SourceEventArgs.ChangeType
    Write-Host "Zaznamenána událost $changeType na $path" -ForegroundColor DarkCyan
    Start-Sleep -Seconds 2 # Počkej na dopsání
    Send-SuplovaniFile -FilePath $path
}

Register-ObjectEvent $watcher "Created" -Action $action | Out-Null
Register-ObjectEvent $watcher "Changed" -Action $action | Out-Null

Write-Host "Sledování je aktivní. Pro ukončení stiskněte Ctrl+C." -ForegroundColor Green

try {
    while ($true) {
        Start-Sleep -Seconds 10
    }
} finally {
    Unregister-Event -SourceIdentifier * -ErrorAction SilentlyContinue
    $watcher.Dispose()
}
