#!/usr/bin/env python3
"""
TAO20 Index vs Root Network Staking Comparison
===============================================
Compares the performance of:
1. TAO20 Index (diversified subnet portfolio with price appreciation + APY)
2. Root Network Staking (stable value, staking rewards only)
3. Simple TAO HODL (no staking, no diversification)

Author: Alexander Lange
Date: October 28, 2025
"""

import os
import glob
import json
import logging
from datetime import datetime, timedelta
from typing import Dict
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

START_NAV = 1.0
ROOT_STAKING_APY = 10.0  # Conservative estimate for root network staking


def load_tao20_results() -> pd.DataFrame:
    """Load the most recent TAO20 backtest results."""
    logger.info("Loading TAO20 backtest results...")
    
    # Find most recent backtest file
    backtest_files = sorted(glob.glob('backtest_results/tao20_backtest_*.csv'))
    if not backtest_files:
        logger.error("No TAO20 backtest results found")
        return pd.DataFrame()
    
    latest_file = backtest_files[-1]
    logger.info(f"Loading: {latest_file}")
    
    df = pd.read_csv(latest_file)
    df['date'] = pd.to_datetime(df['date'])
    
    logger.info(f"✓ Loaded {len(df)} days of TAO20 data")
    return df


def simulate_root_staking(start_date: datetime, end_date: datetime, 
                          initial_nav: float = START_NAV, 
                          apy: float = ROOT_STAKING_APY) -> pd.DataFrame:
    """
    Simulate root network staking with compound returns.
    
    Since subnet 0 has a stable value (no price fluctuation), returns come
    entirely from staking rewards.
    """
    logger.info(f"Simulating root network staking (APY: {apy:.2f}%)...")
    
    days = (end_date - start_date).days + 1
    daily_rate = (apy / 100) / 365
    
    results = []
    nav = initial_nav
    
    for day in range(days):
        current_date = start_date + timedelta(days=day)
        daily_reward = nav * daily_rate
        nav += daily_reward
        
        results.append({
            'date': current_date,
            'nav': nav,
            'daily_return': daily_reward / (nav - daily_reward) * 100 if day > 0 else 0
        })
    
    df = pd.DataFrame(results)
    logger.info(f"✓ Simulated {len(df)} days")
    return df


def simulate_tao_price_only(tao20_df: pd.DataFrame) -> pd.DataFrame:
    """
    Simulate holding just TAO (subnet 1) without staking or diversification.
    Uses TAO price movements from the emissions data.
    """
    logger.info("Calculating TAO-only price performance...")
    
    # Load TAO (subnet 1) prices from emissions data
    data_dir = 'data/emissions_v2'
    files = sorted(glob.glob(f'{data_dir}/emissions_v2_*.json'))
    
    tao_prices = {}
    for filepath in files:
        filename = os.path.basename(filepath)
        date_str = filename.replace('emissions_v2_', '').replace('.json', '')
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            prices = data.get('emissions', {})
            if '1' in prices:  # Subnet 1 is TAO
                tao_prices[date_str] = float(prices['1'])
        except Exception as e:
            continue
    
    # Match dates with TAO20 backtest
    results = []
    initial_price = None
    
    for _, row in tao20_df.iterrows():
        date_str = row['date'].strftime('%Y%m%d')
        if date_str in tao_prices:
            price = tao_prices[date_str]
            if initial_price is None:
                initial_price = price
            
            # Calculate NAV relative to initial price
            nav = START_NAV * (price / initial_price)
            results.append({
                'date': row['date'],
                'nav': nav
            })
    
    df = pd.DataFrame(results)
    if len(df) > 0:
        logger.info(f"✓ Loaded TAO price data for {len(df)} days")
    else:
        logger.warning("No TAO price data available, using flat baseline")
        df = pd.DataFrame({
            'date': tao20_df['date'],
            'nav': START_NAV
        })
    
    return df


