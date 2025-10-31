#!/usr/bin/env python3
"""
TAO20 Dynamic APY Backtest
==========================
Backtests the TAO20 emission-weighted index with dynamic alpha staking APY.

Features:
- Fetches daily historical prices from archive node
- Uses btcli for emission data (SDK emission_value returns 0)
- Calculates alpha staking APY using calibrated power law model
- APY varies by subnet maturity (newer subnets have higher APY)
- Biweekly rebalancing based on emission weights
- Compounds NAV from both price returns and APY yields

Author: Alexander Lange
Date: October 22, 2025
"""

import os
import sys
import subprocess
import json
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np

# Import the APY model
from alpha_apy_model import AlphaAPYModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
NETWORK = 'finney'
ARCHIVE_NODE = 'wss://archive.chain.opentensor.ai:443'
BLOCKS_PER_DAY = 7200  # ~12 seconds per block
REBALANCE_DAYS = 14  # Biweekly rebalancing
START_NAV = 1.0

# Backtest period
BACKTEST_DAYS = 7  # Last 7 days for testing
END_DATE = datetime.now()
START_DATE = END_DATE - timedelta(days=BACKTEST_DAYS)


def get_current_block() -> int:
    """Get the current block number."""
    try:
        import bittensor as bt
        subtensor = bt.subtensor(network=NETWORK)
        return subtensor.get_current_block()
    except Exception as e:
        logger.error(f"Failed to get current block: {e}")
        return 0


def get_emissions_from_btcli() -> Dict[int, float]:
    """
    Fetch emissions using btcli --json-output.
    
    Returns:
        {netuid: emission_fraction}
    """
    logger.info("Fetching emissions from btcli...")
    
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
        
        emissions = {}
        for netuid_str, subnet_data in subnets.items():
            netuid = int(netuid_str)
            emission = subnet_data.get('emission', 0)
            if emission > 0:
                emissions[netuid] = emission
        
        logger.info(f"✓ Fetched emissions for {len(emissions)} subnets")
        return emissions
        
    except Exception as e:
        logger.error(f"Failed to fetch emissions: {e}")
        return {}


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
                'daily_emissions': daily_emissions
            }
            
            if emission > 0.01:  # Log significant subnets
                logger.info(
                    f"  Subnet {netuid}: emission={emission:.4f}, "
                    f"supply={supply:,.0f}, APY={apy:.1f}%, "
                    f"staked={staked/supply*100:.1f}%"
                )
        
        logger.info(f"✓ Calculated APY for {len(subnet_data)} subnets")
        return subnet_data
        
    except Exception as e:
        logger.error(f"Failed to get subnet data: {e}")
        return {}


def fetch_price_at_block(netuid: int, block: int) -> Optional[float]:
    """
    Fetch alpha token price at a specific block from archive node.
    
    Uses the bonding curve formula: Price = tau_reserves / alpha_reserves
    
    Args:
        netuid: Subnet UID
        block: Block number
    
    Returns:
        Price in TAO per alpha token, or None if unavailable
    """
    try:
        import bittensor as bt
        subtensor = bt.subtensor(network=NETWORK, _endpoint=ARCHIVE_NODE)
        
        # Get AlphaValues which contains [tau_in, alpha_in]
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
                
                # These are bonding curve ratio coefficients
                # Price = tau_in / alpha_in (direct ratio)
                if alpha_in > 0:
                    price = float(tau_in) / float(alpha_in)
                    return price
        
        return None
        
    except Exception as e:
        logger.debug(f"Failed to fetch price for subnet {netuid} at block {block}: {e}")
        return None


def build_price_history(
    subnet_data: Dict[int, Dict[str, float]],
    start_block: int,
    end_block: int
) -> pd.DataFrame:
    """
    Build daily price history for all subnets.
    
    Args:
        subnet_data: Subnet information including emissions
        start_block: Starting block number
        end_block: Ending block number
    
    Returns:
        DataFrame with columns: date, block, netuid, price
    """
    logger.info(f"Building price history from block {start_block} to {end_block}...")
    
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
        logger.info(f"  ✓ Day {day_idx + 1}: fetched {success_count}/{len(netuids)} prices in {day_duration:.1f}s ({completed}/{total_queries} total)")
    
    df = pd.DataFrame(price_data)
    
    if not df.empty:
        # Add date column
        df['date'] = df['block'].apply(
            lambda b: END_DATE - timedelta(days=(end_block - b) / BLOCKS_PER_DAY)
        )
        logger.info(f"✓ Built price history: {len(df)} data points across {len(blocks_to_sample)} days")
    else:
        logger.warning("No price data collected!")
    
    return df


