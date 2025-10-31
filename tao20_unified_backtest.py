#!/usr/bin/env python3
"""
TAO20 Unified Backtest System
==============================
Complete TAO20 emission-weighted index backtest with dynamic alpha staking APY.

Features:
- Integrated alpha APY model with power law calibration
- Fast simulation mode (30 seconds)
- Full historical mode with archive node price data
- Multiple scenario analysis
- Emission-based portfolio weighting
- Biweekly rebalancing

Author: Alexander Lange
Date: October 22, 2025
"""

import os
import sys
import subprocess
import json
import re
import math
import logging
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

NETWORK = 'finney'
ARCHIVE_NODE = 'wss://archive.chain.opentensor.ai:443'
BLOCKS_PER_DAY = 7200  # ~12 seconds per block
REBALANCE_DAYS = 14  # Biweekly rebalancing
START_NAV = 1.0

# Default backtest parameters
DEFAULT_BACKTEST_DAYS = 30
DEFAULT_MODE = 'simple'  # 'simple' or 'historical'


# ============================================================================
# ALPHA APY MODEL
# ============================================================================

class AlphaAPYModel:
    """
    Model for estimating alpha token staking APY based on subnet characteristics.
    
    The model estimates staking participation rate, which inversely affects APY.
    Newer subnets (lower supply) have lower participation → higher APY.
    """
    
    # Network constants
    TAO_PER_DAY = 7200  # Network emits 7200 TAO/day
    ALPHA_MULTIPLIER = 2  # Alpha emits at 2x TAO rate
    
    # Calibration data (current as of Oct 2025)
    CALIBRATION_POINTS = {
        64: {'supply': 3_166_000, 'apy': 70.0},    # Chutes
        120: {'supply': 1_129_000, 'apy': 135.0},  # Affine
    }
    
    def __init__(self):
        """Initialize the model."""
        pass
    
    def estimate_staking_ratio(self, supply: float) -> float:
        """
        Estimate the percentage of alpha tokens staked based on supply (maturity proxy).
        
        Model: Power law decay calibrated to known data points.
        Key insight: Staking ratio DECREASES as supply grows (inflation outpaces staking).
        
        Calibration points:
        - Subnet 120 (1.129M supply) → 20.66% staked → 135% APY
        - Subnet 64 (3.166M supply) → 18.38% staked → 70% APY
        
        Args:
            supply: Total alpha token supply for the subnet
        
        Returns:
            Estimated fraction of tokens staked (0.0 to 1.0)
        """
        if supply <= 0:
            return 0.15  # Default for invalid data
        
        # Calibration data (supply in millions, ratio as decimal)
        s1, r1 = 1.129, 0.2066  # Subnet 120
        s2, r2 = 3.166, 0.1838  # Subnet 64
        
        supply_m = supply / 1_000_000
        
        # Power law: ratio = a * supply^b
        b = math.log(r2 / r1) / math.log(s2 / s1)
        a = r1 / (s1 ** b)
        
        # Apply power law
        estimated_ratio = a * (supply_m ** b)
        
        # Clamp to reasonable bounds (5% to 40%)
        estimated_ratio = max(0.05, min(0.40, estimated_ratio))
        
        # Special handling for very new subnets (< 100k supply)
        if supply_m < 0.1:
            calc_at_100k = a * (0.1 ** b)
            ratio_new = (supply_m / 0.1) * calc_at_100k + (1 - supply_m / 0.1) * 0.30
            return ratio_new
        
        return estimated_ratio
    
    def calculate_alpha_apy(
        self,
        emission_fraction: float,
        supply: float,
        override_staked_ratio: float = None
    ) -> Tuple[float, float, float]:
        """
        Calculate alpha staking APY for a subnet.
        
        Args:
            emission_fraction: Subnet's share of network emissions (0-1)
            supply: Total alpha token supply
            override_staked_ratio: Optional manual staking ratio (for testing)
        
        Returns:
            Tuple of (apy, estimated_staked_alpha, daily_emissions)
        """
        # Calculate daily alpha emissions
        daily_alpha = emission_fraction * self.TAO_PER_DAY * self.ALPHA_MULTIPLIER
        
        # Estimate staked amount
        if override_staked_ratio is not None:
            staked_ratio = override_staked_ratio
        else:
            staked_ratio = self.estimate_staking_ratio(supply)
        
        staked_alpha = supply * staked_ratio
        
        # Calculate APY
        if staked_alpha > 0:
            daily_yield = daily_alpha / staked_alpha
            apy = daily_yield * 365 * 100
        else:
            apy = 0.0
        
        return apy, staked_alpha, daily_alpha
    
    def validate_model(self) -> Dict[int, Dict[str, float]]:
        """
        Validate the model against known calibration points.
        
        Returns:
            Dictionary of validation results for each calibration subnet
        """
        results = {}
        
        for netuid, data in self.CALIBRATION_POINTS.items():
            supply = data['supply']
            target_apy = data['apy']
            
            # Emission fractions from calibration
            if netuid == 64:
                emission_fraction = 0.0775
            elif netuid == 120:
                emission_fraction = 0.0599
            else:
                emission_fraction = 0.05  # Default
            
            apy, staked, daily = self.calculate_alpha_apy(emission_fraction, supply)
            
            error = abs(apy - target_apy)
            error_pct = (error / target_apy) * 100
            
            results[netuid] = {
                'supply': supply,
                'target_apy': target_apy,
                'calculated_apy': apy,
                'error': error,
                'error_pct': error_pct,
                'staked_alpha': staked,
                'staked_ratio': staked / supply,
                'daily_emissions': daily
            }
        
        return results


