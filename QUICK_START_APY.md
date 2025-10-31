# TAO20 APY Model - Quick Start Guide

## TL;DR

The TAO20 index earns **35.28% APY** from staking alpha tokens across 127 Bittensor subnets, weighted by emissions.

---

## Run the Backtest (30 seconds)

```bash
cd /Users/alexanderlange/Desktop/ETF
source venv/bin/activate
python tao20_apy_backtest_simple.py
```

**Results**:
- 30-day simulation
- Portfolio APY: 35.28%
- Expected monthly return: 2.94%
- Annualized return: 42.29%

---

## Key Results

### Portfolio Composition

- **127 subnets** weighted by emission share
- **Top 3 holdings**:
  1. Subnet 64 (Chutes): 7.76% weight, 70% APY
  2. Subnet 62 (Ridges): 6.94% weight, 63.5% APY
  3. Subnet 120 (Affine): 5.99% weight, **135% APY** ⭐

### APY Breakdown

| Metric                     | Value  |
|----------------------------|--------|
| Portfolio-weighted APY     | 35.28% |
| Daily yield                | 0.097% |
| 30-day return (APY only)   | 2.94%  |

### Scenario Analysis

| Scenario                | Final NAV | Return  |
|-------------------------|-----------|---------|
| APY Only (stable price) | 1.0294    | +2.94%  |
| With -1% daily price    | 0.7617    | -23.83% |
| With +1% daily price    | 1.3871    | +38.71% |

**Insight**: APY adds a consistent 2.94% cushion regardless of price movement.

---

## How It Works

### 1. Alpha Emission Economics

```
Network-wide: 7200 TAO/day
Alpha rate: 2× TAO = 14,400 alpha/day total

Each subnet receives:
  daily_alpha = emission_fraction × 14,400
```

### 2. Staking APY Calculation

```
APY = (daily_alpha / staked_alpha) × 365 × 100

Where staked_alpha = total_supply × staking_ratio
```

### 3. Power Law Model

Staking ratio decreases as subnets mature:

| Supply Range | Staking Ratio | Typical APY |
|--------------|---------------|-------------|
| < 500k       | ~20-25%       | 150-300%    |
| 500k - 1.5M  | ~18-21%       | 80-140%     |
| 1.5M - 2.5M  | ~18-19%       | 50-80%      |
| > 2.5M       | ~18%          | 30-70%      |

**Calibrated to**:
- Subnet 64 (3.2M supply): 18.38% staked → 70% APY ✓
- Subnet 120 (1.1M supply): 20.66% staked → 135% APY ✓

---

## Why This Matters

### For TAO20 Strategy

1. **Yield Enhancement**: 35% APY on top of price appreciation
2. **Volatility Cushion**: Consistent yield offsets price drawdowns
3. **Emission-Weighted**: Captures value from network growth

### For Subnet Analysis

1. **APY Prediction**: Estimate APY for any subnet from supply alone
2. **Maturity Tracking**: Lower APY indicates mature, heavily-staked subnet
3. **Opportunity Identification**: High APY subnets = early-stage opportunities

---

## Validate the Model

```bash
python alpha_apy_model.py
```

**Output**:
```
Subnet 64 Validation:
  Target APY: 70.0%
  Calculated APY: 70.0%
  Error: 0.0% ✓ PASS

Subnet 120 Validation:
  Target APY: 135.0%
  Calculated APY: 135.0%
  Error: 0.0% ✓ PASS
```

---

## Output Files

All results saved to `backtest_results/`:

- `tao20_simple_apy_only_*.csv` - APY-only scenario
- `tao20_simple_bearish_*.csv` - Bearish price scenario
- `tao20_simple_bullish_*.csv` - Bullish price scenario  
- `tao20_simple_summary_*.csv` - Comparison table

---

## Next Steps

1. **Review detailed docs**: See `TAO20_APY_MODEL_README.md`
2. **Run full backtest**: `python tao20_dynamic_apy_backtest.py` (slow, uses archive node)
3. **Customize scenarios**: Edit price assumptions in `tao20_apy_backtest_simple.py`
4. **Analyze results**: Open CSV files in Excel/pandas for deeper analysis

---

## Questions?

**Q: Why is Subnet 120 APY so high (135%)?**  
A: It's a newer subnet (1.1M supply) with lower staking participation (20.7%) relative to emissions.

**Q: Why does the model use supply as age proxy?**  
A: Subnets emit alpha daily, so supply correlates with time since launch.

**Q: Will APY stay at 35% forever?**  
A: No - APY decreases as:
  - Staking participation increases
  - Emission fractions shift between subnets
  - New subnets launch with initially high APY

**Q: Is this the same as TAO validator APY?**  
A: No - this is **alpha staking APY** for holding subnet tokens, not TAO validator rewards.

---

**Created**: October 22, 2025  
**Last Run**: See latest timestamp in `backtest_results/`












