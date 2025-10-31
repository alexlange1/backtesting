#!/usr/bin/env python3
"""
Quick Test Script for TAO20 Unified Backtest
=============================================
Tests the backtest system with a short 14-day period to validate functionality
before running the full 260-day backtest.

This should complete in ~5-10 minutes.
"""

import sys
from datetime import datetime
from pathlib import Path

# Temporarily modify config for quick test
import config
original_start = config.Config.START_DATE
original_end = config.Config.END_DATE

# Set to 14 days (2 weeks) for quick test
config.Config.START_DATE = datetime(2025, 10, 1)
config.Config.END_DATE = datetime(2025, 10, 14)

print("=" * 80)
print("QUICK TEST - TAO20 UNIFIED BACKTEST")
print("=" * 80)
print(f"Original period: {original_start.date()} to {original_end.date()}")
print(f"Test period: {config.Config.START_DATE.date()} to {config.Config.END_DATE.date()}")
print("Duration: 14 days (2 weeks)")
print("Expected runtime: 5-10 minutes")
print("=" * 80)
print()

# Import and run the main backtest
import tao20_unified_backtest

# Run the test
result = tao20_unified_backtest.main()

# Restore original dates
config.Config.START_DATE = original_start
config.Config.END_DATE = original_end

print()
print("=" * 80)
print("QUICK TEST COMPLETE")
print("=" * 80)
print()
print("If test was successful, run the full backtest:")
print("  python tao20_unified_backtest.py")
print()

sys.exit(result)


