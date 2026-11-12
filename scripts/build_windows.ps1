<#
  MARX SECRET – build completo para Windows 10/11 (64 bits)

  Gera em .\release:
    MARX_SECRET_Setup.exe       (instalador Inno Setup)
    MARX_SECRET_Portable.zip    (versão portátil)
    MARX_SECRET_Source.zip      (projeto completo e código-fonte)
    Manual_MARX_SECRET.pdf      (manual)
    MARX_SECRET_Entrega\        (as quatro pastas de entrega)

  Uso (PowerShell, na raiz do projeto):
    powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1 [-SkipTests] [-Python py]
  Requisitos: Python 3.12 x64 e Inno Setup 6 (instalado automaticamente via winget/choco se ausente).
#>
param(
  [switch]$SkipTests,
  [string]$Python = "python"
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Release = Join-Path $Root "release"
$Dist = Join-Path $Root "dist"

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Green }

Step "Ambiente virtual de build"
if (-not (Test-Path ".venv-build")) { & $Python -m venv .venv-build }
$Py = Join-Path $Root ".venv-build\Scripts\python.exe"
& $Py -m pip install --upgrade pip | Out-Null
& $Py -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar dependências" }

if (-not $SkipTests) {
  Step "Testes automatizados"
  $env:QT_QPA_PLATFORM = "offscreen"
  & $Py -m pytest -q
  if ($LASTEXITCODE -ne 0) { throw "Testes falharam" }
  Remove-Item Env:\QT_QPA_PLATFORM
}

Step "Limpeza"
foreach ($d in @("build", "dist", "release")) { if (Test-Path $d) { Remove-Item -Recurse -Force $d } }
New-Item -ItemType Directory -Force $Release | Out-Null

Step "Manual em PDF"
& $Py tools\make_manual.py "$Release\Manual_MARX_SECRET.pdf"
if ($LASTEXITCODE -ne 0) { throw "Falha ao gerar o manual" }

Step "Executável (PyInstaller)"
& $Py -m PyInstaller installer\marx_secret.spec --noconfirm --clean --distpath $Dist --workpath build
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou" }
$AppDir = Join-Path $Dist "MARX_SECRET"
Copy-Item "$Release\Manual_MARX_SECRET.pdf" $AppDir

Step "Autodiagnóstico do executável"
$report = Join-Path $Dist "selftest.txt"
$p = Start-Process -FilePath "$AppDir\MARX_SECRET.exe" -ArgumentList "--self-test", "--report", "`"$report`"" -Wait -PassThru
Get-Content $report
if ($p.ExitCode -ne 0) { throw "Autodiagnóstico do executável falhou" }

Step "Versão portátil"
$Portable = Join-Path $Dist "MARX SECRET Portable"
Copy-Item -Recurse $AppDir $Portable
Set-Content -Path "$Portable\portable.flag" -Value "MARX SECRET - modo portatil" -Encoding ASCII
@"
MARX SECRET Professional - Versao portatil
==========================================
1. Extraia esta pasta para qualquer local (inclusive pendrive).
2. Execute MARX_SECRET.exe.
Dados e historico ficam em .\dados e as saidas sugeridas em .\saida.
Para remover, basta apagar a pasta. Manual: Manual_MARX_SECRET.pdf
"@ | Set-Content -Path "$Portable\LEIA-ME.txt" -Encoding UTF8
Compress-Archive -Path $Portable -DestinationPath "$Release\MARX_SECRET_Portable.zip" -CompressionLevel Optimal

Step "Código-fonte"
& $Py tools\make_source_zip.py "$Release\MARX_SECRET_Source.zip"

Step "Instalador (Inno Setup)"
$iscc = @(
  "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
  "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
  "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
  Write-Host "Inno Setup não encontrado; instalando..."
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    winget install --id JRSoftware.InnoSetup -e --silent --accept-package-agreements --accept-source-agreements
  } elseif (Get-Command choco -ErrorAction SilentlyContinue) {
    choco install innosetup -y --no-progress
  } else { throw "Instale o Inno Setup 6: https://jrsoftware.org/isdl.php" }
  $iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
            "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
}
& $iscc installer\marx_secret.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup falhou" }

Step "Pastas de entrega"
& $Py tools\package_delivery.py
if ($LASTEXITCODE -ne 0) { throw "Entrega incompleta" }

Step "Concluído"
Get-ChildItem $Release | Format-Table Name, Length
