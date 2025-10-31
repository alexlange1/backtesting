#!/bin/bash
#
# Bittensor TAO Index - Setup Script (Production)
# ================================================
# Sets up the production environment for TAO Index backtesting
#
# Author: Alexander Lange
# Date: October 22, 2025

set -e  # Exit on error

echo "============================================="
echo "🚀 Bittensor TAO Index - Setup"
echo "============================================="
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8+ first."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "✅ Python found: $PYTHON_VERSION"
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "✅ Dependencies installed successfully"
else
    echo "❌ Failed to install dependencies"
    exit 1
fi
echo ""

# Create required directories
echo "📁 Creating required directories..."
mkdir -p logs
mkdir -p data/emissions
mkdir -p backtest_results

echo "✅ Directories created:"
echo "   - logs/"
echo "   - data/emissions/"
echo "   - backtest_results/"
echo ""

# Copy environment template if .env doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "✅ .env file created (please customize as needed)"
else
    echo "✅ .env file already exists"
fi
echo ""

# Make Python scripts executable
echo "🔧 Making scripts executable..."
chmod +x tao_index_backtest_dynamic.py
chmod +x emissions_collector.py
chmod +x scheduler.py
echo "✅ Scripts are now executable"
echo ""

# Validate configuration
echo "🔍 Validating configuration..."
python3 -c "from config import Config; Config.print_config()"

echo ""
echo "============================================="
echo "✅ Setup completed successfully!"
echo "============================================="
echo ""
echo "📋 Quick Start:"
echo ""
echo "   # Run TAO Index backtest"
echo "   python tao_index_backtest_dynamic.py"
echo ""
echo "   # Collect emissions data (one-time)"
echo "   python emissions_collector.py"
echo ""
echo "   # Start scheduled emissions collection"
echo "   python scheduler.py"
echo ""
echo "📖 See README.md for complete documentation"
echo ""