def calculate_emission_weights(subnet_data: Dict[int, Dict[str, float]]) -> Dict[int, float]:
    """
    Calculate emission-based portfolio weights.
    
    Args:
        subnet_data: Subnet emission data
    
    Returns:
        {netuid: weight} where weights sum to 1.0
    """
    total_emission = sum(d['emission'] for d in subnet_data.values())
    
    if total_emission == 0:
        return {}
    
    weights = {
        netuid: data['emission'] / total_emission
        for netuid, data in subnet_data.items()
    }
    
    return weights


def run_backtest(
    price_df: pd.DataFrame,
    subnet_data: Dict[int, Dict[str, float]],
    weights: Dict[int, float]
) -> pd.DataFrame:
    """
    Run the backtest simulation.
    
    Args:
        price_df: Historical price data
        subnet_data: Subnet data including APY
        weights: Portfolio weights (emission-based)
    
    Returns:
        DataFrame with NAV history
    """
    logger.info("Running backtest simulation...")
    
    if price_df.empty:
        logger.error("No price data available for backtest")
        return pd.DataFrame()
    
    # Initialize
    nav = START_NAV
    price_only_nav = START_NAV
    
    results = []
    
    # Get unique dates sorted
    dates = sorted(price_df['date'].unique())
    
    # Track holdings
    holdings = {netuid: weight * nav for netuid, weight in weights.items()}
    
    for i, date in enumerate(dates):
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
            'total_return': price_return + apy_return
        })
        
        logger.debug(
            f"  Day {i}: NAV={nav:.4f}, "
            f"price_return={price_return*100:.2f}%, "
            f"apy_return={apy_return*100:.2f}%"
        )
    
    results_df = pd.DataFrame(results)
    logger.info(f"✓ Backtest complete: {len(results_df)} days simulated")
    
    return results_df


def main():
    """Main execution."""
    logger.info("=" * 80)
    logger.info("TAO20 DYNAMIC APY BACKTEST")
    logger.info("=" * 80)
    logger.info("")
    
    # Step 1: Get current subnet data and APY
    logger.info("[1/4] Fetching subnet data and calculating APY...")
    subnet_data = get_subnet_data_with_apy()
    
    if not subnet_data:
        logger.error("Failed to get subnet data. Exiting.")
        return
    
    logger.info(f"Loaded data for {len(subnet_data)} subnets")
    logger.info("")
    
    # Step 2: Calculate weights
    logger.info("[2/4] Calculating emission-based weights...")
    weights = calculate_emission_weights(subnet_data)
    logger.info(f"Portfolio contains {len(weights)} subnets")
    
    # Show top holdings
    sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)[:10]
    logger.info("Top 10 holdings:")
    for netuid, weight in sorted_weights:
        apy = subnet_data[netuid]['alpha_apy']
        logger.info(f"  Subnet {netuid}: {weight*100:.2f}% weight, {apy:.1f}% APY")
    logger.info("")
    
    # Step 3: Build price history
    logger.info("[3/4] Building price history...")
    current_block = get_current_block()
    
    if current_block == 0:
        logger.error("Failed to get current block. Exiting.")
        return
    
    start_block = current_block - (BACKTEST_DAYS * BLOCKS_PER_DAY)
    end_block = current_block
    
    logger.info(f"Fetching prices from block {start_block} to {end_block}")
    logger.info(f"Date range: {START_DATE.strftime('%Y-%m-%d')} to {END_DATE.strftime('%Y-%m-%d')}")
    
    price_df = build_price_history(subnet_data, start_block, end_block)
    
    if price_df.empty:
        logger.error("No price data available. Exiting.")
        return
    
    logger.info("")
    
    # Step 4: Run backtest
    logger.info("[4/4] Running backtest...")
    results_df = run_backtest(price_df, subnet_data, weights)
    
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
    logger.info("BACKTEST RESULTS")
    logger.info("=" * 80)
    logger.info(f"Period: {BACKTEST_DAYS} days")
    logger.info(f"Starting NAV: {START_NAV:.4f}")
    logger.info(f"Ending NAV: {final_nav:.4f}")
    logger.info(f"Total Return: {total_return:.2f}%")
    logger.info(f"  - Price Return: {price_return:.2f}%")
    logger.info(f"  - APY Contribution: {apy_contribution:.2f}%")
    logger.info(f"Price-Only NAV: {final_price_nav:.4f}")
    logger.info("")
    
    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"backtest_results/tao20_dynamic_apy_{timestamp}.csv"
    os.makedirs('backtest_results', exist_ok=True)
    
    results_df.to_csv(output_file, index=False)
    logger.info(f"✓ Results saved to: {output_file}")
    logger.info("")


if __name__ == '__main__':
    main()

