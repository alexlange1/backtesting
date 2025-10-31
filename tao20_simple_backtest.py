#!/usr/bin/env python3
"""
TAO20 Simplified Backtest - One Week Test
==========================================
Simplified version that:
- Uses current emissions/stake for APY (not historical)
- Focuses on price data fetching from archive
- Tests with just one week of data

This addresses issues with historical emissions/stake queries.
"""

import logging
import time
import subprocess
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from pathlib import Path

import bittensor as bt
import matplotlib.pyplot as plt
import pandas as pd

from config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Config.get_log_file('tao20_simple_backtest')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# Configuration - ONE WEEK TEST
# ============================================================================

# Test with last week only
START_DATE = datetime(2025, 10, 15)
END_DATE = datetime(2025, 10, 22)
TOTAL_DAYS = (END_DATE - START_DATE).days
DAILY_DATES = [START_DATE + timedelta(days=d) for d in range(TOTAL_DAYS + 1)]

NETWORK = 'finney'
ARCHIVE_NETWORK = 'archive'
TOP_N_SUBNETS = 20

logger.info(f"Testing period: {START_DATE.date()} to {END_DATE.date()} ({TOTAL_DAYS} days)")

# ============================================================================
# Core Functions
# ============================================================================

def ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime values are timezone-aware (UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def get_emissions_from_btcli() -> Dict[int, float]:
    """
    Fetch emissions using btcli with JSON output (SDK returns 0).
    
    Returns:
        {netuid: emission_value}
    """
    logger.info("Fetching emissions via btcli...")
    
    try:
        # Run btcli to get emissions in JSON format
        cmd = ['btcli', 'subnets', 'list', '--network', NETWORK, '--json-output']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            logger.error(f"btcli failed: {result.stderr}")
            return {}
        
        # Parse JSON output
        # Clean invalid control characters (btcli JSON contains literal newlines in strings)
        try:
            cleaned = re.sub(r'\\n', ' ', result.stdout)  # Replace escaped newlines
            cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)  # Remove control chars
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse btcli JSON: {e}")
            logger.debug(f"Output was: {result.stdout[:500]}")
            return {}
        
        emissions = {}
        
        # Parse the JSON structure
        # Format: {"subnets": {"0": {"netuid": 0, "emission": 0.0, ...}, "64": {...}, ...}}
        if isinstance(data, dict) and 'subnets' in data:
            subnets_dict = data['subnets']
            for netuid_str, subnet_data in subnets_dict.items():
                try:
                    netuid = int(netuid_str)
                    emission = float(subnet_data.get('emission', 0))
                    if emission > 0:
                        emissions[netuid] = emission
                except (ValueError, KeyError, TypeError):
                    continue
        else:
            # Fallback: try to parse as before
            if isinstance(data, list):
                for subnet in data:
                    try:
                        netuid = int(subnet.get('netuid', -1))
                        emission = float(subnet.get('emission', 0))
                        if emission > 0:
                            emissions[netuid] = emission
                    except (ValueError, KeyError, TypeError):
                        continue
            elif isinstance(data, dict):
                for key, subnet in data.items():
                    try:
                        if isinstance(subnet, dict):
                            netuid = int(subnet.get('netuid', key))
                            emission = float(subnet.get('emission', 0))
                            if emission > 0:
                                emissions[netuid] = emission
                    except (ValueError, KeyError, TypeError):
                        continue
        
        logger.info(f"✓ Parsed emissions for {len(emissions)} subnets via btcli")
        if len(emissions) > 0:
            sample = list(emissions.items())[:3]
            logger.info(f"  Sample: {sample}")
        else:
            logger.warning("No emissions found in btcli output")
            logger.debug(f"Data structure: {list(data.keys()) if isinstance(data, dict) else f'list of {len(data)} items'}")
        
        return emissions
        
    except Exception as e:
        logger.error(f"Failed to fetch emissions via btcli: {e}", exc_info=True)
        return {}


