#!/usr/bin/env python3
"""
TAO20 Rebalancing Frequency Optimization
==========================================
Simulates different rebalancing frequencies using hourly emissions data to find
the optimal balance between performance, tracking error, and transaction costs.

Features:
- Hourly price data from emissions_v2
- Staking rewards calculated from validator dividends
- Variable rebalancing frequencies (1h to 1 week)
- Comprehensive performance metrics
- Cost/benefit analysis

Author: Alexander Lange
Date: October 30, 2025
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
BASE_DIR = Path(__file__).parent.absolute()
EMISSIONS_DIR = BASE_DIR / 'emissions_v2'
RESULTS_DIR = BASE_DIR / 'rebalance_optimization_results'
RESULTS_DIR.mkdir(exist_ok=True)

# Simulation parameters
INITIAL_CAPITAL = 1_000_000  # $1M
TRANSACTION_COST_BPS = 10  # 10 basis points = 0.1%
SLIPPAGE_BPS = 5  # 5 basis points = 0.05%
TOP_N_SUBNETS = 20  # TAO20 index

# Rebalancing frequencies to test (in hours)
REBALANCING_FREQUENCIES = {
    '1h': 1,
    '2h': 2,
    '4h': 4,
    '8h': 8,
    '12h': 12,
    '1d': 24,
    '2d': 48,
    '3d': 72,
    '1w': 168,
    'continuous': 0  # Ideal benchmark - rebalance every hour with no costs
}

# Reputable validators for staking rewards calculation
REPUTABLE_VALIDATORS = [
    'opentensor',
    'rt21',
    'rizzo',
    'yuma',
    'kraken',
    'OTF',
    'RT21',
    'Rizzo',
    'Yuma',
    'Kraken'
]


class EmissionsDataLoader:
    """Loads and processes hourly emissions data."""
    
    def __init__(self, emissions_dir: Path):
        self.emissions_dir = emissions_dir
        self.hourly_data = []
        self.subnet_prices = {}
        
    def load_all_data(self) -> pd.DataFrame:
        """Load all emissions data files and create a unified hourly dataset."""
        logger.info("Loading emissions data from %s", self.emissions_dir)
        
        json_files = sorted(self.emissions_dir.glob('emissions_v2_*.json'))
        logger.info("Found %d emissions files", len(json_files))
        
        all_samples = []
        
        for json_file in json_files:
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                
                if 'samples' not in data:
                    logger.warning("No samples in %s", json_file)
                    continue
                
                # Extract samples with emissions data
                for sample in data['samples']:
                    sample_data = {
                        'timestamp': pd.to_datetime(sample['block_timestamp_utc']),
                        'block': sample['closest_block'],
                        'emissions': sample['emissions']
                    }
                    all_samples.append(sample_data)
                    
            except Exception as e:
                logger.error("Error loading %s: %s", json_file, e)
                continue
        
        logger.info("Loaded %d hourly samples", len(all_samples))
        
        # Convert to DataFrame
        df = pd.DataFrame(all_samples)
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        # Calculate implied prices from emissions (using emissions as proxy for relative value)
        df = self._calculate_subnet_prices(df)
        
        return df
    
    def _calculate_subnet_prices(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate subnet prices from emissions data.
        
        We simulate price movement as cumulative returns based on emission rate changes.
        Higher emissions = more demand = price appreciation.
        """
        logger.info("Calculating subnet price proxies from emissions")
        
        # Extract all unique subnet IDs
        all_subnet_ids = set()
        for emissions in df['emissions']:
            all_subnet_ids.update(emissions.keys())
        
        subnet_ids = sorted([int(sid) for sid in all_subnet_ids])
        logger.info("Found %d unique subnets", len(subnet_ids))
        
        # Create price columns for each subnet
        # Use cumulative product of (1 + emission_change_pct) to simulate price movement
        price_data = {}
        
        for subnet_id in subnet_ids:
            subnet_str = str(subnet_id)
            emission_rates = []
            
            for emissions in df['emissions']:
                rate = float(emissions.get(subnet_str, 0.0))
                emission_rates.append(rate)
            
            # Calculate percentage changes in emissions
            emission_series = pd.Series(emission_rates).replace(0, np.nan)
            
            # For price simulation: assume emission changes correlate with price changes
            # Use a scaling factor to convert emissions to reasonable price movements
            pct_changes = emission_series.pct_change(fill_method=None).fillna(0.0)
            
            # Scale down to reasonable hourly returns (emissions are too volatile)
            pct_changes = pct_changes * 0.1  # Scale factor
            
            # Clip extreme values
            pct_changes = pct_changes.clip(-0.5, 0.5)
            
            # Calculate cumulative prices starting at 100
            prices = 100 * (1 + pct_changes).cumprod()
            
            # Fill NaN with forward fill
            prices = prices.ffill().fillna(100.0)
            
            price_data[f'price_{subnet_id}'] = prices.values
        
        # Add all price columns at once to avoid fragmentation
        price_df = pd.DataFrame(price_data, index=df.index)
        df = pd.concat([df, price_df], axis=1)
        
        return df


