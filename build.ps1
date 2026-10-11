$ErrorActionPreference = 'Stop'
$studioSource = $PSScriptRoot
$studioPython = Join-Path $studioSource '.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $studioPython)) { python -m venv (Join-Path $studioSource '.venv') }
if ($LASTEXITCODE -ne 0) { throw 'Create virtual environment failed' }
& $studioPython -m pip install -r (Join-Path $studioSource 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Install dependencies failed' }
& $studioPython -m unittest discover -s $studioSource -p 'test_*.py'
if ($LASTEXITCODE -ne 0) { throw 'Offline tests failed' }
# Only code-generated samples and web UI. Private firmware/resources are external.
& $studioPython -m PyInstaller --noconfirm --clean --onefile --windowed --name '368K Studio Public' --icon (Join-Path $studioSource 'assets/app.ico') --add-data "${studioSource}/assets:assets" --add-data "${studioSource}/web:web" --distpath (Join-Path $studioSource 'dist') --workpath (Join-Path $studioSource 'build') --specpath (Join-Path $studioSource 'build') (Join-Path $studioSource 'server.py')
if ($LASTEXITCODE -ne 0) { throw 'EXE build failed' }
Write-Host 'Created dist/368K Studio Public.exe (no vehicle firmware bundled)'
