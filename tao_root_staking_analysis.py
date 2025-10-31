#!/usr/bin/env python3
"""
Root Network (Subnet 0) Staking Analysis
=========================================
Analyzes what would have happened if TAO was staked to the root network (subnet 0)
from the beginning, calculating compound staking rewards over time.

The root network has a stable value of 1 (no price fluctuation) but earns staking APY.

Author: Alexander Lange
Date: October 28, 2025
"""

import os
import json
import logging
import subprocess
import re
from datetime import datetime, timedelta
from typing import Dict, Tuple
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

NETWORK = 'finney'
START_AMOUNT = 100.0  # Starting with 100 TAO staked
ROOT_SUBNET_ID = 0


class RootNetworkStakingModel:
    """Model for calculating root network staking returns."""
    
    def __init__(self):
        self.tao_per_day = 7200  # Total TAO emissions per day
        
    def get_current_root_network_data(self) -> Dict:
        """Fetch current root network data from the chain."""
        logger.info(f"Fetching root network (subnet {ROOT_SUBNET_ID}) data...")
        
        try:
            cmd = ['btcli', 'subnets', 'list', '--network', NETWORK, '--json-output']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0:
                logger.error("Failed to fetch subnet data")
                return {}
            
            # Clean the JSON output
            cleaned = re.sub(r'\\n', ' ', result.stdout)
            cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)
            data = json.loads(cleaned)
            subnets = data.get('subnets', {})
            
            # Get root network data
            if str(ROOT_SUBNET_ID) not in subnets:
                logger.error(f"Subnet {ROOT_SUBNET_ID} not found in data")
                return {}
            
            root_data = subnets[str(ROOT_SUBNET_ID)]
            logger.info(f"✓ Root network data fetched")
            logger.info(f"  Emission: {root_data.get('emission', 0)}")
            logger.info(f"  Supply: {root_data.get('supply', 0)}")
            
            return root_data
            
        except Exception as e:
            logger.error(f"Failed to get root network data: {e}")
            return {}
    
    def calculate_root_apy(self, emission_fraction: float, total_supply: float, 
                          staking_ratio: float = 0.15) -> Tuple[float, float]:
        """
        Calculate APY for root network staking.
        
        Args:
            emission_fraction: Fraction of total emissions going to subnet 0
            total_supply: Total supply of the subnet
            staking_ratio: Estimated ratio of TAO that is staked (default 15%)
            
        Returns:
            Tuple of (apy_percentage, daily_emissions)
        """
        # Daily emissions for root network
        daily_emissions = emission_fraction * self.tao_per_day
        
        # Staked amount (estimated)
        staked_tao = total_supply * staking_ratio
        
        if staked_tao <= 0:
            return 0.0, daily_emissions
        
        # Daily yield per staked TAO
        daily_yield_per_tao = daily_emissions / staked_tao
        
        # Annualize
        apy = daily_yield_per_tao * 365 * 100
        
        return apy, daily_emissions
    
    def estimate_historical_apy(self, date: datetime) -> float:
        """
        Estimate historical APY for root network.
        Uses a simplified model based on network growth over time.
        
        Early network: Higher APY (more emissions, less staked)
        Mature network: Lower APY (same emissions, more staked)
        """
        # Days since network start (approximate)
        network_start = datetime(2024, 1, 1)  # Approximate
        days_elapsed = (date - network_start).days
        
        # Model: APY decreases as network matures
        # Early: ~20-30% APY, Current: ~5-15% APY
        if days_elapsed < 100:
            # Early network, high APY
            base_apy = 25.0
        elif days_elapsed < 200:
            # Transitioning
            base_apy = 20.0
        elif days_elapsed < 300:
            base_apy = 15.0
        elif days_elapsed < 400:
            base_apy = 12.0
        else:
            # Mature network
            base_apy = 10.0
        
        # Add some variation based on season
        # In reality, APY fluctuates based on staking participation
        day_of_year = date.timetuple().tm_yday
        seasonal_factor = 1.0 + 0.1 * (day_of_year % 30 - 15) / 15  # ±10% variation
        
        estimated_apy = base_apy * seasonal_factor
        
        return estimated_apy


