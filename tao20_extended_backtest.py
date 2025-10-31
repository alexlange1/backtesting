#!/usr/bin/env python3
"""
TAO20 Extended Historical Backtest
===================================
Complete backtest from August 4 to October 22, 2025 with all rebalancing periods.

Rebalancing dates:
- August 4: Initial weights
- August 18: First rebalance
- September 1: Second rebalance  
- September 14: Third rebalance
- October 12: Fourth rebalance
- October 22: End date

Author: Alexander Lange
Date: October 22, 2025
"""

import os
import json
import re
import subprocess
import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

NETWORK = 'finney'
ARCHIVE_NODE = 'wss://archive.chain.opentensor.ai:443'
BLOCKS_PER_DAY = 7200
START_NAV = 1.0

# Historical TAO20 portfolio weights for all rebalancing periods
AUG_4_WEIGHTS = {
    64: 0.1643,   # Chutes
    120: 0.1136,  # Affine
    51: 0.0876,   # Lium
    4: 0.0751,    # Targon
    3: 0.0709,    # Templar
    56: 0.0645,   # Gradients
    8: 0.0592,    # PTN
    9: 0.0416,    # Iota
    5: 0.0374,    # Hone
    44: 0.0349,   # Score
    14: 0.0304,   # TAOhash
    33: 0.0266,   # Ready
    34: 0.0267,   # Bitmind
    39: 0.0233,   # Basilica
    1: 0.0230,    # Apex
    17: 0.0228,   # 404 Gen
    13: 0.0224,   # Data
    19: 0.0243,   # Nineteen
    15: 0.0255,   # Quant
    62: 0.0261    # Ridges
}

AUG_18_WEIGHTS = {
    64: 0.1662,   # Chutes
    120: 0.0996,  # Affine
    51: 0.0824,   # Lium
    4: 0.0739,    # Targon
    3: 0.0674,    # Templar
    56: 0.0635,   # Gradients
    8: 0.0601,    # PTN
    62: 0.0538,   # Ridges
    9: 0.0403,    # Iota
    5: 0.0354,    # Hone
    44: 0.0305,   # Score
    33: 0.0300,   # Ready
    34: 0.0281,   # Bitmind
    11: 0.0277,   # Dippy
    15: 0.0265,   # Quant
    39: 0.0251,   # Basilica
    19: 0.0238,   # Nineteen
    17: 0.0222,   # 404
    13: 0.0219,   # Data Universe
    14: 0.0217    # TAOHash
}

SEPT_1_WEIGHTS = {
    64: 0.1533,   # Chutes
    62: 0.1097,   # Ridges
    120: 0.1073,  # Affine
    51: 0.0858,   # Lium
    4: 0.0692,    # Targon
    3: 0.0642,    # Templar
    56: 0.0569,   # Gradients
    8: 0.0568,    # PTN
    5: 0.0337,    # Hone
    93: 0.0281,   # Bitcast
    9: 0.0280,    # Iota
    34: 0.0279,   # Bitmind
    11: 0.0272,   # Dippy
    44: 0.0262,   # Score
    39: 0.0226,   # Basilica
    19: 0.0210,   # Nineteen
    33: 0.0210,   # Ready
    13: 0.0206,   # Data
    17: 0.0205,   # 404 Gen
    1: 0.0201     # Apex
}

SEPT_14_WEIGHTS = {
    64: 0.15490265080834242,
    120: 0.11499584392158993,
    62: 0.11325810549343905,
    51: 0.08659696482673056,
    4: 0.06831600275049653,
    56: 0.06053416057270168,
    8: 0.052018069013671495,
    3: 0.051732693468386284,
    93: 0.03778109942706883,
    5: 0.03678363557454613,
    11: 0.02975089181450724,
    34: 0.02779743884183065,
    44: 0.026031863386321786,
    9: 0.025047437865686237,
    123: 0.020516990373303078,
    35: 0.020211464249694704,
    17: 0.018868410663745828,
    39: 0.018544588714866278,
    33: 0.01817703455216786,
    19: 0.01813465368090342
}

