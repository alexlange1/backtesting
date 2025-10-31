#!/usr/bin/env python3
"""
TAO20 Market Comparison
========================
Compare TAO20 performance vs total market (sum of all subnet alpha prices)

Author: Alexander Lange
Date: October 22, 2025
"""

import os
import json
import re
import subprocess
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
NETWORK = 'finney'
ARCHIVE_NODE = 'https://archive.chain.opentensor.ai:443'
START_NAV = 1.0
BLOCKS_PER_DAY = 7200


def get_subnet_data():
    """Get current subnet data for all subnets."""
    logger.info("Fetching current subnet data...")
    
    try:
        result = subprocess.run(
            ['btcli', 'subnets', 'list', '--network', NETWORK, '--json-output'],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            logger.error(f"btcli failed: {result.stderr}")
            return {}
        
        # Clean up JSON output
        output = result.stdout
        output = re.sub(r'\\n', ' ', output)
        output = re.sub(r'\\[trm]', '', output)
        output = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', output)
        
        data = json.loads(output)
        
        # Extract subnets dict from response
        if isinstance(data, dict) and 'subnets' in data:
            subnets_data = data['subnets']
        else:
            subnets_data = data
        
        subnet_info = {}
        for netuid_str, subnet in subnets_data.items():
            netuid = int(subnet['netuid'])
            
            # Parse emission
            emission_val = subnet.get('emission', 0)
            if isinstance(emission_val, str):
                emission_clean = emission_val.replace('%', '').strip()
                try:
                    emission = float(emission_clean) / 100
                except:
                    emission = 0.0
            else:
                emission = float(emission_val) if emission_val else 0.0
            
            # Calculate APY from emission
            alpha_emissions_per_day = emission * 7200 * 2
            alpha_supply = float(subnet.get('supply', 4096))
            staked_ratio = estimate_staked_alpha_ratio(alpha_supply)
            staked_alpha = alpha_supply * staked_ratio
            
            alpha_apy = (alpha_emissions_per_day / staked_alpha * 365 * 100) if staked_alpha > 0 else 0
            
            subnet_info[netuid] = {
                'emission': emission,
                'alpha_apy': alpha_apy,
                'supply': alpha_supply
            }
        
        logger.info(f"✓ Loaded {len(subnet_info)} subnets")
        return subnet_info
        
    except Exception as e:
        logger.error(f"Failed to get subnet data: {e}")
        return {}


def estimate_staked_alpha_ratio(alpha_supply: float) -> float:
    """Estimate staked ratio based on supply (proxy for age)."""
    if alpha_supply < 1000:
        return 0.10
    elif alpha_supply < 2000:
        return 0.15
    elif alpha_supply < 3000:
        return 0.25
    elif alpha_supply < 4000:
        return 0.40
    else:
        return 0.50


def get_current_block() -> int:
    """Get current block number."""
    try:
        import bittensor as bt
        subtensor = bt.subtensor(network=NETWORK)
        return subtensor.get_current_block()
    except Exception as e:
        logger.error(f"Failed to get block: {e}")
        return 0


def fetch_price_at_block(netuid: int, block: int, subtensor) -> float:
    """Fetch alpha price at specific block."""
    try:
        balance = subtensor.get_subnet_price(netuid=netuid, block=block)
        price_value = float(balance.tao)
        return price_value if price_value > 0 else None
    except Exception as e:
        return None


def calculate_total_market_value(dates, subnet_data):
    """
    Calculate total market value (sum of all subnet alpha prices).
    
    Args:
        dates: List of dates to calculate for
        subnet_data: Subnet information
    
    Returns:
        DataFrame with total market value normalized to start at 1.0
    """
    logger.info("Calculating total market value (sum of all subnet prices)...")
    logger.info(f"Fetching prices for {len(subnet_data)} subnets over {len(dates)} days")
    logger.info("This will take a few minutes...")
    
    import bittensor as bt
    subtensor = bt.subtensor(network=NETWORK, archive_endpoints=[ARCHIVE_NODE])
    
    # Get current block and calculate blocks for each date
    current_block = get_current_block()
    if current_block == 0:
        logger.error("Failed to get current block")
        return pd.DataFrame()
    
    start_date = dates[0]
    days_back = (datetime.now() - start_date).days
    start_block = current_block - (days_back * BLOCKS_PER_DAY)
    
    results = []
    all_subnets = list(subnet_data.keys())
    
    for day_idx, date in enumerate(dates):
        block = start_block + (day_idx * BLOCKS_PER_DAY)
        
        # Fetch prices for all subnets and sum them
        total_price_sum = 0.0
        fetched_count = 0
        
        for netuid in all_subnets:
            price = fetch_price_at_block(netuid, block, subtensor)
            if price and price > 0:
                total_price_sum += price
                fetched_count += 1
        
        results.append({
            'date': date,
            'total_market_value': total_price_sum,
            'n_subnets': fetched_count
        })
        
        if day_idx % 10 == 0:
            logger.info(f"Day {day_idx} ({date.strftime('%Y-%m-%d')}): Total Market Value={total_price_sum:.4f} TAO, Subnets={fetched_count}")
        
        # Small delay to avoid rate limiting
        time.sleep(0.1)
    
    df_market = pd.DataFrame(results)
    
    # Normalize to start at 1.0
    if len(df_market) > 0 and df_market.iloc[0]['total_market_value'] > 0:
        start_value = df_market.iloc[0]['total_market_value']
        df_market['market_index'] = df_market['total_market_value'] / start_value
    else:
        df_market['market_index'] = 1.0
    
    logger.info(f"✓ Calculated total market value over {len(df_market)} days")
    
    return df_market


def calculate_market_comparison():
    """Compare TAO20 vs total market (sum of all subnet prices)."""
    logger.info("=" * 80)
    logger.info("TAO20 vs TOTAL MARKET COMPARISON")
    logger.info("=" * 80)
    logger.info("")
    
    # Load TAO20 data
    tao20_file = 'backtest_results/tao20_extended_backtest_20251022_201019.csv'
    if not os.path.exists(tao20_file):
        logger.error(f"TAO20 data not found: {tao20_file}")
        return
    
    df_tao20 = pd.read_csv(tao20_file)
    df_tao20['date'] = pd.to_datetime(df_tao20['date'])
    
    start_date = df_tao20.iloc[0]['date']
    end_date = df_tao20.iloc[-1]['date']
    
    logger.info(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    logger.info("")
    
    # Get subnet data
    subnet_data = get_subnet_data()
    if not subnet_data:
        logger.error("Failed to get subnet data")
        return
    
    # Calculate total market value
    dates = pd.to_datetime(df_tao20['date']).tolist()
    df_market = calculate_total_market_value(dates, subnet_data)
    
    # Merge datasets
    df_merged = pd.merge(
        df_tao20[['date', 'nav', 'price_only_nav']],
        df_market[['date', 'market_index', 'total_market_value']],
        on='date',
        how='inner'
    )
    
    if df_merged.empty:
        logger.error("No overlapping dates")
        return
    
    logger.info(f"Matched {len(df_merged)} days of data")
    logger.info("")
    
    # Calculate returns
    tao20_return = ((df_merged.iloc[-1]['nav'] / df_merged.iloc[0]['nav']) - 1) * 100
    tao20_price_only = ((df_merged.iloc[-1]['price_only_nav'] / df_merged.iloc[0]['price_only_nav']) - 1) * 100
    market_return = ((df_merged.iloc[-1]['market_index'] / df_merged.iloc[0]['market_index']) - 1) * 100
    
    outperformance = tao20_return - market_return
    
    # Results
    logger.info("PERFORMANCE COMPARISON")
    logger.info("=" * 80)
    logger.info(f"TAO20 Index (with APY):          {tao20_return:+.2f}%")
    logger.info(f"TAO20 (price only):              {tao20_price_only:+.2f}%")
    logger.info(f"Total Market (All Subnets):      {market_return:+.2f}%")
    logger.info("")
    logger.info(f"TAO20 vs Market:                 {outperformance:+.2f}%")
    
    if outperformance > 0:
        logger.info(f"✅ TAO20 OUTPERFORMED MARKET by {abs(outperformance):.2f}%")
    else:
        logger.info(f"❌ TAO20 UNDERPERFORMED MARKET by {abs(outperformance):.2f}%")
    
    logger.info("")
    
    # Create comparison plot
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 12))
    
    # Plot 1: Normalized performance
    ax1.plot(df_merged['date'], df_merged['nav'], 'b-', linewidth=3, label='TAO20 Index (Top 20, with APY)', zorder=3)
    ax1.plot(df_merged['date'], df_merged['market_index'], 'green', linewidth=2.5, linestyle='--', 
             label='Total Market (Sum of All Subnet Prices)', zorder=2, alpha=0.8)
    ax1.axhline(y=1.0, color='gray', linestyle=':', alpha=0.5, label='Starting Value (1.0)')
    
    # Mark rebalancing dates
    rebalance_dates = [
        datetime(2025, 8, 4),
        datetime(2025, 8, 18),
        datetime(2025, 9, 1),
        datetime(2025, 9, 14),
        datetime(2025, 10, 12)
    ]
    for rb_date in rebalance_dates:
        if start_date <= rb_date <= end_date:
            ax1.axvline(x=rb_date, color='purple', alpha=0.2, linestyle='--', linewidth=1.5)
    
    ax1.set_xlabel('Date', fontsize=12)
    ax1.set_ylabel('Normalized Value (Starting = 1.0)', fontsize=12)
    ax1.set_title(f'TAO20 vs Total Market (Aug 4 - Oct 22, 2025)', fontsize=14, fontweight='bold')
    ax1.legend(loc='best', fontsize=10)
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # Add performance text box
    textstr = f'TAO20 (Top 20):       {tao20_return:+.2f}%\nTotal Market:         {market_return:+.2f}%\nOutperformance:       {outperformance:+.2f}%'
    props = dict(boxstyle='round', facecolor='lightblue', alpha=0.8)
    ax1.text(0.02, 0.98, textstr, transform=ax1.transAxes, fontsize=11,
            verticalalignment='top', bbox=props, family='monospace')
    
    # Plot 2: Relative performance
    df_merged['tao20_return'] = ((df_merged['nav'] / df_merged.iloc[0]['nav']) - 1) * 100
    df_merged['market_return'] = ((df_merged['market_index'] / df_merged.iloc[0]['market_index']) - 1) * 100
    df_merged['outperformance'] = df_merged['tao20_return'] - df_merged['market_return']
    
    # Fill area based on outperformance
    ax2.plot(df_merged['date'], df_merged['outperformance'], 'purple', linewidth=2.5, label='TAO20 vs Market', zorder=2)
    ax2.fill_between(df_merged['date'], 0, df_merged['outperformance'], 
                     where=(df_merged['outperformance'] >= 0), 
                     color='green', alpha=0.3, label='TAO20 outperforming', interpolate=True)
    ax2.fill_between(df_merged['date'], 0, df_merged['outperformance'], 
                     where=(df_merged['outperformance'] < 0), 
                     color='red', alpha=0.3, label='TAO20 underperforming', interpolate=True)
    ax2.axhline(y=0, color='black', linestyle='-', linewidth=1)
    
    # Mark rebalancing dates
    for rb_date in rebalance_dates:
        if start_date <= rb_date <= end_date:
            ax2.axvline(x=rb_date, color='purple', alpha=0.2, linestyle='--', linewidth=1.5)
    
    ax2.set_xlabel('Date', fontsize=12)
    ax2.set_ylabel('Relative Performance (%)', fontsize=12)
    ax2.set_title('TAO20 Relative Performance vs Total Market', fontsize=13, fontweight='bold')
    ax2.legend(loc='best', fontsize=10)
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    plt.tight_layout()
    
    # Save
    os.makedirs('backtest_results', exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    plot_file = f"backtest_results/tao20_vs_market_{timestamp}.png"
    plt.savefig(plot_file, dpi=150, bbox_inches='tight')
    logger.info(f"✓ Plot saved: {plot_file}")
    logger.info("")
    
    # Open plot
    os.system(f"open {plot_file}")
    
    return df_merged


if __name__ == '__main__':
    calculate_market_comparison()