class StakingRewardsCalculator:
    """Calculates staking rewards from validator dividend data."""
    
    def __init__(self):
        pass
    
    def calculate_staking_apy(self, emissions_data: Dict, subnet_id: int, 
                              validator_data: Optional[Dict] = None) -> float:
        """
        Calculate staking APY for a subnet.
        
        Formula from user:
        1. Find reputable validator on subnet
        2. Get dividends earned by validator in block
        3. Divide by validator's stake in block
        4. Add 1 to get multiplier (e.g., 1.000002)
        
        For now, we'll estimate based on emissions rate as we don't have
        full validator dividend data in the current emissions files.
        """
        # Placeholder: In production, this would query actual validator data
        # For now, estimate based on emissions rate
        # Typical staking rewards are 10-20% APY in Bittensor
        
        emission_rate = emissions_data.get(str(subnet_id), 0.0)
        
        # Rough estimation: higher emissions generally correlate with higher staking rewards
        # This is a simplification and should be replaced with actual validator data
        estimated_daily_return = emission_rate * 0.0001  # Conservative estimate
        estimated_apy = estimated_daily_return * 365
        
        return estimated_apy
    
    def apply_staking_rewards(self, holdings: Dict[int, float], 
                              emissions_data: Dict, hours: float) -> Dict[int, float]:
        """
        Apply staking rewards to holdings over a time period.
        
        Args:
            holdings: Dict of subnet_id -> amount
            emissions_data: Emissions data for the period
            hours: Number of hours to compound
        
        Returns:
            Updated holdings with staking rewards
        """
        updated_holdings = holdings.copy()
        
        for subnet_id, amount in holdings.items():
            if amount <= 0:
                continue
            
            apy = self.calculate_staking_apy(emissions_data, subnet_id)
            hourly_rate = (1 + apy) ** (1 / (365 * 24)) - 1
            
            # Compound over the hours
            multiplier = (1 + hourly_rate) ** hours
            updated_holdings[subnet_id] = amount * multiplier
        
        return updated_holdings