# ============================================================================
# DATA FETCHING
# ============================================================================

def get_subnet_data_with_apy() -> Dict[int, Dict[str, float]]:
    """
    Fetch emissions, supply, and calculate alpha staking APY for all subnets.
    
    Returns:
        {netuid: {
            'emission': float,
            'supply': float,
            'alpha_apy': float,
            'staked_alpha': float,
            'staked_ratio': float
        }}
    """
    logger.info("Fetching subnet data and calculating APY...")
    
    try:
        cmd = ['btcli', 'subnets', 'list', '--network', NETWORK, '--json-output']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            logger.error(f"btcli failed: {result.stderr}")
            return {}
        
        # Clean invalid control characters from JSON
        cleaned = re.sub(r'\\n', ' ', result.stdout)
        cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)
        
        data = json.loads(cleaned)
        subnets = data.get('subnets', {})
        
        # Initialize APY model
        apy_model = AlphaAPYModel()
        
        subnet_data = {}
        
        for netuid_str, subnet_info in subnets.items():
            netuid = int(netuid_str)
            emission = subnet_info.get('emission', 0)
            supply = subnet_info.get('supply', 0)
            
            if emission <= 0 or supply <= 0:
                continue
            
            # Calculate APY using the model
            apy, staked, daily_emissions = apy_model.calculate_alpha_apy(emission, supply)
            
            subnet_data[netuid] = {
                'emission': emission,
                'supply': supply,
                'alpha_apy': apy,
                'staked_alpha': staked,
                'staked_ratio': staked / supply,
                'daily_emissions': daily_emissions,
                'name': subnet_info.get('subnet_name', f'Subnet{netuid}')
            }
        
        logger.info(f"✓ Calculated APY for {len(subnet_data)} subnets")
        return subnet_data
        
    except Exception as e:
        logger.error(f"Failed to get subnet data: {e}")
        return {}


def get_current_block() -> int:
    """Get the current block number."""
    try:
        import bittensor as bt
        subtensor = bt.subtensor(network=NETWORK)
        return subtensor.get_current_block()
    except Exception as e:
        logger.error(f"Failed to get current block: {e}")
        return 0


