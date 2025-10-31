#!/usr/bin/env python3
"""
TAO20 Simplified APY Backtest
==============================
Simplified backtest focusing on APY contribution to NAV.

Uses current prices and simulates NAV growth from alpha staking yields.
This provides a quick demonstration of how the APY model works without
requiring slow historical price fetching from the archive node.

Author: Alexander Lange
Date: October 22, 2025
"""

import os
import json
import re
import subprocess
import logging
from datetime import datetime, timedelta
from typing import Dict
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
BACKTEST_DAYS = 30  # 30 days simulation
START_NAV = 1.0
REBALANCE_DAYS = 14  # Biweekly rebalancing


def get_emissions_from_btcli() -> Dict[int, float]:
    """Fetch emissions using btcli --json-output."""
    logger.info("Fetching emissions from btcli...")
    
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
    """Fetch emissions, supply, and calculate alpha staking APY."""
    logger.info("Fetching subnet data and calculating APY...")
    
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
            
            if emission <= 0 or supply <= 0:
                continue
            
            apy, staked, daily_emissions = apy_model.calculate_alpha_apy(emission, supply)
            
            subnet_data[netuid] = {
                'emission': emission,
                'supply': supply,
                'alpha_apy': apy,
                'staked_alpha': staked,
                'staked_ratio': staked / supply,
                'daily_emissions': daily_emissions
            }
        
        logger.info(f"✓ Calculated APY for {len(subnet_data)} subnets")
        return subnet_data
        
    except Exception as e:
        logger.error(f"Failed to get subnet data: {e}")
        return {}


def run_simplified_backtest(
    subnet_data: Dict[int, Dict[str, float]],
    days: int,
    assume_price_change: float = 0.0
) -> pd.DataFrame:
    """
    Run simplified backtest with APY compounding.
    
    Args:
        subnet_data: Subnet data with APY
        days: Number of days to simulate
        assume_price_change: Daily price change assumption (e.g., 0.01 = 1% per day)
    
    Returns:
        DataFrame with daily NAV history
    """
    logger.info(f"Running simplified backtest for {days} days...")
    
    # Calculate emission weights
    total_emission = sum(d['emission'] for d in subnet_data.values())
    weights = {
        netuid: data['emission'] / total_emission
        for netuid, data in subnet_data.items()
    }
    
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


def main():
    """Main execution."""
    logger.info("=" * 80)
    logger.info("TAO20 SIMPLIFIED APY BACKTEST")
    logger.info("=" * 80)
    logger.info("")
    
    # Get subnet data
    logger.info("[1/3] Fetching subnet data and calculating APY...")
    subnet_data = get_subnet_data_with_apy()
    
    if not subnet_data:
        logger.error("Failed to get subnet data. Exiting.")
        return
    
    logger.info(f"Loaded data for {len(subnet_data)} subnets")
    logger.info("")
    
    # Calculate weights and show portfolio
    logger.info("[2/3] Calculating emission-based weights...")
    total_emission = sum(d['emission'] for d in subnet_data.values())
    weights = {
        netuid: data['emission'] / total_emission
        for netuid, data in subnet_data.items()
    }
    
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
        logger.info(f"  Subnet {netuid}: {weight*100:.2f}% weight, {apy:.1f}% APY")
    logger.info("")
    
    # Run backtest scenarios
    logger.info("[3/3] Running backtest scenarios...")
    logger.info("")
    
    scenarios = [
        ("APY Only (no price change)", 0.0),
        ("Bearish (-1% daily price)", -0.01),
        ("Bullish (+1% daily price)", 0.01),
    ]
    
    all_results = {}
    
    for scenario_name, price_change in scenarios:
        logger.info(f"Scenario: {scenario_name}")
        results_df = run_simplified_backtest(subnet_data, BACKTEST_DAYS, price_change)
        
        final_nav = results_df.iloc[-1]['nav']
        total_return = (final_nav - START_NAV) / START_NAV * 100
        annualized_return = ((final_nav / START_NAV) ** (365 / BACKTEST_DAYS) - 1) * 100
        
        logger.info(f"  Final NAV: {final_nav:.4f}")
        logger.info(f"  Total Return ({BACKTEST_DAYS} days): {total_return:.2f}%")
        logger.info(f"  Annualized Return: {annualized_return:.2f}%")
        logger.info("")
        
        all_results[scenario_name] = results_df
    
    # Save results
    logger.info("=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    os.makedirs('backtest_results', exist_ok=True)
    
    # Save each scenario
    for scenario_name, df in all_results.items():
        filename = scenario_name.lower().replace(' ', '_').replace('(', '').replace(')', '').replace('%', 'pct')
        output_file = f"backtest_results/tao20_simple_{filename}_{timestamp}.csv"
        df.to_csv(output_file, index=False)
        logger.info(f"✓ Saved: {output_file}")
    
    # Create summary comparison
    summary_data = []
    for scenario_name, df in all_results.items():
        final = df.iloc[-1]
        summary_data.append({
            'scenario': scenario_name,
            'final_nav': final['nav'],
            'total_return_pct': (final['nav'] - START_NAV) / START_NAV * 100,
            'annualized_return_pct': ((final['nav'] / START_NAV) ** (365 / BACKTEST_DAYS) - 1) * 100,
            'apy_contribution': (final['apy_only_nav'] - START_NAV) / START_NAV * 100
        })
    
    summary_df = pd.DataFrame(summary_data)
    summary_file = f"backtest_results/tao20_simple_summary_{timestamp}.csv"
    summary_df.to_csv(summary_file, index=False)
    logger.info(f"✓ Saved summary: {summary_file}")
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("KEY INSIGHTS")
    logger.info("=" * 80)
    logger.info(f"Portfolio-weighted APY: {weighted_apy:.2f}%")
    logger.info(f"Expected daily yield: {(weighted_apy/365):.3f}%")
    logger.info(f"Expected {BACKTEST_DAYS}-day return (APY only): {((1 + weighted_apy/100/365) ** BACKTEST_DAYS - 1) * 100:.2f}%")
    logger.info("")
    
    # Calculate APY contribution vs price for different scenarios
    logger.info("APY provides a strong yield cushion against price volatility.")
    logger.info(f"Even with -1% daily price decline, APY ({weighted_apy:.1f}%) helps offset losses.")
    logger.info("")


if __name__ == '__main__':
    main()