def create_comparison(tao20_df: pd.DataFrame, root_df: pd.DataFrame, 
                     tao_df: pd.DataFrame):
    """Create comprehensive comparison visualization."""
    logger.info("Creating comparison visualization...")
    
    # Calculate metrics
    days = len(tao20_df)
    years = days / 365
    
    # TAO20 metrics
    tao20_return = (tao20_df.iloc[-1]['nav'] - START_NAV) / START_NAV * 100
    tao20_cagr = ((tao20_df.iloc[-1]['nav'] / START_NAV) ** (1/years) - 1) * 100
    
    # Root network metrics
    root_return = (root_df.iloc[-1]['nav'] - START_NAV) / START_NAV * 100
    root_cagr = ((root_df.iloc[-1]['nav'] / START_NAV) ** (1/years) - 1) * 100
    
    # TAO only metrics
    tao_return = (tao_df.iloc[-1]['nav'] - START_NAV) / START_NAV * 100 if len(tao_df) > 0 else 0
    tao_cagr = ((tao_df.iloc[-1]['nav'] / START_NAV) ** (1/years) - 1) * 100 if len(tao_df) > 0 else 0
    
    # Create figure
    fig = plt.figure(figsize=(20, 12))
    gs = fig.add_gridspec(3, 2, hspace=0.3, wspace=0.3)
    
    # 1. Main comparison chart (large, top)
    ax1 = fig.add_subplot(gs[0, :])
    ax1.plot(tao20_df['date'], tao20_df['nav'], 'b-', linewidth=3, label='TAO20 Index', alpha=0.9)
    ax1.plot(root_df['date'], root_df['nav'], 'g-', linewidth=2.5, label='Root Network Staking', alpha=0.8)
    if len(tao_df) > 0:
        ax1.plot(tao_df['date'], tao_df['nav'], 'orange', linewidth=2, label='TAO (Subnet 1) Only', alpha=0.7)
    ax1.axhline(y=START_NAV, color='gray', linestyle=':', alpha=0.5, label='Starting NAV')
    
    ax1.set_xlabel('Date', fontsize=12, fontweight='bold')
    ax1.set_ylabel('NAV', fontsize=12, fontweight='bold')
    ax1.set_title('Investment Strategy Comparison: TAO20 Index vs Root Staking vs TAO Only', 
                  fontsize=15, fontweight='bold', pad=20)
    ax1.legend(loc='best', fontsize=11, framealpha=0.9)
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=10)
    
    # Add performance text box
    textstr = f'TAO20: {tao20_return:.2f}% ({tao20_cagr:.1f}% CAGR)\n'
    textstr += f'Root Staking: {root_return:.2f}% ({root_cagr:.1f}% CAGR)\n'
    textstr += f'TAO Only: {tao_return:.2f}% ({tao_cagr:.1f}% CAGR)'
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.8)
    ax1.text(0.02, 0.98, textstr, transform=ax1.transAxes, fontsize=11,
            verticalalignment='top', bbox=props, family='monospace')
    
    # 2. Cumulative returns comparison
    ax2 = fig.add_subplot(gs[1, 0])
    ax2.plot(tao20_df['date'], (tao20_df['nav'] / START_NAV - 1) * 100, 
            'b-', linewidth=2.5, label='TAO20', alpha=0.9)
    ax2.plot(root_df['date'], (root_df['nav'] / START_NAV - 1) * 100, 
            'g-', linewidth=2, label='Root Staking', alpha=0.8)
    if len(tao_df) > 0:
        ax2.plot(tao_df['date'], (tao_df['nav'] / START_NAV - 1) * 100, 
                'orange', linewidth=2, label='TAO Only', alpha=0.7)
    ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
    ax2.set_xlabel('Date', fontsize=11)
    ax2.set_ylabel('Cumulative Return (%)', fontsize=11)
    ax2.set_title('Cumulative Returns', fontsize=12, fontweight='bold')
    ax2.legend(loc='best', fontsize=9)
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=9)
    
    # 3. Volatility comparison (rolling 30-day std)
    ax3 = fig.add_subplot(gs[1, 1])
    tao20_returns = tao20_df['nav'].pct_change() * 100
    tao20_vol = tao20_returns.rolling(window=30, min_periods=1).std()
    
    root_returns = root_df['nav'].pct_change() * 100
    root_vol = root_returns.rolling(window=30, min_periods=1).std()
    
    ax3.plot(tao20_df['date'], tao20_vol, 'b-', linewidth=2, label='TAO20', alpha=0.7)
    ax3.plot(root_df['date'], root_vol, 'g-', linewidth=2, label='Root Staking', alpha=0.7)
    ax3.set_xlabel('Date', fontsize=11)
    ax3.set_ylabel('Daily Volatility (%) [30d rolling]', fontsize=11)
    ax3.set_title('Volatility Comparison', fontsize=12, fontweight='bold')
    ax3.legend(loc='best', fontsize=9)
    ax3.grid(True, alpha=0.3)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=9)
    
    # 4. Performance metrics table
    ax4 = fig.add_subplot(gs[2, :])
    ax4.axis('off')
    
    metrics_data = [
        ['Metric', 'TAO20 Index', 'Root Staking', 'TAO Only'],
        ['Final NAV', f'{tao20_df.iloc[-1]["nav"]:.4f}', 
         f'{root_df.iloc[-1]["nav"]:.4f}', 
         f'{tao_df.iloc[-1]["nav"]:.4f}' if len(tao_df) > 0 else 'N/A'],
        ['Total Return', f'{tao20_return:.2f}%', f'{root_return:.2f}%', 
         f'{tao_return:.2f}%' if len(tao_df) > 0 else 'N/A'],
        ['CAGR', f'{tao20_cagr:.2f}%', f'{root_cagr:.2f}%', 
         f'{tao_cagr:.2f}%' if len(tao_df) > 0 else 'N/A'],
        ['Volatility (std)', f'{tao20_returns.std():.3f}%', f'{root_returns.std():.3f}%', 'N/A'],
        ['Sharpe Ratio', f'{(tao20_cagr / (tao20_returns.std() * np.sqrt(252))):.2f}' if tao20_returns.std() > 0 else 'N/A',
         f'{(root_cagr / (root_returns.std() * np.sqrt(252))):.2f}' if root_returns.std() > 0 else 'N/A', 'N/A'],
        ['Max Drawdown', f'{((tao20_df["nav"] / tao20_df["nav"].cummax()) - 1).min() * 100:.2f}%',
         f'{((root_df["nav"] / root_df["nav"].cummax()) - 1).min() * 100:.2f}%', 'N/A'],
    ]
    
    table = ax4.table(cellText=metrics_data, cellLoc='center', loc='center',
                     bbox=[0.1, 0.2, 0.8, 0.7])
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 2)
    
    # Style header row
    for i in range(4):
        table[(0, i)].set_facecolor('#4CAF50')
        table[(0, i)].set_text_props(weight='bold', color='white')
    
    # Style data rows
    for i in range(1, len(metrics_data)):
        for j in range(4):
            if j == 0:
                table[(i, j)].set_facecolor('#e0e0e0')
                table[(i, j)].set_text_props(weight='bold')
            else:
                table[(i, j)].set_facecolor('#f5f5f5')
    
    ax4.text(0.5, 0.95, 'Performance Metrics Summary', 
            transform=ax4.transAxes, fontsize=13, fontweight='bold',
            ha='center', va='top')
    
    # Save
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f'backtest_results/strategy_comparison_{timestamp}.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    logger.info(f"✓ Saved: {output_file}")
    
    # Open
    os.system(f"open {output_file}")
    
    return metrics_data


