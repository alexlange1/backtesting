#!/usr/bin/env python3
"""
TAO20 Real Historical Backtest - SHORT VERSION (Last 30 days)
================================
Test version to verify the logic works correctly before running full backtest.
"""

import sys
from datetime import datetime, timedelta

# Import the main backtest function
from tao20_real_backtest import run_backtest

if __name__ == '__main__':
    # Test with last 30 days only
    end = datetime.now()
    start = end - timedelta(days=30)
    
    print(f"Running SHORT backtest: {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}")
    print(f"This tests the logic before running the full Feb-Oct backtest")
    print("=" * 80)
    
    run_backtest(start, end)