def run_staking_analysis(start_date: datetime, end_date: datetime, 
                         initial_amount: float = START_AMOUNT):
    """
    Run staking analysis for root network.
    
    Models compound staking where daily rewards are automatically re-staked.
    """
    logger.info("=" * 80)
    logger.info("ROOT NETWORK (SUBNET 0) STAKING ANALYSIS")
    logger.info("=" * 80)
    logger.info(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    logger.info(f"Initial staked amount: {initial_amount:.2f} TAO")
    logger.info("")
    
    model = RootNetworkStakingModel()
    
    # Get current root network data for reference
    current_data = model.get_current_root_network_data()
    if current_data:
        current_emission = current_data.get('emission', 0)
        current_supply = current_data.get('supply', 0)
        current_apy, daily_em = model.calculate_root_apy(current_emission, current_supply)
        logger.info(f"Current root network APY estimate: {current_apy:.2f}%")
        logger.info("")
    
    # Initialize
    staked_amount = initial_amount
    results = []
    
    # Simulate day by day
    days_to_simulate = (end_date - start_date).days + 1
    logger.info(f"Simulating {days_to_simulate} days of staking...")
    logger.info("")
    
    for day in range(days_to_simulate):
        current_date = start_date + timedelta(days=day)
        
        # Estimate APY for this day
        daily_apy = model.estimate_historical_apy(current_date)
        
        # Calculate daily return
        daily_yield_rate = (daily_apy / 100) / 365
        daily_rewards = staked_amount * daily_yield_rate
        
        # Compound: Add rewards to staked amount
        staked_amount += daily_rewards
        
        # Store results
        results.append({
            'date': current_date,
            'staked_amount': staked_amount,
            'daily_apy': daily_apy,
            'daily_rewards': daily_rewards,
            'cumulative_rewards': staked_amount - initial_amount,
            'total_return_pct': ((staked_amount / initial_amount) - 1) * 100
        })
        
        # Log progress
        if day % 30 == 0 or day < 3:
            logger.info(
                f"Day {day:3d} ({current_date.strftime('%Y-%m-%d')}): "
                f"Staked={staked_amount:.4f} TAO, APY={daily_apy:.2f}%, "
                f"Daily Reward={daily_rewards:.6f} TAO"
            )
    
    logger.info("")
    logger.info("✓ Simulation complete!")
    logger.info("")
    
    # Create DataFrame
    df = pd.DataFrame(results)
    
    # Calculate statistics
    final_amount = df.iloc[-1]['staked_amount']
    total_rewards = final_amount - initial_amount
    total_return_pct = ((final_amount / initial_amount) - 1) * 100
    avg_apy = df['daily_apy'].mean()
    
    # Annualized return (CAGR)
    years = days_to_simulate / 365
    cagr = ((final_amount / initial_amount) ** (1 / years) - 1) * 100
    
    logger.info("=" * 80)
    logger.info("STAKING RESULTS")
    logger.info("=" * 80)
    logger.info(f"Initial stake: {initial_amount:.2f} TAO")
    logger.info(f"Final amount: {final_amount:.2f} TAO")
    logger.info(f"Total rewards earned: {total_rewards:.2f} TAO")
    logger.info(f"Total return: {total_return_pct:.2f}%")
    logger.info(f"Average APY: {avg_apy:.2f}%")
    logger.info(f"CAGR (annualized): {cagr:.2f}%")
    logger.info("")
    
    # Save to CSV
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    os.makedirs('backtest_results', exist_ok=True)
    csv_file = f"backtest_results/root_staking_analysis_{timestamp}.csv"
    df.to_csv(csv_file, index=False)
    logger.info(f"✓ Saved: {csv_file}")
    
    # Create visualizations
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(18, 12))
    
    # 1. Staked Amount Growth
    ax1.plot(df['date'], df['staked_amount'], 'b-', linewidth=2.5)
    ax1.axhline(y=initial_amount, color='gray', linestyle=':', alpha=0.5, label='Initial Stake')
    ax1.set_xlabel('Date', fontsize=11)
    ax1.set_ylabel('Staked Amount (TAO)', fontsize=11)
    ax1.set_title('Root Network Staking: Total Staked Amount Growth', fontsize=13, fontweight='bold')
    ax1.legend(loc='best', fontsize=9)
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=9)
    
    # 2. Cumulative Rewards
    ax2.fill_between(df['date'], 0, df['cumulative_rewards'], color='green', alpha=0.3)
    ax2.plot(df['date'], df['cumulative_rewards'], 'g-', linewidth=2)
    ax2.set_xlabel('Date', fontsize=11)
    ax2.set_ylabel('Cumulative Rewards (TAO)', fontsize=11)
    ax2.set_title('Cumulative Staking Rewards Earned', fontsize=13, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=9)
    
    # 3. Daily APY over Time
    ax3.plot(df['date'], df['daily_apy'], 'r-', linewidth=1.5, alpha=0.7)
    ax3.axhline(y=avg_apy, color='blue', linestyle='--', alpha=0.5, label=f'Average APY: {avg_apy:.2f}%')
    ax3.set_xlabel('Date', fontsize=11)
    ax3.set_ylabel('APY (%)', fontsize=11)
    ax3.set_title('Estimated Historical APY (Root Network)', fontsize=13, fontweight='bold')
    ax3.legend(loc='best', fontsize=9)
    ax3.grid(True, alpha=0.3)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=9)
    
    # 4. Total Return Percentage
    ax4.fill_between(df['date'], 0, df['total_return_pct'], color='purple', alpha=0.3)
    ax4.plot(df['date'], df['total_return_pct'], 'purple', linewidth=2)
    ax4.set_xlabel('Date', fontsize=11)
    ax4.set_ylabel('Total Return (%)', fontsize=11)
    ax4.set_title('Total Return from Root Network Staking', fontsize=13, fontweight='bold')
    ax4.grid(True, alpha=0.3)
    ax4.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.setp(ax4.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=9)
    
    plt.tight_layout()
    
    plot_file = f"backtest_results/root_staking_analysis_{timestamp}.png"
    plt.savefig(plot_file, dpi=150, bbox_inches='tight')
    logger.info(f"✓ Plot saved: {plot_file}")
    logger.info("")
    
    # Open plot
    os.system(f"open {plot_file}")
    
    return df


if __name__ == '__main__':
    # Match the backtest period from the TAO20 analysis
    start = datetime(2025, 2, 27)
    end = datetime(2025, 10, 26)
    
    df = run_staking_analysis(start, end, initial_amount=START_AMOUNT)