def estimate_staked_alpha_ratio(alpha_supply: float) -> float:
    """
    Estimate the percentage of alpha tokens staked based on supply (age proxy).
    
    Newer subnets (lower supply) tend to have lower absolute staked amounts
    but potentially higher staking participation rates.
    
    Args:
        alpha_supply: Total alpha token supply for the subnet
    
    Returns:
        Estimated fraction of tokens staked (0.0 to 1.0)
    """
    if alpha_supply < 500_000:
        return 0.10  # Very new subnets: 10% staked
    elif alpha_supply < 1_500_000:
        return 0.20  # Newer subnets: 20% staked
    elif alpha_supply < 2_500_000:
        return 0.35  # Medium age subnets: 35% staked
    else:
        return 0.55  # Older/established subnets: 55% staked


def get_current_emissions_and_alpha_data() -> Dict[int, Dict[str, float]]:
    """
    Fetch emissions and calculate alpha staking APY for all subnets.
    
    This calculates the APY for STAKING ALPHA TOKENS (not TAO validator rewards).
    The TAO20 index holds alpha tokens and earns staking rewards in alpha.
    
    Returns:
        {netuid: {'emission': float, 'alpha_supply': float, 'alpha_apy': float}}
    """
    logger.info("Fetching emissions and alpha data...")
    
    # Get emissions from btcli (which also has alpha supply data)
    emissions_map = get_emissions_from_btcli()
    
    if not emissions_map:
        logger.error("Failed to get emissions from btcli!")
        return {}
    
    # Also get full btcli data for alpha supply
    try:
        cmd = ['btcli', 'subnets', 'list', '--network', NETWORK, '--json-output']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            cleaned = re.sub(r'\\n', ' ', result.stdout)
            cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)
            btcli_data = json.loads(cleaned)
            subnets_data = btcli_data.get('subnets', {})
        else:
            logger.error("Failed to get btcli JSON data")
            return {}
            
    except Exception as e:
        logger.error(f"Failed to parse btcli data: {e}")
        return {}
    
    subnet_data = {}
    tao_per_day = 7200  # Network emits 7200 TAO/day (1 TAO/block)
    alpha_multiplier = 2  # Alpha emits at 2x TAO rate
    
    for netuid, emission_fraction in emissions_map.items():
        try:
            # Get alpha supply from btcli data
            subnet_info = subnets_data.get(str(netuid), {})
            alpha_supply = subnet_info.get('supply', 0)
            
            if alpha_supply == 0:
                logger.debug(f"  Skipping subnet {netuid}: no alpha supply data")
                continue
            
            # Calculate alpha emissions per day
            alpha_emissions_per_day = emission_fraction * tao_per_day * alpha_multiplier
            
            # Estimate staked alpha based on supply
            staked_ratio = estimate_staked_alpha_ratio(alpha_supply)
            staked_alpha = alpha_supply * staked_ratio
            
            # Calculate alpha staking APY
            if staked_alpha > 0:
                daily_yield = alpha_emissions_per_day / staked_alpha
                alpha_apy = daily_yield * 365 * 100
            else:
                alpha_apy = 0.0
            
            subnet_data[netuid] = {
                'emission': emission_fraction,
                'alpha_supply': alpha_supply,
                'staked_alpha': staked_alpha,
                'staked_ratio': staked_ratio,
                'alpha_apy': alpha_apy
            }
            
            if emission_fraction > 0:
                logger.info(
                    f"  Subnet {netuid}: emission={emission_fraction:.6f}, "
                    f"supply={alpha_supply:,.0f}, staked={staked_ratio*100:.0f}%, "
                    f"Alpha APY={alpha_apy:.2f}%"
                )
            
        except Exception as e:
            logger.debug(f"  Skipping subnet {netuid}: {e}")
            continue
    
    logger.info(f"✓ Calculated alpha APY for {len(subnet_data)} subnets")
    return subnet_data


def calculate_top_subnets(subnet_data: Dict[int, Dict], top_n: int) -> Dict[int, float]:
    """Select top N subnets by emission and return weights."""
    # Sort by emission
    sorted_subnets = sorted(
        [(netuid, data['emission']) for netuid, data in subnet_data.items()],
        key=lambda x: x[1],
        reverse=True
    )
    
    # Take top N
    top_subnets = sorted_subnets[:top_n]
    
    # Calculate weights
    total_emission = sum(emission for _, emission in top_subnets)
    if total_emission == 0:
        return {netuid: 1.0/top_n for netuid, _ in top_subnets}
    
    weights = {netuid: emission/total_emission for netuid, emission in top_subnets}
    return weights


