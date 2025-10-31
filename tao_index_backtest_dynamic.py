#!/usr/bin/env python3
"""
TAO Index Backtest - Dynamic Rebalancing (Production)
======================================================
Backtests TAO20, TAO15, and TAO10 indices with bi-weekly rebalancing
based on emission-weighted allocations using Bittensor SDK.

Key Features:
- Dynamic rebalancing every 2 weeks
- Emission-based weighting (proportional to subnet emissions)
- NAV calculation starting at 1.0 (continuous through rebalances)
- Real historical price data from Bittensor archive node
- Production-ready with error handling and retry logic
- Uses Bittensor SDK (not btcli subprocess calls)

Author: Alexander Lange
Date: October 22, 2025
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from pathlib import Path

import bittensor as bt
import matplotlib.pyplot as plt
import pandas as pd

from config import Config

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format=Config.LOG_FORMAT,
    handlers=[
        logging.FileHandler(Config.get_log_file('tao_index_backtest')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

# Use centralized configuration
START_DATE = Config.START_DATE
END_DATE = Config.END_DATE
TOTAL_DAYS = (END_DATE - START_DATE).days
WEEKS_TOTAL = TOTAL_DAYS // 7 + 1

# Pre-compute calendar weeks for convenience
WEEKLY_DATES = [START_DATE + timedelta(weeks=week) for week in range(WEEKS_TOTAL + 1)]

# Rebalancing frequency
REBALANCE_WEEKS = Config.REBALANCE_WEEKS

# Indices to calculate
INDEX_CONFIGS = Config.INDEX_CONFIGS

# Network settings
NETWORK = Config.NETWORK
ARCHIVE_NETWORK = Config.ARCHIVE_NETWORK

# ============================================================================
# Subtensor Data Fetching
# ============================================================================

def retry_on_failure(func, *args, max_retries=Config.RETRY_ATTEMPTS, delay=Config.RETRY_DELAY, **kwargs):
    """
    Retry a function on failure with exponential backoff.
    
    Args:
        func: Function to retry
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries (seconds)
        *args, **kwargs: Arguments to pass to the function
    
    Returns:
        Function result or None on failure
    """
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            if attempt < max_retries:
                wait_time = delay * (2 ** attempt)  # Exponential backoff
                logger.warning(f"Attempt {attempt + 1}/{max_retries + 1} failed: {exc}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"All {max_retries + 1} attempts failed: {exc}")
                return None


def get_current_emissions() -> Dict[int, float]:
    """
    Fetch current emissions for all subnets using the Bittensor Python API.
    
    Returns:
        Mapping of netuid -> emission value (τ per block).
    """
    logger.info("Fetching current emissions from subtensor API...")
    
    def _fetch():
        subtensor = bt.subtensor(network=NETWORK)
        netuids = subtensor.get_subnets()
        emissions: Dict[int, float] = {}
        
        for netuid in netuids:
            try:
                subnet_info = subtensor.get_subnet_info(netuid)
                emission_value = float(subnet_info.emission_value)
                if emission_value > 0:
                    emissions[netuid] = emission_value
            except Exception as inner_exc:
                logger.debug(f"    Skipping subnet {netuid}: {inner_exc}")
                continue
        
        if not emissions:
            raise ValueError("No emissions data retrieved")
        
        return emissions
    
    result = retry_on_failure(_fetch)
    
    if result:
        logger.info(f"✓ Fetched emissions for {len(result)} subnets via API")
    else:
        logger.error("Failed to fetch emissions after all retries")
        result = {}
    
    return result


def calculate_top_subnets_by_emission(
    emissions: Dict[int, float],
    top_n: int
) -> Dict[int, float]:
    """
    Select top N subnets by emission and calculate emission-proportional weights.
    
    Args:
        emissions: {netuid: emission_value}
        top_n: Number of top subnets to select
    
    Returns:
        {netuid: weight} where weights sum to 1.0
    """
    # Sort by emission (descending)
    sorted_subnets = sorted(emissions.items(), key=lambda x: x[1], reverse=True)
    
    # Select top N
    top_subnets = sorted_subnets[:top_n]
    
    # Calculate total emission for normalization
    total_emission = sum(emission for _, emission in top_subnets)
    
    if total_emission == 0:
        logger.warning("Total emission is zero, using equal weights")
        return {netuid: 1.0 / top_n for netuid, _ in top_subnets}
    
    # Calculate emission-proportional weights
    weights = {
        netuid: emission / total_emission
        for netuid, emission in top_subnets
    }
    
    return weights


def ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime values are timezone-aware (UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class HistoricalPriceFetcher:
    """Fetch weekly subnet prices by hitting the archive node directly."""

    def __init__(self, week_datetimes: List[datetime], network: str = ARCHIVE_NETWORK):
        self.week_datetimes = [ensure_utc(dt) for dt in week_datetimes]
        self.subtensor = bt.subtensor(network=network)
        self.current_block = self.subtensor.get_current_block()
        self._timestamp_cache: Dict[int, datetime] = {}
        self.week_blocks = self._compute_week_blocks()

    def _get_timestamp(self, block: int) -> datetime:
        if block not in self._timestamp_cache:
            self._timestamp_cache[block] = self.subtensor.get_timestamp(block)
        return self._timestamp_cache[block]

    def _find_block_for_timestamp(self, target: datetime, low: int, high: int) -> int:
        target_utc = ensure_utc(target)
        best = low
        while low <= high:
            mid = (low + high) // 2
            mid_ts = self._get_timestamp(mid)
            if mid_ts <= target_utc:
                best = mid
                low = mid + 1
            else:
                high = mid - 1
        return best

    def _compute_week_blocks(self) -> List[int]:
        logger.info("Computing weekly block schedule from archive node...")
        blocks: List[int] = []
        low = 1
        high = self.current_block
        for dt in self.week_datetimes:
            block = self._find_block_for_timestamp(dt, low, high)
            blocks.append(block)
            low = block  # timestamps increase monotonically

        if blocks:
            first_ts = self._get_timestamp(blocks[0])
            last_ts = self._get_timestamp(blocks[-1])
            logger.info(
                f"  Week 0 -> block {blocks[0]} ({first_ts.date()}) | "
                f"Week {len(blocks) - 1} -> block {blocks[-1]} ({last_ts.date()})"
            )
        else:
            logger.warning("Unable to compute weekly blocks; price fetching will fail.")

        return blocks

    def weekly_price_count(self) -> int:
        return len(self.week_blocks)

    def fetch_prices(self, netuid: int) -> List[float]:
        prices: List[float] = []
        for block in self.week_blocks:
            price_value = 0.0
            try:
                balance = self.subtensor.get_subnet_price(netuid=netuid, block=block)
                price_value = float(balance.tao)
            except Exception as exc:
                logger.debug(f"    Subnet {netuid} block {block}: price unavailable ({exc})")
            prices.append(price_value)
        return prices


def normalize_price_series(prices: List[float]) -> List[float]:
    """
    Forward-fill zero/blank prices so NAV math is not distorted by missing values.
    """
    if not prices:
        return []

    normalized: List[float] = [0.0] * len(prices)

    first_valid = next((p for p in prices if p > 0), 0.0)
    last_valid = first_valid if first_valid > 0 else None

    for idx, price in enumerate(prices):
        if price > 0:
            last_valid = price
            normalized[idx] = price
        elif last_valid is not None:
            normalized[idx] = last_valid
        else:
            normalized[idx] = first_valid

    return normalized


def fetch_all_price_histories(
    subnet_list: List[int],
    price_fetcher: HistoricalPriceFetcher,
) -> Dict[int, List[float]]:
    """
    Fetch price histories for multiple subnets using the archive subtensor API.
    """
    histories: Dict[int, List[float]] = {}
    total = len(subnet_list)

    logger.info(f"Fetching price histories for {total} subnets from archive node...")

    for idx, netuid in enumerate(subnet_list, 1):
        logger.info(
            f"[{idx}/{total}] Subnet {netuid}: retrieving "
            f"{price_fetcher.weekly_price_count()} weekly points"
        )
        prices_raw = price_fetcher.fetch_prices(netuid)
        prices = normalize_price_series(prices_raw)
        non_zero = sum(1 for p in prices if p > 0)

        if non_zero >= 2:
            first_non_zero = next((p for p in prices if p > 0), 0.0)
            last_non_zero = next((p for p in reversed(prices) if p > 0), 0.0)
            logger.info(
                f"  ✓ {non_zero}/{len(prices)} usable points "
                f"({first_non_zero:.6f} → {last_non_zero:.6f} TAO)"
            )
            histories[netuid] = prices
        else:
            logger.warning("  ✗ Insufficient historical price data")

    return histories


# ============================================================================
# NAV Calculation with Dynamic Rebalancing
# ============================================================================

def calculate_index_nav_with_rebalancing(
    all_emissions: Dict[int, float],
    price_histories: Dict[int, List[float]],
    index_name: str,
    top_n: int,
    rebalance_weeks: int
) -> pd.DataFrame:
    """
    Calculate NAV for an index with periodic rebalancing.
    
    Args:
        all_emissions: Current emissions for all subnets (proxy for historical)
        price_histories: {netuid: [weekly prices]}
        index_name: Name of the index (e.g., 'TAO20')
        top_n: Number of top subnets to include
        rebalance_weeks: Rebalance frequency in weeks
    
    Returns:
        DataFrame with columns: week, date, nav, holdings
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Calculating {index_name} with rebalancing every {rebalance_weeks} weeks")
    logger.info(f"{'='*60}")
    
    # Determine number of weeks from shortest price history
    if not price_histories:
        return pd.DataFrame()
    
    num_weeks = min(len(prices) for prices in price_histories.values()) - 1
    
    # Initialize
    nav = 1.0
    nav_history = []
    
    # Initial rebalancing at week 0
    current_weights = calculate_top_subnets_by_emission(all_emissions, top_n)
    current_holdings = list(current_weights.keys())
    
    logger.info(f"\nWeek 0 - Initial allocation:")
    logger.info(f"  Holdings: {len(current_holdings)} subnets")
    for netuid, weight in sorted(current_weights.items(), key=lambda x: x[1], reverse=True)[:5]:
        logger.info(f"    Subnet {netuid}: {weight*100:.2f}%")
    
    # Iterate through weeks
    for week in range(num_weeks + 1):
        # Check if it's a rebalancing week (every rebalance_weeks, starting from week 0)
        if week > 0 and week % rebalance_weeks == 0:
            logger.info(f"\nWeek {week} - REBALANCING")
            
            # Recalculate top subnets and weights based on current emissions
            current_weights = calculate_top_subnets_by_emission(all_emissions, top_n)
            current_holdings = list(current_weights.keys())
            
            logger.info(f"  New holdings: {len(current_holdings)} subnets")
            for netuid, weight in sorted(current_weights.items(), key=lambda x: x[1], reverse=True)[:3]:
                logger.info(f"    Subnet {netuid}: {weight*100:.2f}%")
            
            # NAV stays the same, only holdings change
            logger.info(f"  NAV before/after rebalance: {nav:.6f} (unchanged)")
        
        # Calculate returns for this week
        if week > 0:
            week_return = 0.0
            
            for netuid in current_holdings:
                if netuid not in price_histories:
                    continue
                
                prices = price_histories[netuid]
                price_prev = prices[week - 1]
                price_now = prices[week]
                
                if price_prev > 0 and price_now > 0:
                    token_return = (price_now / price_prev) - 1
                    weight = current_weights.get(netuid, 0)
                    week_return += weight * token_return
                else:
                    logger.debug(
                        f"      Skipping subnet {netuid} week {week}: "
                        f"price_prev={price_prev:.6f}, price_now={price_now:.6f}"
                    )
            
            # Update NAV (continuous, not reset at rebalance)
            nav *= (1 + week_return)
            logger.info(f"Week {week}: Return = {week_return*100:+.2f}%, NAV = {nav:.6f}")
        
        # Record NAV
        if week < len(WEEKLY_DATES):
            week_date = WEEKLY_DATES[week]
        else:
            week_date = START_DATE + timedelta(weeks=week)
        nav_history.append({
            'week': week,
            'date': week_date,
            'nav': nav,
            'num_holdings': len(current_holdings)
        })
    
    logger.info(f"\nFinal {index_name} NAV: {nav:.6f}")
    logger.info(f"Total Return: {(nav - 1) * 100:+.2f}%")
    
    return pd.DataFrame(nav_history)


