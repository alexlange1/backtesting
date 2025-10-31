# TAO20 Unified Backtest System

**The complete TAO20 emission-weighted index backtest with dynamic alpha staking APY - all in one script.**

---

## 🚀 Quick Start

```bash
cd /Users/alexanderlange/Desktop/ETF
source venv/bin/activate

# Run 30-day backtest (fast, ~10 seconds)
python tao20_unified_backtest.py --mode simple --days 30

# Validate APY model
python tao20_unified_backtest.py --validate

# Run historical backtest with real prices (slow, 5+ minutes)
python tao20_unified_backtest.py --mode historical --days 7
```

---

## 📋 What's Included

This **single script** (`tao20_unified_backtest.py`) contains:

1. ✅ **Alpha APY Model** - Power law calibrated to 70% (subnet 64) and 135% (subnet 120)
2. ✅ **Data Fetching** - Uses `btcli` for emissions and supply
3. ✅ **Simple Backtest** - Fast simulation with scenario analysis
4. ✅ **Historical Backtest** - Real price data from archive node
5. ✅ **Emission Weighting** - TAO20 strategy implementation
6. ✅ **Command-Line Interface** - Easy to use with options

---

## 🎯 Features

### Dynamic APY Modeling

- **Fluctuates with subnet launch date** (newer = higher APY)
- **Based on supply as age proxy** (correlates with maturity)
- **Power law calibration** (0% error on known data points)
- **Realistic economics** (staking ratio decreases as subnets mature)

### Emission-Based Weighting

- **127 active subnets** in current portfolio
- **Portfolio APY: 35.28%** (weighted average)
- **Top holdings**:
  - Subnet 64 (Chutes): 7.76% weight, 70.0% APY
  - Subnet 62 (Ridges): 6.94% weight, 63.5% APY
  - Subnet 120 (Affine): 5.99% weight, 134.9% APY

### Multiple Backtest Modes

**Simple Mode** (fast):
- Simulates APY compounding over N days
- Tests multiple price scenarios (neutral, bearish, bullish)
- Completes in ~10 seconds
- Perfect for quick analysis

**Historical Mode** (slow):
- Fetches real historical prices from archive node
- Combines actual price changes + APY yields
- Takes 5+ minutes due to blockchain queries
- Use for detailed validation

---

## 📊 Results (30-Day Backtest)

| Scenario                | Final NAV | Total Return | APY Contribution |
|-------------------------|-----------|--------------|------------------|
| APY Only (no price)     | 1.0294    | **+2.94%**   | +2.94%           |
| Bearish (-1% daily)     | 0.7617    | -23.83%      | +2.94%           |
| Bullish (+1% daily)     | 1.3871    | +38.71%      | +2.94%           |

**Key Insight**: APY provides a **consistent 2.94% monthly cushion** regardless of price volatility! 🛡️

---

## 🛠️ Usage

### Validate APY Model

```bash
python tao20_unified_backtest.py --validate
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

### Run Simple Backtest

```bash
# 30 days (default)
python tao20_unified_backtest.py --mode simple --days 30

# 90 days
python tao20_unified_backtest.py --mode simple --days 90

# 365 days (full year)
python tao20_unified_backtest.py --mode simple --days 365
```

**Output Files**:
- `backtest_results/tao20_simple_apy_only_*.csv`
- `backtest_results/tao20_simple_bearish_*.csv`
- `backtest_results/tao20_simple_bullish_*.csv`
- `backtest_results/tao20_simple_summary_*.csv`

### Run Historical Backtest

```bash
# 7 days (recommended for speed)
python tao20_unified_backtest.py --mode historical --days 7

# 30 days (slow, ~30+ minutes)
python tao20_unified_backtest.py --mode historical --days 30
```

**Output Files**:
- `backtest_results/tao20_historical_*.csv`

**Note**: Historical mode queries the Bittensor archive node for each subnet at each daily interval, which is slow. Start with 7 days to test.

---

## 📈 Understanding the Results

### Portfolio Metrics

- **Portfolio-weighted APY**: 35.28%
  - Calculated from emission-weighted average of subnet APYs
  - Higher emission subnets contribute more to portfolio APY

- **Daily Yield**: 0.097%
  - Expected daily return from alpha staking
  - Compounds continuously in the backtest

- **Monthly Return (APY only)**: 2.94%
  - Pure APY contribution over 30 days
  - Independent of price movements

### Top Contributors

| Subnet | Weight | APY    | APY Contribution |
|--------|--------|--------|------------------|
| 120    | 5.99%  | 134.9% | **8.08%**        |
| 64     | 7.76%  | 70.0%  | 5.43%            |
| 62     | 6.94%  | 63.5%  | 4.41%            |

Subnet 120 (Affine) is the **highest APY contributor** despite not being the largest holding!

### CSV Output Format

**Simple Mode**:
```csv
day,date,nav,price_only_nav,apy_only_nav,weighted_apy,daily_apy_yield,daily_price_return
1,2025-09-23,1.0010,1.0000,1.0010,35.28,0.0010,0.0000
2,2025-09-24,1.0020,1.0000,1.0020,35.28,0.0010,0.0000
...
```

**Historical Mode**:
```csv
date,nav,price_only_nav,price_return,apy_return,total_return
2025-10-15,1.0012,1.0005,0.0005,0.0007,0.0012
2025-10-16,1.0025,1.0011,0.0006,0.0008,0.0014
...
```

---

## 🔬 Technical Details

### APY Calculation Formula

```
APY = (daily_alpha_emissions / staked_alpha) × 365 × 100