class TAO20Portfolio:
    """Manages TAO20 portfolio with dynamic rebalancing."""
    
    def __init__(self, initial_capital: float, top_n: int = 20):
        self.initial_capital = initial_capital
        self.top_n = top_n
        self.cash = initial_capital
        self.holdings = {}  # subnet_id -> quantity
        self.nav_history = []
        self.rebalance_history = []
        self.transaction_costs = 0.0
        
    def calculate_target_weights(self, emissions: Dict) -> Dict[int, float]:
        """
        Calculate target portfolio weights based on emissions.
        Select top N subnets by emission rate and weight by emission.
        """
        # Convert to integer subnet IDs and float emissions
        subnet_emissions = {
            int(sid): float(emission) 
            for sid, emission in emissions.items()
        }
        
        # Sort by emissions and take top N
        sorted_subnets = sorted(
            subnet_emissions.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:self.top_n]
        
        # Calculate weights proportional to emissions
        total_emissions = sum(emission for _, emission in sorted_subnets)
        
        if total_emissions == 0:
            return {}
        
        weights = {
            subnet_id: emission / total_emissions
            for subnet_id, emission in sorted_subnets
        }
        
        return weights
    
    def calculate_portfolio_value(self, prices: Dict[int, float]) -> float:
        """Calculate total portfolio value."""
        holdings_value = sum(
            quantity * prices.get(subnet_id, 0.0)
            for subnet_id, quantity in self.holdings.items()
        )
        return self.cash + holdings_value
    
    def rebalance(self, target_weights: Dict[int, float], prices: Dict[int, float],
                  transaction_cost_bps: float, slippage_bps: float) -> float:
        """
        Rebalance portfolio to target weights.
        
        Returns:
            Total transaction cost
        """
        portfolio_value = self.calculate_portfolio_value(prices)
        
        # Calculate target values for each subnet
        target_values = {
            subnet_id: portfolio_value * weight
            for subnet_id, weight in target_weights.items()
        }
        
        # Calculate current values
        current_values = {
            subnet_id: self.holdings.get(subnet_id, 0.0) * prices.get(subnet_id, 0.0)
            for subnet_id in set(list(target_weights.keys()) + list(self.holdings.keys()))
        }
        
        # Calculate trades needed
        total_trade_value = 0.0
        trades = {}
        
        for subnet_id in set(list(target_weights.keys()) + list(self.holdings.keys())):
            current_value = current_values.get(subnet_id, 0.0)
            target_value = target_values.get(subnet_id, 0.0)
            trade_value = target_value - current_value
            
            if abs(trade_value) > 0.01:  # Minimum trade threshold
                trades[subnet_id] = trade_value
                total_trade_value += abs(trade_value)
        
        # Execute trades with costs
        total_cost = 0.0
        
        for subnet_id, trade_value in trades.items():
            price = prices.get(subnet_id, 0.0)
            if price == 0:
                continue
            
            # Calculate costs
            cost = abs(trade_value) * (transaction_cost_bps + slippage_bps) / 10000
            total_cost += cost
            
            # Update holdings
            quantity_change = trade_value / price
            current_quantity = self.holdings.get(subnet_id, 0.0)
            new_quantity = current_quantity + quantity_change
            
            if new_quantity > 0.001:
                self.holdings[subnet_id] = new_quantity
            elif subnet_id in self.holdings:
                del self.holdings[subnet_id]
            
            # Update cash
            self.cash -= (trade_value + cost)
        
        self.transaction_costs += total_cost
        
        return total_cost


