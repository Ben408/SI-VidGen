# Developer Guide

## Setup (Windows PowerShell)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
Copy-Item .env.example .env

cd web
npm install
cd ..
```

### Corporate TLS / npm leaf-signature failures

If `npm install` fails with `UNABLE_TO_VERIFY_LEAF_SIGNATURE`, export Windows roots and point Node at the bundle:

```powershell
$pem = Join-Path $env:TEMP 'windows-ca-bundle.pem'
Get-ChildItem Cert:\LocalMachine\Root, Cert:\CurrentUser\Root | ForEach-Object {
  $bytes = $_.Export('Cert')
  $b64 = [Convert]::ToBase64String($bytes, 'InsertLineBreaks')
  Add-Content -Path $pem -Value "-----BEGIN CERTIFICATE-----`n$b64`n-----END CERTIFICATE-----`n"
}
$env:NODE_EXTRA_CA_CERTS = $pem
$env:PIP_CERT = $pem
cd web
npm install
```

Keep these variables in the terminal when running `pip install`. Do not disable TLS verification in npm or pip.

## Build the local help index

```powershell
# Default: safe 10-page cap
python -m src.rag.index_help

# Explicit full crawl and stale-source cleanup
python -m src.rag.index_help --full
```

## Run

Terminal 1:

```powershell
.\.venv\Scripts\Activate.ps1
python main.py
```

Terminal 2:

```powershell
cd web
npm run dev
```

Open `http://localhost:5173`.

## Verify

```powershell
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m pytest --cov=src
cd web
npm run lint
npm run build
```
