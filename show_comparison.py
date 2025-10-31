#!/usr/bin/env python3
"""Quick script to show TAO20 vs market comparison results."""

import pandas as pd
from glob import glob

# Find the most recent comparison data
csv_files = glob('backtest_results/tao20_extended_backtest_*.csv')
if not csv_files:
    print("No backtest data found")
    exit(1)

latest_file = max(csv_files)
print(f"Reading: {latest_file}")
print()

df = pd.read_csv(latest_file)
df['date'] = pd.to_datetime(df['date'])

start_nav = df.iloc[0]['nav']
end_nav = df.iloc[-1]['nav']
start_price_only = df.iloc[0]['price_only_nav']
end_price_only = df.iloc[-1]['price_only_nav']

tao20_return = ((end_nav / start_nav) - 1) * 100
tao20_price_only = ((end_price_only / start_price_only) - 1) * 100

print("=" * 80)
print(f"TAO20 BACKTEST RESULTS")
print("=" * 80)
print(f"Period: {df.iloc[0]['date'].strftime('%Y-%m-%d')} to {df.iloc[-1]['date'].strftime('%Y-%m-%d')}")
print(f"Days: {len(df)}")
print()
print(f"TAO20 Index (with APY):    {tao20_return:+.2f}%")
print(f"TAO20 (price only):        {tao20_price_only:+.2f}%")
print(f"APY Contribution:          {tao20_return - tao20_price_only:+.2f}%")
print()
print(f"Starting NAV:              {start_nav:.4f}")
print(f"Ending NAV:                {end_nav:.4f}")
print("=" * 80)