Where:
  daily_alpha_emissions = emission_fraction × 7200 × 2
  staked_alpha = total_supply × staking_ratio(supply)
  
  staking_ratio(supply) = a × supply^b  (power law)
```

### Calibration

Using **reverse engineering** from known APY values:

1. **Subnet 64**: 70% APY → staking ratio = 18.38%
2. **Subnet 120**: 135% APY → staking ratio = 20.66%

Power law parameters:
```python
b = log(0.1838 / 0.2066) / log(3.166 / 1.129) = -0.1239
a = 0.2066 / (1.129 ^ -0.1239) = 0.2283
```

Result: **0% error** on both calibration points ✓

### Data Sources

1. **Emissions & Supply**: `btcli subnets list --json-output`
   - More reliable than SDK (which returns 0 for emissions)
   - Provides subnet names, emissions, supply, etc.

2. **Historical Prices**: Archive node `AlphaValues` storage
   - Returns `[tau_in, alpha_in]` bonding curve reserves
   - Price = `tau_in / alpha_in`

### Assumptions

- **Network emits 7200 TAO/day** (1 TAO/block)
- **Alpha emission is 2× TAO rate** (14,400 alpha/day total)
- **Staking ratio decreases with maturity** (supply inflation > staking growth)
- **No transaction costs or slippage** (simplified model)

---

## 📁 File Structure

```
/Users/alexanderlange/Desktop/ETF/
├── tao20_unified_backtest.py     ← Main script (all-in-one)
├── README_UNIFIED.md             ← This file
├── backtest_results/             ← CSV output directory
│   ├── tao20_simple_apy_only_*.csv
│   ├── tao20_simple_bearish_*.csv
│   ├── tao20_simple_bullish_*.csv
│   ├── tao20_simple_summary_*.csv
│   └── tao20_historical_*.csv
└── venv/                         ← Python virtual environment
```

**Legacy files** (still available but superseded by unified script):
- `alpha_apy_model.py` - Standalone APY model
- `tao20_apy_backtest_simple.py` - Simple backtest only
- `tao20_dynamic_apy_backtest.py` - Historical backtest only

---

## 🎓 Examples

### Example 1: Quick Validation

```bash
python tao20_unified_backtest.py --validate
```

Use this to verify the APY model is working correctly.

### Example 2: Monthly Performance

```bash
python tao20_unified_backtest.py --mode simple --days 30
```

Shows expected monthly returns under different price scenarios.

### Example 3: Yearly Projection

```bash
python tao20_unified_backtest.py --mode simple --days 365
```

Projects full-year performance with APY compounding.

### Example 4: Real Price Data

```bash
python tao20_unified_backtest.py --mode historical --days 7
```

Uses actual historical prices from the last week.

---

## 🔍 Analyzing Results

### In Python/Pandas

```python
import pandas as pd

# Load results
df = pd.read_csv('backtest_results/tao20_simple_apy_only_20251022_153847.csv')

# Plot NAV over time
import matplotlib.pyplot as plt
plt.plot(df['day'], df['nav'])
plt.xlabel('Day')
plt.ylabel('NAV')
plt.title('TAO20 NAV Growth (APY Only)')
plt.show()

# Calculate daily returns
df['daily_return'] = df['nav'].pct_change()
print(f"Average daily return: {df['daily_return'].mean()*100:.3f}%")
print(f"Volatility (std dev): {df['daily_return'].std()*100:.3f}%")
```

### In Excel

1. Open `tao20_simple_summary_*.csv`
2. Create a chart comparing the three scenarios
3. Calculate:
   - Sharpe ratio = (return - risk_free_rate) / volatility
   - Maximum drawdown
   - Recovery time

---

## ❓ FAQ

**Q: Why is the simple mode so much faster?**  
A: It doesn't query the archive node for historical prices - it just simulates APY compounding with assumed price changes.

**Q: Which mode should I use?**  
A: Use **simple mode** for quick analysis and scenario testing. Use **historical mode** when you need to validate against actual price data.

**Q: Can I change the calibration points?**  
A: Yes! Edit the `CALIBRATION_POINTS` dictionary in the `AlphaAPYModel` class.

**Q: How often should I rerun this?**  
A: Rerun weekly to track:
- Emission changes (as subnets gain/lose share)
- Supply growth (affects APY)
- New subnet launches

**Q: What if a subnet stops emitting?**  
A: It will be automatically excluded (emission = 0 filter).

**Q: Does this account for TAO validator rewards?**  
A: No - this models **alpha staking APY** only, not TAO validator rewards.

---

## 🚨 Limitations

1. **APY is not constant** - it fluctuates as:
   - Staking participation changes
   - Emission fractions shift
   - New subnets launch

2. **No rebalancing costs** - real-world would have:
   - Transaction fees
   - Slippage in bonding curves
   - Gas costs

3. **Simplified price model** - simple mode assumes:
   - Constant daily price change
   - No volatility clustering
   - No correlation between subnets

4. **Archive node dependency** - historical mode requires:
   - Stable connection to archive endpoint
   - Full historical data availability
   - Significant time for queries

---

## 📞 Support

For questions or issues:
1. Check the validation first: `python tao20_unified_backtest.py --validate`
2. Review output logs for error messages
3. Test with fewer days if timing out
4. Contact: Alexander Lange

---

## 📝 Changelog

**v1.0 - October 22, 2025**
- ✅ Initial unified release
- ✅ Integrated APY model with power law calibration
- ✅ Simple and historical backtest modes
- ✅ Command-line interface
- ✅ Multiple scenario support
- ✅ CSV export functionality

---

**Created**: October 22, 2025  
**Last Updated**: October 22, 2025  
**Version**: 1.0