OCT_12_WEIGHTS = {
    64: 0.13053443533600298,
    120: 0.11246736942045972,
    62: 0.11057163936461911,
    51: 0.09438044187996876,
    4: 0.07376200712179182,
    56: 0.05700999456857358,
    8: 0.05086282117452847,
    3: 0.04714329285786645,
    5: 0.03994121675196882,
    41: 0.03352320872268299,
    75: 0.031082854970786312,
    34: 0.030441348121325137,
    9: 0.030218885276463443,
    44: 0.02652781571617138,
    33: 0.025377565504576555,
    93: 0.024591222074727134,
    35: 0.021109357848735,
    50: 0.02071365485799247,
    48: 0.019988979256334423,
    11: 0.019751889174425517
}

# Rebalancing dates
REBALANCE_DATES = [
    (datetime(2025, 8, 4), AUG_4_WEIGHTS),
    (datetime(2025, 8, 18), AUG_18_WEIGHTS),
    (datetime(2025, 9, 1), SEPT_1_WEIGHTS),
    (datetime(2025, 9, 14), SEPT_14_WEIGHTS),
    (datetime(2025, 10, 12), OCT_12_WEIGHTS),
]

# APY Model
class AlphaAPYModel:
    TAO_PER_DAY = 7200
    ALPHA_MULTIPLIER = 2
    
    def estimate_staking_ratio(self, supply: float) -> float:
        if supply <= 0:
            return 0.15
        s1, r1 = 1.129, 0.2066
        s2, r2 = 3.166, 0.1838
        supply_m = supply / 1_000_000
        b = math.log(r2 / r1) / math.log(s2 / s1)
        a = r1 / (s1 ** b)
        estimated_ratio = a * (supply_m ** b)
        estimated_ratio = max(0.05, min(0.40, estimated_ratio))
        if supply_m < 0.1:
            calc_at_100k = a * (0.1 ** b)
            ratio_new = (supply_m / 0.1) * calc_at_100k + (1 - supply_m / 0.1) * 0.30
            return ratio_new
        return estimated_ratio
    
    def calculate_alpha_apy(self, emission_fraction: float, supply: float) -> Tuple[float, float, float]:
        daily_alpha = emission_fraction * self.TAO_PER_DAY * self.ALPHA_MULTIPLIER
        staked_ratio = self.estimate_staking_ratio(supply)
        staked_alpha = supply * staked_ratio
        if staked_alpha > 0:
            daily_yield = daily_alpha / staked_alpha
            apy = daily_yield * 365 * 100
        else:
            apy = 0.0
        return apy, staked_alpha, daily_alpha


def get_subnet_data() -> Dict[int, Dict]:
    """Fetch current subnet data for APY calculation."""
    logger.info("Fetching subnet data...")
    try:
        cmd = ['btcli', 'subnets', 'list', '--network', NETWORK, '--json-output']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            return {}
        cleaned = re.sub(r'\\n', ' ', result.stdout)
        cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)
        data = json.loads(cleaned)
        subnets = data.get('subnets', {})
        apy_model = AlphaAPYModel()
        subnet_data = {}
        for netuid_str, subnet_info in subnets.items():
            netuid = int(netuid_str)
            emission = subnet_info.get('emission', 0)
            supply = subnet_info.get('supply', 0)
            if supply > 0:
                apy, staked, daily_emissions = apy_model.calculate_alpha_apy(emission, supply)
                subnet_data[netuid] = {
                    'emission': emission,
                    'supply': supply,
                    'alpha_apy': apy,
                    'name': subnet_info.get('subnet_name', f'Subnet{netuid}')
                }
        logger.info(f"✓ Got data for {len(subnet_data)} subnets")
        return subnet_data
    except Exception as e:
        logger.error(f"Failed: {e}")
        return {}


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
    """Fetch alpha price at specific block using the official SDK method."""
    try:
        balance = subtensor.get_subnet_price(netuid=netuid, block=block)
        price_value = float(balance.tao)
        return price_value if price_value > 0 else None
    except Exception as e:
        logger.debug(f"Failed to fetch price for subnet {netuid} at block {block}: {e}")
        return None