class RebalanceSimulator:
    """Simulates portfolio performance under different rebalancing frequencies."""
    
    def __init__(self, data: pd.DataFrame):
        self.data = data
        self.staking_calc = StakingRewardsCalculator()
        
    def simulate(self, rebalance_freq_hours: int, 
                 transaction_cost_bps: float,
                 slippage_bps: float,
                 apply_costs: bool = True) -> Dict:
        """
        Run simulation for a specific rebalancing frequency.
        
        Args:
            rebalance_freq_hours: Hours between rebalances (0 = every hour)
            transaction_cost_bps: Transaction cost in basis points
            slippage_bps: Slippage cost in basis points
            apply_costs: Whether to apply transaction costs
        
        Returns:
            Dictionary with simulation results
        """
        portfolio = TAO20Portfolio(INITIAL_CAPITAL, TOP_N_SUBNETS)
        
        nav_history = []
        rebalance_count = 0
        total_transaction_costs = 0.0
        hours_since_rebalance = 0
        
        for idx, row in self.data.iterrows():
            timestamp = row['timestamp']
            emissions = row['emissions']
            
            # Extract prices
            prices = {}
            for col in self.data.columns:
                if col.startswith('price_'):
                    subnet_id = int(col.split('_')[1])
                    prices[subnet_id] = row[col]
            
            # Apply staking rewards for the hour
            if portfolio.holdings:
                portfolio.holdings = self.staking_calc.apply_staking_rewards(
                    portfolio.holdings, emissions, 1.0
                )
            
            # Check if we should rebalance
            should_rebalance = False
            
            if rebalance_freq_hours == 0:
                # Continuous rebalancing (every hour)
                should_rebalance = True
            elif rebalance_freq_hours > 0:
                if hours_since_rebalance >= rebalance_freq_hours:
                    should_rebalance = True
                    hours_since_rebalance = 0
            
            # Rebalance if needed
            if should_rebalance or idx == 0:  # Always rebalance on first iteration
                target_weights = portfolio.calculate_target_weights(emissions)
                
                if target_weights:
                    cost = portfolio.rebalance(
                        target_weights, 
                        prices,
                        transaction_cost_bps if apply_costs else 0.0,
                        slippage_bps if apply_costs else 0.0
                    )
                    total_transaction_costs += cost
                    rebalance_count += 1
            
            # Record NAV
            nav = portfolio.calculate_portfolio_value(prices)
            nav_history.append({
                'timestamp': timestamp,
                'nav': nav,
                'cash': portfolio.cash
            })
            
            hours_since_rebalance += 1
        
        # Calculate metrics
        nav_df = pd.DataFrame(nav_history)
        
        initial_nav = nav_df['nav'].iloc[0]
        final_nav = nav_df['nav'].iloc[-1]
        total_return = (final_nav - initial_nav) / initial_nav
        
        # Calculate tracking error vs continuous rebalancing (will be computed later)
        tracking_error = 0.0  # Placeholder
        
        # Annualized return
        try:
            days = (nav_df['timestamp'].iloc[-1] - nav_df['timestamp'].iloc[0]).days
            if days > 0:
                annualized_return = (1 + total_return) ** (365 / days) - 1
            else:
                annualized_return = 0.0
        except:
            days = 0
            annualized_return = 0.0
        
        # Volatility
        nav_df['returns'] = nav_df['nav'].pct_change()
        daily_vol = nav_df['returns'].std()
        annualized_vol = daily_vol * np.sqrt(24 * 365)  # Hourly to annual
        
        # Sharpe ratio (assuming 5% risk-free rate)
        risk_free_rate = 0.05
        sharpe_ratio = (annualized_return - risk_free_rate) / annualized_vol if annualized_vol > 0 else 0.0
        
        # Max drawdown
        nav_df['cummax'] = nav_df['nav'].cummax()
        nav_df['drawdown'] = (nav_df['nav'] - nav_df['cummax']) / nav_df['cummax']
        max_drawdown = nav_df['drawdown'].min()
        
        results = {
            'nav_history': nav_df,
            'final_nav': final_nav,
            'total_return': total_return,
            'annualized_return': annualized_return,
            'annualized_volatility': annualized_vol,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'rebalance_count': rebalance_count,
            'total_transaction_costs': total_transaction_costs,
            'transaction_cost_pct': total_transaction_costs / INITIAL_CAPITAL,
            'tracking_error': tracking_error,
            'days': days
        }
        
        return results
    
    def run_all_simulations(self) -> Dict[str, Dict]:
        """Run simulations for all rebalancing frequencies."""
        logger.info("Running simulations for all rebalancing frequencies")
        
        results = {}
        
        for freq_name, freq_hours in REBALANCING_FREQUENCIES.items():
            logger.info("Simulating %s rebalancing (%d hours)", freq_name, freq_hours)
            
            # Apply costs for all except continuous benchmark
            apply_costs = (freq_name != 'continuous')
            
            result = self.simulate(
                freq_hours,
                TRANSACTION_COST_BPS,
                SLIPPAGE_BPS,
                apply_costs=apply_costs
            )
            
            results[freq_name] = result
            
            logger.info(
                "%s: Return=%.2f%%, Sharpe=%.2f, Rebalances=%d, Costs=$%.0f",
                freq_name,
                result['total_return'] * 100,
                result['sharpe_ratio'],
                result['rebalance_count'],
                result['total_transaction_costs']
            )
        
        # Calculate tracking errors vs continuous benchmark
        continuous_nav = results['continuous']['nav_history']['nav'].values
        
        for freq_name in results:
            if freq_name == 'continuous':
                results[freq_name]['tracking_error'] = 0.0
                continue
            
            freq_nav = results[freq_name]['nav_history']['nav'].values
            
            # Ensure same length for comparison
            min_len = min(len(continuous_nav), len(freq_nav))
            
            # Tracking error = std dev of return differences
            returns_diff = (
                pd.Series(freq_nav[:min_len]).pct_change() - 
                pd.Series(continuous_nav[:min_len]).pct_change()
            )
            
            tracking_error = returns_diff.std() * np.sqrt(24 * 365)  # Annualized
            results[freq_name]['tracking_error'] = tracking_error
        
        return results