# ============================================================================
# Visualization
# ============================================================================

def create_comparison_chart(nav_dfs: Dict[str, pd.DataFrame], output_path: str):
    """
    Create comparison chart for multiple indices.
    
    Args:
        nav_dfs: {index_name: nav_dataframe}
        output_path: Path to save the chart
    """
    plt.figure(figsize=(14, 8))
    
    colors = {
        'TAO20': '#2E86AB',
        'TAO15': '#A23B72',
        'TAO10': '#F18F01'
    }
    
    for index_name, df in nav_dfs.items():
        if not df.empty:
            plt.plot(
                df['date'],
                df['nav'],
                label=index_name,
                linewidth=2.5,
                color=colors.get(index_name, '#333333')
            )
    
    plt.axhline(y=1.0, color='gray', linestyle=':', alpha=0.5, label='Initial NAV')
    
    plt.title(
        f'TAO Index Performance - Dynamic Rebalancing\n{START_DATE.strftime("%B %Y")} (4 weeks)',
        fontsize=16,
        fontweight='bold',
        pad=20
    )
    plt.xlabel('Date', fontsize=12)
    plt.ylabel('Net Asset Value (NAV)', fontsize=12)
    plt.legend(loc='best', fontsize=11, framealpha=0.9)
    plt.grid(True, alpha=0.3, linestyle='--')
    plt.tight_layout()
    
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    logger.info(f"✓ Chart saved: {output_path}")
    plt.close()