class SimpleDailyPriceFetcher:
    """Simplified fetcher for daily prices only."""
    
    def __init__(self, daily_dates: List[datetime]):
        self.daily_dates = [ensure_utc(dt) for dt in daily_dates]
        logger.info(f"Connecting to archive node...")
        self.subtensor = bt.subtensor(network=ARCHIVE_NETWORK)
        self.current_block = self.subtensor.get_current_block()
        logger.info(f"✓ Connected. Current block: {self.current_block}")
        self.daily_blocks = self._compute_blocks()
    
    def _compute_blocks(self) -> List[int]:
        """Convert dates to block numbers using binary search."""
        logger.info(f"Computing blocks for {len(self.daily_dates)} days...")
        blocks = []
        
        for i, target_date in enumerate(self.daily_dates):
            # Binary search for block
            low, high = 1, self.current_block
            best_block = low
            
            while low <= high:
                mid = (low + high) // 2
                try:
                    mid_ts = self.subtensor.get_timestamp(mid)
                    if mid_ts <= target_date:
                        best_block = mid
                        low = mid + 1
                    else:
                        high = mid - 1
                except:
                    high = mid - 1
            
            blocks.append(best_block)
            if i == 0 or i == len(self.daily_dates) - 1:
                ts = self.subtensor.get_timestamp(best_block)
                logger.info(f"  Day {i}: {target_date.date()} -> block {best_block} ({ts.date()})")
        
        return blocks
    
    def fetch_prices(self, netuid: int) -> List[float]:
        """Fetch daily prices for a subnet."""
        prices = []
        logger.info(f"  Fetching {len(self.daily_blocks)} price points for subnet {netuid}")
        
        for block in self.daily_blocks:
            try:
                balance = self.subtensor.get_subnet_price(netuid=netuid, block=block)
                price = float(balance.tao)
                prices.append(price)
            except Exception as e:
                logger.debug(f"    Block {block}: price unavailable ({e})")
                prices.append(0.0)
        
        # Forward-fill zeros
        last_valid = 0.0
        for i, p in enumerate(prices):
            if p > 0:
                last_valid = p
            elif last_valid > 0:
                prices[i] = last_valid
        
        non_zero = sum(1 for p in prices if p > 0)
        logger.info(f"  ✓ Got {non_zero}/{len(prices)} valid prices")
        return prices


def calculate_nav_simple(
    subnet_weights: Dict[int, float],
    subnet_data: Dict[int, Dict],
    price_histories: Dict[int, List[float]]
) -> pd.DataFrame:
    """
    Calculate NAV with daily compounding of price + APY.
    Uses CURRENT APY values for all days (simplified assumption).
    """
    logger.info(f"\nCalculating NAV for {len(subnet_weights)} holdings...")
    
    num_days = len(DAILY_DATES)
    nav = 1.0
    price_only_nav = 1.0
    results = []
    
    for day in range(num_days):
        if day > 0:
            price_return = 0.0
            apy_return = 0.0
            
            for netuid, weight in subnet_weights.items():
                if netuid not in price_histories:
                    continue
                
                prices = price_histories[netuid]
                if day >= len(prices):
                    continue
                
                # Price return
                price_prev = prices[day - 1]
                price_now = prices[day]
                
                if price_prev > 0 and price_now > 0:
                    token_return = (price_now / price_prev) - 1
                    price_return += weight * token_return
                
                # Alpha staking APY return (daily)
                if netuid in subnet_data:
                    alpha_apy = subnet_data[netuid]['alpha_apy']
                    daily_yield = (alpha_apy / 100) / 365
                    apy_return += weight * daily_yield
            
            # Update NAVs
            nav *= (1 + price_return + apy_return)
            price_only_nav *= (1 + price_return)
            
            logger.info(
                f"Day {day} ({DAILY_DATES[day].date()}): "
                f"Price={price_return*100:+.3f}%, APY={apy_return*100:+.3f}%, "
                f"NAV={nav:.6f}"
            )
        
        results.append({
            'day': day,
            'date': DAILY_DATES[day],
            'nav': nav,
            'price_only_nav': price_only_nav,
            'apy_contribution': nav - price_only_nav
        })
    
    return pd.DataFrame(results)