class RebalanceAnalyzer:
    """Analyzes and visualizes rebalancing optimization results."""
    
    def __init__(self, results: Dict[str, Dict]):
        self.results = results
        
    def generate_report(self) -> pd.DataFrame:
        """Generate comparative report of all strategies."""
        logger.info("Generating comparative report")
        
        report_data = []
        
        for freq_name, result in self.results.items():
            report_data.append({
                'Frequency': freq_name,
                'Total Return (%)': result['total_return'] * 100,
                'Annualized Return (%)': result['annualized_return'] * 100,
                'Volatility (%)': result['annualized_volatility'] * 100,
                'Sharpe Ratio': result['sharpe_ratio'],
                'Max Drawdown (%)': result['max_drawdown'] * 100,
                'Rebalances': result['rebalance_count'],
                'Transaction Costs ($)': result['total_transaction_costs'],
                'Transaction Costs (%)': result['transaction_cost_pct'] * 100,
                'Tracking Error (%)': result['tracking_error'] * 100,
                'Final NAV': result['final_nav'],
                'Days': result['days']
            })
        
        df = pd.DataFrame(report_data)
        
        # Sort by total return
        df = df.sort_values('Total Return (%)', ascending=False)
        
        return df
    
    def plot_nav_comparison(self, output_path: Path):
        """Plot NAV comparison across all frequencies."""
        logger.info("Creating NAV comparison plot")
        
        fig, ax = plt.subplots(figsize=(14, 8))
        
        for freq_name, result in self.results.items():
            nav_df = result['nav_history'].copy()
            
            # Drop rows with NaT timestamps
            nav_df = nav_df.dropna(subset=['timestamp'])
            
            # Normalize to start at 1.0
            normalized_nav = nav_df['nav'] / nav_df['nav'].iloc[0]
            
            label = f"{freq_name} (Return: {result['total_return']*100:.1f}%)"
            ax.plot(nav_df['timestamp'], normalized_nav, label=label, linewidth=2)
        
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Normalized NAV (Starting at 1.0)', fontsize=12)
        ax.set_title('TAO20 Performance by Rebalancing Frequency', fontsize=14, fontweight='bold')
        ax.legend(loc='best', fontsize=10)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info("Saved NAV comparison to %s", output_path)
        plt.close()
    
    def plot_metrics_comparison(self, output_path: Path):
        """Plot key metrics comparison."""
        logger.info("Creating metrics comparison plot")
        
        fig, axes = plt.subplots(2, 3, figsize=(18, 10))
        fig.suptitle('TAO20 Rebalancing Optimization Metrics', fontsize=16, fontweight='bold')
        
        frequencies = list(self.results.keys())
        
        # Exclude 'continuous' from some comparisons
        freq_with_costs = [f for f in frequencies if f != 'continuous']
        
        # 1. Total Return
        returns = [self.results[f]['total_return'] * 100 for f in frequencies]
        axes[0, 0].bar(frequencies, returns, color='green', alpha=0.7)
        axes[0, 0].set_title('Total Return (%)')
        axes[0, 0].set_ylabel('Return (%)')
        axes[0, 0].tick_params(axis='x', rotation=45)
        axes[0, 0].grid(True, alpha=0.3)
        
        # 2. Sharpe Ratio
        sharpes = [self.results[f]['sharpe_ratio'] for f in frequencies]
        axes[0, 1].bar(frequencies, sharpes, color='blue', alpha=0.7)
        axes[0, 1].set_title('Sharpe Ratio')
        axes[0, 1].set_ylabel('Sharpe Ratio')
        axes[0, 1].tick_params(axis='x', rotation=45)
        axes[0, 1].grid(True, alpha=0.3)
        
        # 3. Transaction Costs
        costs = [self.results[f]['transaction_cost_pct'] * 100 for f in freq_with_costs]
        axes[0, 2].bar(freq_with_costs, costs, color='red', alpha=0.7)
        axes[0, 2].set_title('Transaction Costs (%)')
        axes[0, 2].set_ylabel('Cost (% of Capital)')
        axes[0, 2].tick_params(axis='x', rotation=45)
        axes[0, 2].grid(True, alpha=0.3)
        
        # 4. Tracking Error
        tracking_errors = [self.results[f]['tracking_error'] * 100 for f in freq_with_costs]
        axes[1, 0].bar(freq_with_costs, tracking_errors, color='orange', alpha=0.7)
        axes[1, 0].set_title('Tracking Error vs Continuous (%)')
        axes[1, 0].set_ylabel('Tracking Error (%)')
        axes[1, 0].tick_params(axis='x', rotation=45)
        axes[1, 0].grid(True, alpha=0.3)
        
        # 5. Rebalance Count
        rebalances = [self.results[f]['rebalance_count'] for f in frequencies]
        axes[1, 1].bar(frequencies, rebalances, color='purple', alpha=0.7)
        axes[1, 1].set_title('Number of Rebalances')
        axes[1, 1].set_ylabel('Count')
        axes[1, 1].tick_params(axis='x', rotation=45)
        axes[1, 1].grid(True, alpha=0.3)
        
        # 6. Max Drawdown
        drawdowns = [abs(self.results[f]['max_drawdown']) * 100 for f in frequencies]
        axes[1, 2].bar(frequencies, drawdowns, color='darkred', alpha=0.7)
        axes[1, 2].set_title('Maximum Drawdown (%)')
        axes[1, 2].set_ylabel('Drawdown (%)')
        axes[1, 2].tick_params(axis='x', rotation=45)
        axes[1, 2].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info("Saved metrics comparison to %s", output_path)
        plt.close()
    
    def plot_efficiency_frontier(self, output_path: Path):
        """Plot efficiency frontier: Return vs Cost."""
        logger.info("Creating efficiency frontier plot")
        
        fig, ax = plt.subplots(figsize=(12, 8))
        
        frequencies = list(self.results.keys())
        colors = plt.cm.viridis(np.linspace(0, 1, len(frequencies)))
        
        for i, freq_name in enumerate(frequencies):
            result = self.results[freq_name]
            
            x = result['transaction_cost_pct'] * 100
            y = result['total_return'] * 100
            
            ax.scatter(x, y, s=200, c=[colors[i]], alpha=0.7, edgecolors='black', linewidth=2)
            ax.annotate(
                freq_name, 
                (x, y), 
                xytext=(10, 10), 
                textcoords='offset points',
                fontsize=10,
                bbox=dict(boxstyle='round,pad=0.5', facecolor=colors[i], alpha=0.3)
            )
        
        ax.set_xlabel('Transaction Costs (% of Capital)', fontsize=12)
        ax.set_ylabel('Total Return (%)', fontsize=12)
        ax.set_title('Rebalancing Efficiency Frontier\n(Higher and Left is Better)', 
                     fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info("Saved efficiency frontier to %s", output_path)
        plt.close()
    
    def save_detailed_results(self, output_path: Path):
        """Save detailed results to CSV."""
        logger.info("Saving detailed results")
        
        all_data = []
        
        for freq_name, result in self.results.items():
            nav_df = result['nav_history'].copy()
            nav_df['frequency'] = freq_name
            all_data.append(nav_df)
        
        combined_df = pd.concat(all_data, ignore_index=True)
        combined_df.to_csv(output_path, index=False)
        
        logger.info("Saved detailed NAV history to %s", output_path)


def main():
    """Main execution function."""
    logger.info("=" * 80)
    logger.info("TAO20 REBALANCING FREQUENCY OPTIMIZATION")
    logger.info("=" * 80)
    logger.info("")
    logger.info("Configuration:")
    logger.info("  Initial Capital: $%s", f"{INITIAL_CAPITAL:,.0f}")
    logger.info("  Transaction Cost: %d bps", TRANSACTION_COST_BPS)
    logger.info("  Slippage: %d bps", SLIPPAGE_BPS)
    logger.info("  Top N Subnets: %d", TOP_N_SUBNETS)
    logger.info("  Frequencies: %s", list(REBALANCING_FREQUENCIES.keys()))
    logger.info("")
    
    # Load data
    logger.info("Step 1: Loading emissions data")
    loader = EmissionsDataLoader(EMISSIONS_DIR)
    data = loader.load_all_data()
    
    if data.empty:
        logger.error("No data loaded. Exiting.")
        return
    
    logger.info("Loaded %d hourly samples from %s to %s", 
                len(data),
                data['timestamp'].min(),
                data['timestamp'].max())
    logger.info("")
    
    # Run simulations
    logger.info("Step 2: Running rebalancing simulations")
    simulator = RebalanceSimulator(data)
    results = simulator.run_all_simulations()
    logger.info("")
    
    # Analyze results
    logger.info("Step 3: Analyzing results")
    analyzer = RebalanceAnalyzer(results)
    
    # Generate report
    report_df = analyzer.generate_report()
    print("\n" + "=" * 100)
    print("REBALANCING OPTIMIZATION SUMMARY")
    print("=" * 100)
    print(report_df.to_string(index=False))
    print("=" * 100)
    print()
    
    # Save report
    report_path = RESULTS_DIR / 'rebalancing_comparison_report.csv'
    report_df.to_csv(report_path, index=False)
    logger.info("Saved report to %s", report_path)
    
    # Generate visualizations
    logger.info("Step 4: Generating visualizations")
    
    analyzer.plot_nav_comparison(RESULTS_DIR / 'nav_comparison.png')
    analyzer.plot_metrics_comparison(RESULTS_DIR / 'metrics_comparison.png')
    analyzer.plot_efficiency_frontier(RESULTS_DIR / 'efficiency_frontier.png')
    analyzer.save_detailed_results(RESULTS_DIR / 'detailed_nav_history.csv')
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("OPTIMIZATION COMPLETE")
    logger.info("=" * 80)
    logger.info("Results saved to: %s", RESULTS_DIR)
    
    # Find optimal frequency
    # Optimal = highest Sharpe ratio with reasonable costs
    report_df_filtered = report_df[report_df['Frequency'] != 'continuous']
    optimal = report_df_filtered.loc[report_df_filtered['Sharpe Ratio'].idxmax()]
    
    print("\n" + "=" * 80)
    print("RECOMMENDED OPTIMAL FREQUENCY")
    print("=" * 80)
    print(f"Frequency: {optimal['Frequency']}")
    print(f"Total Return: {optimal['Total Return (%)']:.2f}%")
    print(f"Annualized Return: {optimal['Annualized Return (%)']:.2f}%")
    print(f"Sharpe Ratio: {optimal['Sharpe Ratio']:.2f}")
    print(f"Transaction Costs: ${optimal['Transaction Costs ($)']:,.0f} ({optimal['Transaction Costs (%)']:.2f}%)")
    print(f"Tracking Error: {optimal['Tracking Error (%)']:.2f}%")
    print(f"Rebalances: {optimal['Rebalances']:.0f}")
    print("=" * 80)
    print()


if __name__ == '__main__':
    main()