# ============================================================================
# Main Execution
# ============================================================================

def main():
    """Main execution function with proper error handling."""
    try:
        Config.print_config()
        
        logger.info("=" * 80)
        logger.info("TAO INDEX BACKTEST - DYNAMIC REBALANCING")
        logger.info("=" * 80)
        logger.info(f"Period: {START_DATE.strftime('%Y-%m-%d')} to {END_DATE.strftime('%Y-%m-%d')}")
        logger.info(f"Duration: {TOTAL_DAYS} days = {WEEKS_TOTAL} weeks")
        logger.info(f"Rebalancing: Every {REBALANCE_WEEKS} weeks")
        logger.info(f"Indices: {', '.join(INDEX_CONFIGS.keys())}")
        logger.info("")
        
        # Step 1: Fetch emissions data
        logger.info("=" * 80)
        logger.info("STEP 1: Fetching Emissions Data")
        logger.info("=" * 80)
        
        all_emissions = get_current_emissions()
        
        if not all_emissions:
            logger.error("Failed to fetch emissions data!")
            return 1
    
        logger.info(f"Total subnets with emissions: {len(all_emissions)}")
        logger.info(f"Total emission rate: {sum(all_emissions.values()):.6f} τ/block")
        
        # Show top 10 by emission
        logger.info("\nTop 10 subnets by emission:")
        sorted_emissions = sorted(all_emissions.items(), key=lambda x: x[1], reverse=True)
        for i, (netuid, emission) in enumerate(sorted_emissions[:10], 1):
            logger.info(f"  {i}. Subnet {netuid}: {emission:.6f} τ/block")
        
        # Step 2: Determine all subnets we need price data for
        logger.info("")
        logger.info("=" * 80)
        logger.info("STEP 2: Determining Required Subnets")
        logger.info("=" * 80)
        
        # Get top 20 (covers TAO20, TAO15, TAO10)
        max_subnets = max(INDEX_CONFIGS.values())
        all_required_subnets = list(calculate_top_subnets_by_emission(all_emissions, max_subnets).keys())
        
        logger.info(f"Need price data for top {max_subnets} subnets: {all_required_subnets}")
        
        # Step 3: Fetch price histories
        logger.info("")
        logger.info("=" * 80)
        logger.info("STEP 3: Fetching Price Histories (ARCHIVE)")
        logger.info("=" * 80)
        logger.info(
            f"Fetching {WEEKS_TOTAL + 1} weekly price points "
            f"({WEEKLY_DATES[0].strftime('%Y-%m-%d')} → {WEEKLY_DATES[-1].strftime('%Y-%m-%d')})"
        )
        logger.info("Using archive subtensor API for reliable historical prices")
        logger.info("")
        
        price_fetcher = HistoricalPriceFetcher(WEEKLY_DATES, network=ARCHIVE_NETWORK)
        start_time = time.time()
        price_histories = fetch_all_price_histories(all_required_subnets, price_fetcher)
        elapsed = time.time() - start_time
        
        logger.info("")
        logger.info(f"✓ Completed in {elapsed/60:.1f} minutes")
        logger.info(f"✓ Successfully fetched {len(price_histories)}/{len(all_required_subnets)} subnets")
        
        if len(price_histories) < 5:
            logger.error("Insufficient price data - less than 5 subnets fetched!")
            return 1
        
        # Step 4: Calculate NAV for each index
        logger.info("")
        logger.info("=" * 80)
        logger.info("STEP 4: Calculating Index NAVs")
        logger.info("=" * 80)
        
        nav_results = {}
        
        for index_name, top_n in INDEX_CONFIGS.items():
            nav_df = calculate_index_nav_with_rebalancing(
                all_emissions=all_emissions,
                price_histories=price_histories,
                index_name=index_name,
                top_n=top_n,
                rebalance_weeks=REBALANCE_WEEKS
            )
            nav_results[index_name] = nav_df
        
        # Step 5: Create visualization
        logger.info("")
        logger.info("=" * 80)
        logger.info("STEP 5: Creating Visualization")
        logger.info("=" * 80)
        
        chart_path = Config.get_results_file('tao_index_dynamic_comparison', 'png')
        create_comparison_chart(nav_results, chart_path)
        
        # Step 6: Save results to CSV
        logger.info("")
        logger.info("=" * 80)
        logger.info("STEP 6: Saving Results")
        logger.info("=" * 80)
        
        csv_path = Config.get_results_file('tao_index_dynamic', 'csv')
        
        # Combine all NAV data
        if any(not df.empty for df in nav_results.values()):
            combined_df = None
            
            for index_name, df in nav_results.items():
                if not df.empty:
                    if combined_df is None:
                        combined_df = df[['week', 'date']].copy()
                    combined_df[index_name] = df['nav'].values
            
            if combined_df is not None:
                combined_df.to_csv(csv_path, index=False)
                logger.info(f"✓ Data saved: {csv_path}")
        
        # Step 7: Print summary
        logger.info("")
        logger.info("=" * 80)
        logger.info("FINAL RESULTS")
        logger.info("=" * 80)
        logger.info("")
        
        for index_name, df in nav_results.items():
            if not df.empty:
                final_nav = df['nav'].iloc[-1]
                total_return = (final_nav - 1) * 100
                logger.info(f"{index_name:8s}: NAV = {final_nav:.6f}, Return = {total_return:+.2f}%")
    
        logger.info("")
        logger.info("=" * 80)
        logger.info("BACKTEST COMPLETE!")
        logger.info("=" * 80)
        
        return 0
        
    except KeyboardInterrupt:
        logger.warning("Backtest interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Backtest failed with error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