def main():
    logger.info("=" * 80)
    logger.info("STRATEGY COMPARISON: TAO20 vs ROOT STAKING vs TAO ONLY")
    logger.info("=" * 80)
    logger.info("")
    
    # Load TAO20 results
    tao20_df = load_tao20_results()
    if tao20_df.empty:
        logger.error("Cannot proceed without TAO20 data")
        return
    
    # Get date range from TAO20 data
    start_date = tao20_df.iloc[0]['date']
    end_date = tao20_df.iloc[-1]['date']
    
    # Simulate root network staking
    root_df = simulate_root_staking(start_date, end_date)
    
    # Get TAO-only performance
    tao_df = simulate_tao_price_only(tao20_df)
    
    # Create comparison
    metrics = create_comparison(tao20_df, root_df, tao_df)
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("COMPARISON COMPLETE")
    logger.info("=" * 80)
    logger.info("")
    logger.info("Key Insights:")
    logger.info(f"  • TAO20 Index: Diversified exposure with {len(set([col for col in tao20_df.columns if 'price' in col.lower()]))} subnets")
    logger.info(f"  • Root Staking: Stable {ROOT_STAKING_APY:.1f}% APY with no price volatility")
    logger.info(f"  • TAO Only: Single subnet exposure to subnet 1")
    logger.info("")


if __name__ == '__main__':
    main()