def fetch_historical_prices(
    subnet_data: Dict[int, Dict[str, float]],
    start_block: int,
    end_block: int
) -> pd.DataFrame:
    """
    Fetch historical prices from archive node.
    
    Args:
        subnet_data: Subnet information
        start_block: Starting block number
        end_block: Ending block number
    
    Returns:
        DataFrame with columns: date, block, netuid, price
    """
    logger.info(f"Fetching historical prices from block {start_block} to {end_block}...")
    
    # Create a persistent subtensor connection for the archive node
    import bittensor as bt
    logger.info(f"Connecting to archive node: {ARCHIVE_NODE}")
    subtensor = bt.subtensor(network=NETWORK, archive_endpoints=[ARCHIVE_NODE])
    
    price_data = []
    netuids = list(subnet_data.keys())
    
    # Calculate blocks to sample
    blocks_to_sample = []
    current_block = start_block
    while current_block <= end_block:
        blocks_to_sample.append(current_block)
        current_block += BLOCKS_PER_DAY
    
    total_queries = len(blocks_to_sample) * len(netuids)
    logger.info(f"Will fetch {total_queries} price points ({len(blocks_to_sample)} days × {len(netuids)} subnets)")
    
    completed = 0
    
    for day_idx, block in enumerate(blocks_to_sample):
        logger.info(f"Fetching prices for day {day_idx + 1}/{len(blocks_to_sample)} (block {block})...")
        
        day_start_time = datetime.now()
        success_count = 0
        
        for netuid in netuids:
            try:
                # Get AlphaValues at this block
                alpha_values = subtensor.substrate.query(
                    module='SubtensorModule',
                    storage_function='AlphaValues',
                    params=[netuid],
                    block_hash=subtensor.substrate.get_block_hash(block)
                )
                
                if alpha_values and hasattr(alpha_values, 'value'):
                    reserves = alpha_values.value
                    if isinstance(reserves, (list, tuple)) and len(reserves) == 2:
                        tau_in, alpha_in = reserves
                        
                        if alpha_in > 0:
                            price = float(tau_in) / float(alpha_in)
                            price_data.append({
                                'block': block,
                                'netuid': netuid,
                                'price': price
                            })
                            success_count += 1
                
                completed += 1
                
            except Exception as e:
                logger.debug(f"Failed to fetch price for subnet {netuid} at block {block}: {e}")
                completed += 1
                continue
        
        day_duration = (datetime.now() - day_start_time).total_seconds()
        logger.info(f"  ✓ Day {day_idx + 1}: fetched {success_count}/{len(netuids)} prices in {day_duration:.1f}s")
    
    df = pd.DataFrame(price_data)
    
    if not df.empty:
        # Add date column
        end_date = datetime.now()
        df['date'] = df['block'].apply(
            lambda b: end_date - timedelta(days=(end_block - b) / BLOCKS_PER_DAY)
        )
        logger.info(f"✓ Built price history: {len(df)} data points across {len(blocks_to_sample)} days")
    else:
        logger.warning("No price data collected!")
    
    return df


# ============================================================================
# BACKTEST LOGIC
# ============================================================================

def calculate_emission_weights(subnet_data: Dict[int, Dict[str, float]], top_n: int = None) -> Dict[int, float]:
    """
    Calculate emission-based portfolio weights.
    
    Args:
        subnet_data: Subnet emission data
        top_n: If provided, only include top N subnets by emission
    
    Returns:
        {netuid: weight} where weights sum to 1.0
    """
    # Filter to top N if specified
    if top_n:
        sorted_subnets = sorted(
            subnet_data.items(),
            key=lambda x: x[1]['emission'],
            reverse=True
        )[:top_n]
        subnet_data = dict(sorted_subnets)
        logger.info(f"Selected top {top_n} subnets by emission")
    
    total_emission = sum(d['emission'] for d in subnet_data.values())
    
    if total_emission == 0:
        return {}
    
    weights = {
        netuid: data['emission'] / total_emission
        for netuid, data in subnet_data.items()
    }
    
    return weights


