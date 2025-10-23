# TAO20 Backtesting Framework

A comprehensive backtesting framework for the TAO20 index strategy on the Bittensor network.

## Overview

This repository contains tools for backtesting the TAO20 index strategy, which is an emission-weighted index of the top 20 Bittensor subnets. The framework includes:

- Historical price data fetching from Bittensor archive nodes
- APY calculation for alpha token staking
- NAV calculation with both price returns and yield
- Professional visualization with detailed performance attribution
- Market comparison tools

## Files

- `tao20_real_backtest.py` - Main backtesting script with real historical weights
- `tao20_market_comparison.py` - Market comparison tools
- `config.py` - Configuration settings
- `requirements.txt` - Python dependencies

## Features

### TAO20 Real Backtest
- Uses actual historical portfolio weights from September 14th and October 12th
- Fetches real historical alpha token prices from Bittensor archive
- Calculates NAV with both price returns and APY yields
- Generates detailed 3-panel performance charts
- Shows daily returns breakdown and cumulative attribution

### Market Comparison
- Compares TAO20 performance against total market (sum of all subnet prices)
- Normalized performance tracking
- Relative outperformance analysis

## Requirements

- Python 3.8+
- Bittensor SDK
- btcli command-line tool
- Access to Bittensor network (finney)

## Installation

```bash
pip install bittensor pandas matplotlib
```

## Usage

### Run TAO20 Backtest
```bash
python tao20_real_backtest.py
```

### Run Market Comparison
```bash
python tao20_market_comparison.py
```

## Results

The framework generates:
- CSV files with detailed performance data
- Professional charts showing NAV development
- Daily returns breakdown (price vs APY)
- Cumulative return attribution
- Market comparison visualizations

## Author

Alexander Lange - October 2025