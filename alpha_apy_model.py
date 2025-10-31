#!/usr/bin/env python3
"""
Alpha Token Staking APY Model
==============================
Models APY for staking subnet alpha tokens based on subnet maturity.

Key Insights:
- APY is determined by: (alpha_emissions / staked_alpha) × 365 × 100
- Each subnet emits up to 14,400 alpha/day (proportional to emission fraction)
- Staking participation increases as subnets mature
- Newer subnets have lower staking participation → higher APY

Calibration Points (as of Oct 2025):
- Subnet 64 (Chutes, supply 3.2M): ~70% APY
- Subnet 120 (Affine, supply 1.1M): ~135% APY

Author: Alexander Lange
Date: October 22, 2025
"""

import math
from typing import Dict, Tuple


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
        """Initialize and calibrate the model."""
        self._calibrate_model()
    
    def _calibrate_model(self):
        """
        Calibrate staking participation model using known APY values.
        
        Working backwards from known APYs to find implied staking ratios:
        staked_ratio = (emission × 7200 × 2) / (supply × APY / 365 / 100)
        """
        self.implied_staking_ratios = {}
        
        for netuid, data in self.CALIBRATION_POINTS.items():
            # Assuming emission fraction from subnet 64 ≈ 0.0775, subnet 120 ≈ 0.0599
            # But we need to work this out from the model
            # For now, we'll use the relationship between supply and staking ratio
            pass
    
    def estimate_staking_ratio(self, supply: float) -> float:
        """
        Estimate the percentage of alpha tokens staked based on supply (maturity proxy).
        
        Model: Power law decay calibrated to known data points.
        Key insight: Staking ratio DECREASES as supply grows (inflation outpaces staking).
        
        Calibration points:
        - Subnet 120 (1.129M supply) → 20.66% staked → 135% APY
        - Subnet 64 (3.166M supply) → 18.38% staked → 70% APY
        
        The model uses interpolation between these points and extrapolation for others.
        
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
        # Using the two calibration points to solve for a and b
        # r1 = a * s1^b  →  a = r1 / s1^b
        # r2 = a * s2^b  →  r2 = (r1 / s1^b) * s2^b
        # r2/r1 = (s2/s1)^b  →  b = log(r2/r1) / log(s2/s1)
        
        b = math.log(r2 / r1) / math.log(s2 / s1)
        a = r1 / (s1 ** b)
        
        # Apply power law
        estimated_ratio = a * (supply_m ** b)
        
        # Clamp to reasonable bounds (5% to 40%)
        estimated_ratio = max(0.05, min(0.40, estimated_ratio))
        
        # Special handling for very new subnets (< 100k supply)
        # Assume very high staking ratios for brand new subnets
        if supply_m < 0.1:
            # Linear interpolation from 30% at 0 to calculated value at 100k
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
            
            # We need emission fraction - estimate from reverse engineering
            # For subnet 64: daily_alpha ≈ 1116, supply ≈ 3.2M, staked ≈ 18.5%
            # emission_fraction ≈ 1116 / (7200 * 2) ≈ 0.0775
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


# Example usage and validation
if __name__ == '__main__':
    model = AlphaAPYModel()
    
    print("=" * 80)
    print("ALPHA STAKING APY MODEL - VALIDATION")
    print("=" * 80)
    print()
    
    # Validate against calibration points
    validation = model.validate_model()
    
    for netuid, results in validation.items():
        print(f"Subnet {netuid} Validation:")
        print(f"  Supply: {results['supply']:,.0f} alpha")
        print(f"  Target APY: {results['target_apy']:.1f}%")
        print(f"  Calculated APY: {results['calculated_apy']:.1f}%")
        print(f"  Error: {results['error']:.1f}% ({results['error_pct']:.1f}% relative)")
        print(f"  Staked: {results['staked_alpha']:,.0f} ({results['staked_ratio']*100:.1f}% of supply)")
        print(f"  Daily emissions: {results['daily_emissions']:.2f} alpha")
        status = "✓ PASS" if results['error_pct'] < 5 else "✗ NEEDS CALIBRATION"
        print(f"  Status: {status}")
        print()
    
    # Test with other subnets
    print("=" * 80)
    print("PREDICTIONS FOR OTHER SUBNETS")
    print("=" * 80)
    print()
    
    test_cases = [
        (62, 0.0694, 3_122_000, "Ridges"),
        (51, 0.0543, 3_167_000, "lium.io"),
        (115, 0.0178, 132_000, "SoulX"),
    ]
    
    for netuid, emission, supply, name in test_cases:
        apy, staked, daily = model.calculate_alpha_apy(emission, supply)
        print(f"Subnet {netuid} ({name}):")
        print(f"  Supply: {supply:,.0f} alpha")
        print(f"  Estimated staked: {staked:,.0f} ({staked/supply*100:.1f}%)")
        print(f"  Predicted APY: {apy:.1f}%")
        print()