def run_simplified_backtest(
    subnet_data: Dict[int, Dict[str, float]],
    days: int,
    assume_price_change: float = 0.0
) -> pd.DataFrame:
    """
    Run simplified backtest with APY compounding (no historical prices).
    
    Args:
        subnet_data: Subnet data with APY
        days: Number of days to simulate
        assume_price_change: Daily price change assumption (e.g., 0.01 = 1% per day)
    
    Returns:
        DataFrame with daily NAV history
    """
    logger.info(f"Running simplified backtest for {days} days...")
    
    # Calculate emission weights
    weights = calculate_emission_weights(subnet_data)
    
    # Initialize NAVs
    nav = START_NAV
    price_only_nav = START_NAV
    apy_only_nav = START_NAV
    
    results = []
    
    for day in range(days):
        # Calculate weighted APY
        weighted_apy = sum(
            weights[netuid] * data['alpha_apy']
            for netuid, data in subnet_data.items()
        )
        
        # Daily returns
        daily_apy_yield = (weighted_apy / 100) / 365
        daily_price_return = assume_price_change
        
        # Update NAVs
        nav *= (1 + daily_price_return + daily_apy_yield)
        price_only_nav *= (1 + daily_price_return)
        apy_only_nav *= (1 + daily_apy_yield)
        
        date = datetime.now() - timedelta(days=days - day - 1)
        
        results.append({
            'day': day + 1,
            'date': date,
            'nav': nav,
            'price_only_nav': price_only_nav,
            'apy_only_nav': apy_only_nav,
            'weighted_apy': weighted_apy,
            'daily_apy_yield': daily_apy_yield,
            'daily_price_return': daily_price_return
        })
    
    df = pd.DataFrame(results)
    logger.info(f"✓ Simulation complete")
    
    return df


def run_historical_backtest(
    price_df: pd.DataFrame,
    subnet_data: Dict[int, Dict[str, float]],
    initial_weights: Dict[int, float],
    rebalance_days: int = 14
) -> pd.DataFrame:
    """
    Run backtest using historical price data with periodic rebalancing.
    
    Args:
        price_df: Historical price data
        subnet_data: Subnet data including APY
        initial_weights: Initial portfolio weights (emission-based)
        rebalance_days: Days between rebalancing (default 14 for biweekly)
    
    Returns:
        DataFrame with NAV history
    """
    logger.info(f"Running historical backtest with {rebalance_days}-day rebalancing...")
    
    if price_df.empty:
        logger.error("No price data available for backtest")
        return pd.DataFrame()
    
    # Initialize
    nav = START_NAV
    price_only_nav = START_NAV
    weights = initial_weights.copy()
    
    results = []
    
    # Get unique dates sorted
    dates = sorted(price_df['date'].unique())
    last_rebalance_day = 0
    
    for i, date in enumerate(dates):
        # Rebalance if it's time
        if i > 0 and i % rebalance_days == 0:
            # Rebalance back to emission weights
            weights = initial_weights.copy()
            logger.info(f"  🔄 Rebalancing on day {i} ({date.strftime('%Y-%m-%d')})")
            last_rebalance_day = i
        
        # Get prices for this date
        day_prices = price_df[price_df['date'] == date].set_index('netuid')['price'].to_dict()
        
        # Calculate returns
        price_return = 0.0
        apy_return = 0.0
        
        for netuid, weight in weights.items():
            if netuid not in day_prices:
                continue
            
            # Price return (only if we have previous price)
            if i > 0:
                prev_day_prices = price_df[price_df['date'] == dates[i-1]].set_index('netuid')['price'].to_dict()
                if netuid in prev_day_prices and prev_day_prices[netuid] > 0:
                    price_change = (day_prices[netuid] - prev_day_prices[netuid]) / prev_day_prices[netuid]
                    price_return += weight * price_change
            
            # APY return (daily)
            if netuid in subnet_data:
                alpha_apy = subnet_data[netuid]['alpha_apy']
                daily_yield = (alpha_apy / 100) / 365
                apy_return += weight * daily_yield
        
        # Update NAVs
        nav *= (1 + price_return + apy_return)
        price_only_nav *= (1 + price_return)
        
        results.append({
            'date': date,
            'nav': nav,
            'price_only_nav': price_only_nav,
            'price_return': price_return,
            'apy_return': apy_return,
            'total_return': price_return + apy_return,
            'days_since_rebalance': i - last_rebalance_day
        })
        
        logger.debug(
            f"  Day {i}: NAV={nav:.4f}, "
            f"price_return={price_return*100:.2f}%, "
            f"apy_return={apy_return*100:.2f}%"
        )
    
    results_df = pd.DataFrame(results)
    logger.info(f"✓ Backtest complete: {len(results_df)} days simulated")
    
    return results_df


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def print_portfolio_summary(subnet_data: Dict[int, Dict[str, float]], weights: Dict[int, float]):
    """Print portfolio summary with top holdings."""
    # Calculate portfolio-weighted APY
    weighted_apy = sum(
        weights[netuid] * data['alpha_apy']
        for netuid, data in subnet_data.items()
    )
    
    logger.info(f"Portfolio contains {len(weights)} subnets")
    logger.info(f"Portfolio-weighted APY: {weighted_apy:.2f}%")
    logger.info("")
    
    # Show top holdings
    sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)[:10]
    logger.info("Top 10 holdings:")
    for netuid, weight in sorted_weights:
        apy = subnet_data[netuid]['alpha_apy']
        name = subnet_data[netuid]['name']
        logger.info(f"  Subnet {netuid:3d} ({name:20s}): {weight*100:5.2f}% weight, {apy:6.1f}% APY")
    logger.info("")


