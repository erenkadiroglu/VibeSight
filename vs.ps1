<#
.SYNOPSIS
  VibeSight görev betiği (Windows). Makefile ile aynı komutları sunar.

.EXAMPLE
  .\vs.ps1 setup        # ilk kurulum
  .\vs.ps1 demo         # kamerasız demo
  .\vs.ps1 dev          # kamera / webcam ile çalıştır
  .\vs.ps1 check        # push öncesi tüm kontroller
#>
param(
  [Parameter(Position = 0)]
  [ValidateSet('help', 'doctor', 'setup', 'models', 'demo', 'dev', 'serve', 'stop', 'camera-test', 'lint', 'test', 'check', 'format')]
  [string]$Task = 'help'
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$Backend = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'

function Step($text) { Write-Host "`n> $text" -ForegroundColor Cyan }
function Ok($text) { Write-Host "  [OK] $text" -ForegroundColor Green }
function Fail($text) { Write-Host "  [X]  $text" -ForegroundColor Red }

function Invoke-In($dir, [scriptblock]$block) {
  Push-Location $dir
  try {
    & $block
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "Komut başarısız oldu (çıkış kodu $LASTEXITCODE)." }
  } finally { Pop-Location }
}

function Test-Tool($name, $hint) {
  if (Get-Command $name -ErrorAction SilentlyContinue) { Ok "$name bulundu"; return $true }
  Fail "$name bulunamadı. Kurulum: $hint"
  return $false
}

function Stop-VibeSight {
  # Önceki çalıştırmalardan kalan arka uç pencerelerini ve Vite sunucularını kapatır.
  $procs = @(Get-CimInstance Win32_Process | Where-Object {
      $_.ProcessId -ne $PID -and $_.CommandLine -and (
        $_.CommandLine -like '*uv run vibesight*' -or
        $_.CommandLine -like '*\Scripts\vibesight*' -or
        ($_.CommandLine -like '*vite*' -and $_.CommandLine -like "*$Frontend*"))
    })
  foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
  if ($procs.Count) {
    Ok "Önceki VibeSight süreçleri kapatıldı ($($procs.Count))."
    Start-Sleep -Seconds 1
  }
  foreach ($port in 8000, 5173) {
    $busy = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($busy) {
      $owner = (Get-Process -Id $busy[0].OwningProcess -ErrorAction SilentlyContinue).ProcessName
      Fail "$port portu başka bir uygulama tarafından kullanılıyor ($owner). O uygulamayı kapatıp tekrar deneyin."
      exit 1
    }
  }
}

function Start-Backend([string]$source) {
  $cmd = "Set-Location '$Backend'; "
  if ($source) { $cmd += "`$env:VIBESIGHT_SOURCE='$source'; " }
  $cmd += "uv run vibesight"
  Start-Process powershell -ArgumentList '-NoExit', '-Command', $cmd | Out-Null
  Ok 'Arka uç yeni bir pencerede başlatıldı (kapatmak için o pencereyi kapatın).'
}

switch ($Task) {
  'help' {
    Write-Host @'
VibeSight komutları:
  .\vs.ps1 doctor       Gerekli araçlar kurulu mu kontrol eder
  .\vs.ps1 setup        Bağımlılıkları kurar, modelleri indirir, .env oluşturur
  .\vs.ps1 models       Modelleri indirir / doğrular
  .\vs.ps1 demo         Kamerasız demo (http://localhost:5173)
  .\vs.ps1 dev          Kamera veya webcam ile geliştirme modu
  .\vs.ps1 serve        Derlenmiş arayüzle tek port (http://127.0.0.1:8000)
  .\vs.ps1 stop         Çalışan VibeSight süreçlerini kapatır
  .\vs.ps1 camera-test  Tapo kamera bağlantısını test eder
  .\vs.ps1 check        Lint + tip kontrolü + test + derleme
'@
  }
  'doctor' {
    Step 'Araçlar kontrol ediliyor'
    $results = @(
      (Test-Tool 'git' 'winget install Git.Git'),
      (Test-Tool 'uv' 'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'),
      (Test-Tool 'node' 'winget install OpenJS.NodeJS.LTS')
    )
    $ok = -not ($results -contains $false)
    if ($ok) { Ok 'Her şey hazır.' } else { Write-Host "`nKurduktan sonra PowerShell'i kapatıp yeniden açın." }
  }
  'setup' {
    Step 'Python bağımlılıkları (uv sync)'
    Invoke-In $Backend { uv sync }
    Step 'Arayüz bağımlılıkları (npm ci)'
    Invoke-In $Frontend { npm ci }
    & $PSCommandPath models
    $envFile = Join-Path $Backend '.env'
    if (-not (Test-Path $envFile)) {
      Copy-Item (Join-Path $Backend '.env.example') $envFile
      Ok 'backend\.env oluşturuldu'
    }
    Ok 'Kurulum tamamlandı. Şimdi: .\vs.ps1 demo'
  }
  'models' {
    Step 'Modeller indiriliyor'
    Invoke-In $Backend { uv run python ..\scripts\download_models.py }
  }
  'demo' {
    Step 'Demo modu'
    Stop-VibeSight
    Start-Backend 'mock'
    Start-Sleep -Seconds 3
    Start-Process 'http://localhost:5173'
    Invoke-In $Frontend { npm run dev }
  }
  'dev' {
    Step 'Geliştirme modu (.env içindeki kaynak)'
    Stop-VibeSight
    Start-Backend ''
    Start-Sleep -Seconds 3
    Start-Process 'http://localhost:5173'
    Invoke-In $Frontend { npm run dev }
  }
  'serve' {
    Stop-VibeSight
    Step 'Arayüz derleniyor'
    Invoke-In $Frontend { npm run build }
    Start-Process 'http://127.0.0.1:8000'
    Invoke-In $Backend { uv run vibesight }
  }
  'stop' {
    Stop-VibeSight
    Ok 'VibeSight kapalı.'
  }
  'camera-test' {
    Invoke-In $Backend { uv run python ..\scripts\camera_test.py }
  }
  'format' {
    Invoke-In $Backend { uv run ruff check --fix . ..\scripts; uv run ruff format . ..\scripts }
  }
  'lint' {
    Invoke-In $Backend { uv run ruff check . ..\scripts }
    Invoke-In $Backend { uv run ruff format --check . ..\scripts }
    Invoke-In $Backend { uv run mypy vibesight }
    Invoke-In $Frontend { npm run lint }
    Invoke-In $Frontend { npm run typecheck }
  }
  'test' {
    Invoke-In $Backend { uv run pytest -q }
  }
  'check' {
    & $PSCommandPath lint
    & $PSCommandPath test
    Invoke-In $Frontend { npm run build }
    Ok 'Tüm kontroller geçti.'
  }
}
