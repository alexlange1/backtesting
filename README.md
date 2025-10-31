# TAO20 Backtesting Framework

A comprehensive backtesting framework for the TAO20 index strategy on the Bittensor network.

## Overview

This repository contains tools for backtesting the TAO20 index strategy, which is an emission-weighted index of the top 20 Bittensor subnets. The framework includes:

- Historical price data fetching from Bittensor archive nodes
- Dynamic APY calculation for alpha token staking (power law model)
- NAV calculation with both price returns and yield
- Professional visualization with detailed performance attribution
- Market comparison tools

## Core Files

- `tao20_unified_backtest.py` - **Main unified backtesting script** (recommended)
  - Simple mode: Fast simulation with scenario analysis (~10 seconds)
  - Historical mode: Real price data from archive node (5+ minutes)
  - Dynamic APY modeling with power law calibration
  - Emission-based weighting strategy
  
- `tao20_real_backtest.py` - Alternative backtest with historical portfolio weights
- `tao20_market_comparison.py` - Market comparison tools
- `emissions_collector.py` - Data collection from Bittensor network
- `show_comparison.py` - Quick results viewer
- `config.py` - Configuration settings
- `requirements.txt` - Python dependencies
- `setup.sh` - Setup script

## Quick Start

### Installation

```bash
pip install -r requirements.txt
# or
./setup.sh
```

### Run Unified Backtest (Recommended)

```bash
# Fast 30-day simulation
python tao20_unified_backtest.py --mode simple --days 30

# Historical backtest with real prices (slow)
python tao20_unified_backtest.py --mode historical --days 7

# Validate APY model
python tao20_unified_backtest.py --validate
```

### Run Alternative Backtest

```bash
python tao20_real_backtest.py
```

### View Results

```bash
python show_comparison.py
```

## Features

### Dynamic APY Modeling
- Power law calibrated to known subnet APYs (70% for subnet 64, 135% for subnet 120)
- APY fluctuates with subnet maturity (newer subnets have higher APY)
- Based on supply as age proxy
- Realistic economics (staking ratio decreases as subnets mature)

### Emission-Based Weighting
- Portfolio contains top emission-weighted subnets
- Dynamic rebalancing support
- Weighted average APY calculation

### Multiple Backtest Modes
- **Simple Mode**: Fast simulation with multiple price scenarios
- **Historical Mode**: Real historical prices from archive node
- Both modes support APY compounding and price returns

## Requirements

- Python 3.8+
- Bittensor SDK
- btcli command-line tool
- Access to Bittensor network (finney)

## Results

The framework generates:
- CSV files with detailed performance data in `backtest_results/`
- NAV calculations with price and APY attribution
- Performance metrics and statistics

## Author

Alexander Lange - October 2025