def run_backtest(start_date: datetime, end_date: datetime):
    """Run extended backtest with multiple rebalancing periods."""
    logger.info("=" * 80)
    logger.info("TAO20 EXTENDED BACKTEST (Aug 4 - Oct 22, 2025)")
    logger.info("=" * 80)
    logger.info(f"Rebalancing dates: {len(REBALANCE_DATES)}")
    for date, _ in REBALANCE_DATES:
        logger.info(f"  - {date.strftime('%Y-%m-%d')}")
    logger.info("")
    
    # Get subnet data for APY
    subnet_data = get_subnet_data()
    if not subnet_data:
        logger.error("Failed to get subnet data")
        return
    
    # Get current block
    current_block = get_current_block()
    if current_block == 0:
        logger.error("Failed to get current block")
        return
    
    days_to_backtest = (end_date - start_date).days
    start_block = current_block - (days_to_backtest * BLOCKS_PER_DAY)
    
    logger.info(f"Backtesting {days_to_backtest} days")
    logger.info(f"Block range: {start_block} to {current_block}")
    logger.info("")
    
    # Connect to archive node
    import bittensor as bt
    logger.info(f"Connecting to archive node...")
    subtensor = bt.subtensor(network=NETWORK, archive_endpoints=[ARCHIVE_NODE])
    
    # Initialize
    nav = START_NAV
    price_only_nav = START_NAV
    weights = AUG_4_WEIGHTS.copy()
    
    # Get all unique subnet IDs across all periods
    all_netuids = set()
    for _, period_weights in REBALANCE_DATES:
        all_netuids.update(period_weights.keys())
    
    results = []
    logger.info(f"Fetching daily prices for {len(all_netuids)} unique subnets...")
    logger.info("")
    
    for day in range(days_to_backtest + 1):
        current_date = start_date + timedelta(days=day)
        current_block_num = start_block + (day * BLOCKS_PER_DAY)
        
        # Check if we need to rebalance
        for rebal_date, rebal_weights in REBALANCE_DATES:
            if current_date >= rebal_date and day > 0:
                # Only rebalance if we haven't already for this date
                prev_date = start_date + timedelta(days=day-1)
                if prev_date < rebal_date:
                    logger.info(f"🔄 REBALANCING on {current_date.strftime('%Y-%m-%d')}")
                    weights = rebal_weights.copy()
                    break
        
        # Fetch prices for this day
        day_prices = {}
        for netuid in all_netuids:
            price = fetch_price_at_block(netuid, current_block_num, subtensor)
            if price:
                day_prices[netuid] = price
        
        # Calculate returns
        price_return = 0.0
        apy_return = 0.0
        
        if day > 0:
            prev_prices = results[-1]['prices']
            for netuid, weight in weights.items():
                if netuid in day_prices and netuid in prev_prices:
                    if prev_prices[netuid] > 0 and day_prices[netuid] > 0:
                        price_change = (day_prices[netuid] - prev_prices[netuid]) / prev_prices[netuid]
                        price_return += weight * price_change
                if netuid in subnet_data:
                    daily_yield = (subnet_data[netuid]['alpha_apy'] / 100) / 365
                    apy_return += weight * daily_yield
        else:
            for netuid, weight in weights.items():
                if netuid in subnet_data:
                    daily_yield = (subnet_data[netuid]['alpha_apy'] / 100) / 365
                    apy_return += weight * daily_yield
        
        # Update NAV
        nav *= (1 + price_return + apy_return)
        price_only_nav *= (1 + price_return)
        
        results.append({
            'date': current_date,
            'nav': nav,
            'price_only_nav': price_only_nav,
            'price_return': price_return,
            'apy_return': apy_return,
            'total_return': price_return + apy_return,
            'prices': day_prices.copy()
        })
        
        if day % 10 == 0 or day < 3:
            logger.info(
                f"Day {day:3d} ({current_date.strftime('%Y-%m-%d')}): "
                f"NAV={nav:.4f}, Price Ret={price_return*100:+.2f}%, "
                f"APY Ret={apy_return*100:+.2f}%"
            )
    
    logger.info("")
    logger.info("✓ Backtest complete!")
    logger.info("")
    
    # Create DataFrame
    df = pd.DataFrame([{
        'date': r['date'],
        'nav': r['nav'],
        'price_only_nav': r['price_only_nav'],
        'price_return': r['price_return'],
        'apy_return': r['apy_return'],
        'total_return': r['total_return']
    } for r in results])
    
    # Statistics
    final_nav = df.iloc[-1]['nav']
    total_return = (final_nav - START_NAV) / START_NAV * 100
    total_price_return = (df.iloc[-1]['price_only_nav'] - START_NAV) / START_NAV * 100
    total_apy_contribution = total_return - total_price_return
    days_passed = len(df) - 1
    annualized = ((final_nav / START_NAV) ** (365 / days_passed) - 1) * 100 if days_passed > 0 else 0
    
    logger.info("=" * 80)
    logger.info("RESULTS")
    logger.info("=" * 80)
    logger.info(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} ({days_passed} days)")
    logger.info(f"Starting NAV: {START_NAV:.4f}")
    logger.info(f"Ending NAV: {final_nav:.4f}")
    logger.info(f"Price-Only NAV: {df.iloc[-1]['price_only_nav']:.4f}")
    logger.info("")
    logger.info(f"Total Return: {total_return:.2f}%")
    logger.info(f"  ├─ Price Return: {total_price_return:.2f}%")
    logger.info(f"  └─ APY Contribution: {total_apy_contribution:.2f}%")
    logger.info(f"Annualized Return: {annualized:.2f}%")
    logger.info("")
    
    # Save
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    os.makedirs('backtest_results', exist_ok=True)
    
    csv_file = f"backtest_results/tao20_extended_backtest_{timestamp}.csv"
    df.to_csv(csv_file, index=False)
    logger.info(f"✓ Saved: {csv_file}")
    
    # Plot
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(18, 14))
    
    # NAV plot
    ax1.plot(df['date'], df['nav'], 'b-', linewidth=2.5, label='Total NAV (Price + APY)')
    ax1.plot(df['date'], df['price_only_nav'], 'r--', linewidth=1.5, label='Price Only NAV')
    ax1.axhline(y=START_NAV, color='gray', linestyle=':', alpha=0.5, label='Starting NAV')
    
    # Mark all rebalancing dates
    for rebal_date, _ in REBALANCE_DATES[1:]:  # Skip first one
        if rebal_date <= end_date:
            ax1.axvline(x=rebal_date, color='green', alpha=0.3, linestyle='--', linewidth=1.5)
    
    ax1.set_xlabel('Date', fontsize=12)
    ax1.set_ylabel('NAV', fontsize=12)
    ax1.set_title('TAO20 Extended Backtest: Aug 4 - Oct 22, 2025 (Historical Weights)', fontsize=14, fontweight='bold')
    ax1.legend(loc='best')
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # Daily returns breakdown
    ax2.bar(df['date'], df['price_return']*100, color='coral', alpha=0.7, label='Price Return')
    ax2.bar(df['date'], df['apy_return']*100, bottom=df['price_return']*100, color='lightblue', alpha=0.7, label='APY Return')
    ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
    for rebal_date, _ in REBALANCE_DATES[1:]:
        if rebal_date <= end_date:
            ax2.axvline(x=rebal_date, color='green', alpha=0.2, linestyle='--', linewidth=1.5)
    ax2.set_xlabel('Date', fontsize=12)
    ax2.set_ylabel('Daily Return (%)', fontsize=12)
    ax2.set_title('Daily Returns Breakdown (Price vs APY)', fontsize=13, fontweight='bold')
    ax2.legend(loc='best')
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # Cumulative returns
    df['cumulative_price'] = ((df['price_only_nav'] / START_NAV) - 1) * 100
    df['cumulative_apy'] = ((df['nav'] / df['price_only_nav']) - 1) * 100
    
    ax3.fill_between(df['date'], 0, df['cumulative_price'], color='coral', alpha=0.5, label='Price Contribution')
    ax3.fill_between(df['date'], df['cumulative_price'], df['cumulative_price'] + df['cumulative_apy'], 
                     color='lightblue', alpha=0.5, label='APY Contribution')
    ax3.plot(df['date'], df['cumulative_price'] + df['cumulative_apy'], 'b-', linewidth=2, label='Total Return')
    ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
    for rebal_date, _ in REBALANCE_DATES[1:]:
        if rebal_date <= end_date:
            ax3.axvline(x=rebal_date, color='green', alpha=0.2, linestyle='--', linewidth=1.5)
    ax3.set_xlabel('Date', fontsize=12)
    ax3.set_ylabel('Cumulative Return (%)', fontsize=12)
    ax3.set_title('Cumulative Return Attribution', fontsize=13, fontweight='bold')
    ax3.legend(loc='best')
    ax3.grid(True, alpha=0.3)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    plt.tight_layout()
    
    plot_file = f"backtest_results/tao20_extended_backtest_{timestamp}.png"
    plt.savefig(plot_file, dpi=150, bbox_inches='tight')
    logger.info(f"✓ Plot saved: {plot_file}")
    logger.info("")
    
    # Open plot
    os.system(f"open {plot_file}")
    
    return df


if __name__ == '__main__':
    start = datetime(2025, 8, 4)
    end = datetime.now()
    
    run_backtest(start, end)