def save_results(results_df: pd.DataFrame, mode: str, scenario: str = None) -> str:
    """Save results to CSV file."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    os.makedirs('backtest_results', exist_ok=True)
    
    if scenario:
        filename = f"tao20_{mode}_{scenario}_{timestamp}.csv"
    else:
        filename = f"tao20_{mode}_{timestamp}.csv"
    
    output_file = f"backtest_results/{filename}"
    results_df.to_csv(output_file, index=False)
    
    return output_file


def main():
    """Main execution."""
    parser = argparse.ArgumentParser(
        description='TAO20 Unified Backtest System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run simplified backtest (fast, 30 days)
  python tao20_unified_backtest.py --mode simple --days 30
  
  # Run historical backtest (slow, 7 days)
  python tao20_unified_backtest.py --mode historical --days 7
  
  # Validate APY model
  python tao20_unified_backtest.py --validate
        """
    )
    
    parser.add_argument(
        '--mode',
        choices=['simple', 'historical'],
        default=DEFAULT_MODE,
        help='Backtest mode: simple (fast) or historical (slow, uses archive node)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=DEFAULT_BACKTEST_DAYS,
        help='Number of days to backtest'
    )
    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate APY model and exit'
    )
    parser.add_argument(
        '--top',
        type=int,
        default=20,
        help='Number of top subnets to include (default: 20 for TAO20)'
    )
    parser.add_argument(
        '--rebalance-days',
        type=int,
        default=14,
        help='Days between rebalancing (default: 14 for biweekly)'
    )
    parser.add_argument(
        '--plot',
        action='store_true',
        help='Generate NAV plot (requires matplotlib)'
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("TAO20 UNIFIED BACKTEST SYSTEM")
    logger.info("=" * 80)
    logger.info("")
    
    # Validate APY model if requested
    if args.validate:
        logger.info("Validating APY model...")
        logger.info("")
        
        apy_model = AlphaAPYModel()
        validation = apy_model.validate_model()
        
        for netuid, results in validation.items():
            logger.info(f"Subnet {netuid} Validation:")
            logger.info(f"  Supply: {results['supply']:,.0f} alpha")
            logger.info(f"  Target APY: {results['target_apy']:.1f}%")
            logger.info(f"  Calculated APY: {results['calculated_apy']:.1f}%")
            logger.info(f"  Error: {results['error']:.1f}% ({results['error_pct']:.1f}% relative)")
            logger.info(f"  Staked: {results['staked_alpha']:,.0f} ({results['staked_ratio']*100:.1f}% of supply)")
            status = "✓ PASS" if results['error_pct'] < 5 else "✗ NEEDS CALIBRATION"
            logger.info(f"  Status: {status}")
            logger.info("")
        
        return
    
    # Step 1: Get subnet data
    logger.info(f"[1/3] Fetching subnet data and calculating APY...")
    subnet_data = get_subnet_data_with_apy()
    
    if not subnet_data:
        logger.error("Failed to get subnet data. Exiting.")
        return
    
    logger.info(f"Loaded data for {len(subnet_data)} subnets")
    logger.info("")
    
    # Step 2: Calculate weights and show portfolio
    logger.info(f"[2/3] Calculating emission-based weights...")
    weights = calculate_emission_weights(subnet_data, top_n=args.top)
    
    # Filter subnet_data to only include selected subnets
    subnet_data = {k: v for k, v in subnet_data.items() if k in weights}
    
    print_portfolio_summary(subnet_data, weights)
    
    # Step 3: Run backtest based on mode
    if args.mode == 'simple':
        logger.info(f"[3/3] Running simplified backtest ({args.days} days)...")
        logger.info("")
        
        scenarios = [
            ("apy_only", 0.0),
            ("bearish", -0.01),
            ("bullish", 0.01),
        ]
        
        all_results = {}
        
        for scenario_name, price_change in scenarios:
            logger.info(f"Scenario: {scenario_name} ({price_change*100:+.0f}% daily price change)")
            results_df = run_simplified_backtest(subnet_data, args.days, price_change)
            
            final_nav = results_df.iloc[-1]['nav']
            total_return = (final_nav - START_NAV) / START_NAV * 100
            annualized_return = ((final_nav / START_NAV) ** (365 / args.days) - 1) * 100
            
            logger.info(f"  Final NAV: {final_nav:.4f}")
            logger.info(f"  Total Return ({args.days} days): {total_return:.2f}%")
            logger.info(f"  Annualized Return: {annualized_return:.2f}%")
            
            # Save results
            output_file = save_results(results_df, 'simple', scenario_name)
            logger.info(f"  ✓ Saved: {output_file}")
            logger.info("")
            
            all_results[scenario_name] = results_df
        
        # Create summary
        summary_data = []
        for scenario_name, df in all_results.items():
            final = df.iloc[-1]
            summary_data.append({
                'scenario': scenario_name,
                'final_nav': final['nav'],
                'total_return_pct': (final['nav'] - START_NAV) / START_NAV * 100,
                'annualized_return_pct': ((final['nav'] / START_NAV) ** (365 / args.days) - 1) * 100,
                'apy_contribution': (final['apy_only_nav'] - START_NAV) / START_NAV * 100
            })
        
        summary_df = pd.DataFrame(summary_data)
        summary_file = save_results(summary_df, 'simple', 'summary')
        logger.info(f"✓ Summary saved: {summary_file}")
        logger.info("")
        
    else:  # historical mode
        logger.info(f"[3/3] Running historical backtest ({args.days} days)...")
        logger.info("")
        
        # Get current block and calculate date range
        current_block = get_current_block()
        if current_block == 0:
            logger.error("Failed to get current block. Exiting.")
            return
        
        start_block = current_block - (args.days * BLOCKS_PER_DAY)
        end_block = current_block
        
        start_date = datetime.now() - timedelta(days=args.days)
        end_date = datetime.now()
        
        logger.info(f"Block range: {start_block} to {end_block}")
        logger.info(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        logger.info("")
        
        # Fetch historical prices
        price_df = fetch_historical_prices(subnet_data, start_block, end_block)
        
        if price_df.empty:
            logger.error("No price data available. Exiting.")
            return
        
        # Run backtest with rebalancing
        results_df = run_historical_backtest(price_df, subnet_data, weights, args.rebalance_days)
        
        if results_df.empty:
            logger.error("Backtest failed. Exiting.")
            return
        
        # Calculate statistics
        final_nav = results_df.iloc[-1]['nav']
        final_price_nav = results_df.iloc[-1]['price_only_nav']
        total_return = (final_nav - START_NAV) / START_NAV * 100
        price_return = (final_price_nav - START_NAV) / START_NAV * 100
        apy_contribution = total_return - price_return
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("RESULTS")
        logger.info("=" * 80)
        logger.info(f"Period: {args.days} days")
        logger.info(f"Starting NAV: {START_NAV:.4f}")
        logger.info(f"Ending NAV: {final_nav:.4f}")
        logger.info(f"Total Return: {total_return:.2f}%")
        logger.info(f"  - Price Return: {price_return:.2f}%")
        logger.info(f"  - APY Contribution: {apy_contribution:.2f}%")
        logger.info(f"Price-Only NAV: {final_price_nav:.4f}")
        logger.info("")
        
        # Save results
        output_file = save_results(results_df, 'historical')
        logger.info(f"✓ Results saved to: {output_file}")
        logger.info("")
        
        # Plot if requested
        if args.plot:
            try:
                import matplotlib.pyplot as plt
                import matplotlib.dates as mdates
                
                fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
                
                # Plot 1: NAV over time
                ax1.plot(results_df['date'], results_df['nav'], 'b-', linewidth=2, label='Total NAV (Price + APY)')
                ax1.plot(results_df['date'], results_df['price_only_nav'], 'r--', linewidth=1.5, label='Price Only NAV')
                ax1.axhline(y=START_NAV, color='gray', linestyle=':', alpha=0.5, label='Starting NAV')
                
                # Mark rebalancing dates
                rebalance_dates = results_df[results_df['days_since_rebalance'] == 0]['date']
                for rb_date in rebalance_dates:
                    ax1.axvline(x=rb_date, color='green', alpha=0.3, linestyle='--', linewidth=1)
                
                ax1.set_xlabel('Date', fontsize=12)
                ax1.set_ylabel('NAV', fontsize=12)
                ax1.set_title(f'TAO20 Index Performance (Top {args.top} Subnets, Biweekly Rebalancing)', fontsize=14, fontweight='bold')
                ax1.legend(loc='best')
                ax1.grid(True, alpha=0.3)
                ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
                
                # Plot 2: Daily returns
                ax2.bar(results_df['date'], results_df['total_return']*100, color='steelblue', alpha=0.7, label='Total Return')
                ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
                ax2.set_xlabel('Date', fontsize=12)
                ax2.set_ylabel('Daily Return (%)', fontsize=12)
                ax2.set_title('Daily Returns', fontsize=12, fontweight='bold')
                ax2.legend(loc='best')
                ax2.grid(True, alpha=0.3)
                ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
                
                plt.tight_layout()
                
                # Save plot
                plot_file = output_file.replace('.csv', '.png')
                plt.savefig(plot_file, dpi=150, bbox_inches='tight')
                logger.info(f"✓ Plot saved to: {plot_file}")
                logger.info("")
                
                # Also display if in interactive mode
                # plt.show()
                
            except ImportError:
                logger.warning("matplotlib not installed. Install with: pip install matplotlib")
            except Exception as e:
                logger.error(f"Failed to create plot: {e}")
    
    logger.info("=" * 80)
    logger.info("✓ BACKTEST COMPLETE")
    logger.info("=" * 80)


if __name__ == '__main__':
    main()