# ============================================================================
# Main
# ============================================================================

def main():
    try:
        logger.info("=" * 80)
        logger.info("TAO20 SIMPLIFIED ONE-WEEK BACKTEST")
        logger.info("=" * 80)
        logger.info(f"Period: {START_DATE.date()} to {END_DATE.date()}")
        logger.info(f"Duration: {TOTAL_DAYS} days")
        logger.info("")
        
        # Step 1: Get current emissions and alpha staking APY
        logger.info("STEP 1: Fetching Emissions & Alpha Staking APY")
        logger.info("-" * 80)
        subnet_data = get_current_emissions_and_alpha_data()
        
        if len(subnet_data) < 5:
            logger.error("Insufficient subnet data!")
            return 1
        
        logger.info(f"\n✓ Got data for {len(subnet_data)} subnets")
        
        # Step 2: Select top 20
        logger.info("\nSTEP 2: Selecting Top 20 Subnets by Emission")
        logger.info("-" * 80)
        subnet_weights = calculate_top_subnets(subnet_data, TOP_N_SUBNETS)
        
        logger.info(f"Top {TOP_N_SUBNETS} subnets:")
        for i, (netuid, weight) in enumerate(sorted(subnet_weights.items(), key=lambda x: x[1], reverse=True)[:10], 1):
            alpha_apy = subnet_data[netuid]['alpha_apy']
            logger.info(f"  {i}. Subnet {netuid}: {weight*100:.2f}% weight, {alpha_apy:.2f}% Alpha APY")
        
        # Step 3: Fetch historical prices
        logger.info("\nSTEP 3: Fetching Daily Prices from Archive")
        logger.info("-" * 80)
        price_fetcher = SimpleDailyPriceFetcher(DAILY_DATES)
        
        price_histories = {}
        for i, netuid in enumerate(subnet_weights.keys(), 1):
            logger.info(f"[{i}/{len(subnet_weights)}] Subnet {netuid}")
            prices = price_fetcher.fetch_prices(netuid)
            
            if sum(1 for p in prices if p > 0) >= 2:
                price_histories[netuid] = prices
            else:
                logger.warning(f"  ✗ Insufficient price data for subnet {netuid}")
        
        logger.info(f"\n✓ Got prices for {len(price_histories)}/{len(subnet_weights)} subnets")
        
        # Step 4: Calculate NAV
        logger.info("\nSTEP 4: Calculating NAV with APY")
        logger.info("-" * 80)
        nav_df = calculate_nav_simple(subnet_weights, subnet_data, price_histories)
        
        # Step 5: Save results
        logger.info("\nSTEP 5: Saving Results")
        logger.info("-" * 80)
        
        csv_path = Config.RESULTS_DIR / f'tao20_simple_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        nav_df.to_csv(csv_path, index=False)
        logger.info(f"✓ Saved: {csv_path}")
        
        # Step 6: Summary
        logger.info("\n" + "=" * 80)
        logger.info("RESULTS SUMMARY")
        logger.info("=" * 80)
        
        final_nav = nav_df['nav'].iloc[-1]
        final_price_nav = nav_df['price_only_nav'].iloc[-1]
        final_apy_contrib = final_nav - final_price_nav
        
        logger.info(f"Period: {START_DATE.date()} to {END_DATE.date()} ({TOTAL_DAYS} days)")
        logger.info(f"Holdings: {len(price_histories)} subnets")
        logger.info("")
        logger.info(f"Final NAV: {final_nav:.6f}")
        logger.info(f"  - Price-Only NAV: {final_price_nav:.6f}")
        logger.info(f"  - APY Contribution: {final_apy_contrib:.6f}")
        logger.info("")
        logger.info(f"Total Return: {(final_nav - 1) * 100:+.2f}%")
        logger.info(f"  - Price Return: {(final_price_nav - 1) * 100:+.2f}%")
        logger.info(f"  - APY Return: {final_apy_contrib * 100:+.2f}%")
        logger.info("")
        logger.info("=" * 80)
        logger.info("✓ BACKTEST COMPLETE!")
        logger.info("=" * 80)
        
        return 0
        
    except Exception as e:
        logger.error(f"Backtest failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())

