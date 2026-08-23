Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  ParcelPilot AI Support Agent - Setup" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# Check for .env
if (-not (Test-Path ".env")) {
    Write-Host "`nCreating .env from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "Please edit .env and add your OPENAI_API_KEY" -ForegroundColor Yellow
}

# Check for Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Python is required but not found." -ForegroundColor Red
    exit 1
}

# Check for Node
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Node.js is required but not found." -ForegroundColor Red
    exit 1
}

# Setup backend
Write-Host "`n[1/4] Installing Python dependencies..." -ForegroundColor Green
Set-Location backend
pip install -r requirements.txt

# Ingest Excel data
Write-Host "`n[2/4] Ingesting Excel data..." -ForegroundColor Green
python -m app.setup_db

# Setup frontend
Write-Host "`n[3/4] Installing frontend dependencies..." -ForegroundColor Green
Set-Location ../frontend
npm install

# Done
Write-Host "`n[4/4] Setup complete!" -ForegroundColor Green
Write-Host "`nTo run the application:" -ForegroundColor Cyan
Write-Host "  Backend:  cd backend && uvicorn app.main:app --reload --port 8000"
Write-Host "  Frontend: cd frontend && npm run dev"
Write-Host "`nOr with Docker: docker-compose up"

Set-Location ..
