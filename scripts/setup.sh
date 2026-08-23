#!/bin/bash
set -e

echo "========================================="
echo "  ParcelPilot AI Support Agent - Setup"
echo "========================================="

# Check for .env
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "Please edit .env and add your OPENAI_API_KEY"
fi

# Check for Python
if ! command -v python &> /dev/null; then
    echo "ERROR: Python is required but not found."
    exit 1
fi

# Check for Node
if ! command -v node &> /dev/null; then
    echo "ERROR: Node.js is required but not found."
    exit 1
fi

# Setup backend
echo ""
echo "[1/4] Installing Python dependencies..."
cd backend
pip install -r requirements.txt

# Ingest Excel data
echo ""
echo "[2/4] Ingesting Excel data..."
python -m app.setup_db

# Setup frontend
echo ""
echo "[3/4] Installing frontend dependencies..."
cd ../frontend
npm install

# Done
echo ""
echo "[4/4] Setup complete!"
echo ""
echo "To run the application:"
echo "  Backend:  cd backend && uvicorn app.main:app --reload --port 8000"
echo "  Frontend: cd frontend && npm run dev"
echo ""
echo "Or with Docker: docker-compose up"
