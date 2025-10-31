# TAO20 Unified Backtest System

**Production-Ready Daily NAV Backtesting with APY Integration**

## Overview

This unified backtesting system provides comprehensive analysis of the TAO20 strategy with:

- **Daily price snapshots** for accurate NAV tracking
- **Validator APY calculations** from primary sources (Bittensor SDK)
- **Biweekly rebalancing** based on emission-weighted allocations
- **NAV compounding** that includes both price returns and APY yields
- **Detailed analytics** separating price vs APY contribution

## Key Features

### 1. APY Calculation from Primary Sources

The system calculates validator APY directly from Bittensor SDK data:

```python
APY = (emissions_per_day / total_stake) * 365 * 100
```

Where:
- `emissions_per_day` = emission_per_block × 7200 (blocks per day)
- `total_stake` = sum of all validator stakes in the subnet

This provides **real, on-chain APY data** rather than relying on third-party platforms.

### 2. Daily Granularity

- Fetches daily price snapshots from archive node (~260 days)
- Calculates daily APY from emissions and stake data
- Tracks NAV changes day-by-day for maximum accuracy

### 3. NAV Calculation Formula

```python
# Daily compounding
price_return = (price[day] / price[day-1]) - 1
apy_daily_yield = (APY / 100) / 365
total_daily_return = price_return + apy_daily_yield

NAV[day] = NAV[day-1] × (1 + total_daily_return)
```

**Key Points:**
- Price returns and APY yields are **compounded together**
- NAV starts at 1.0 and continues through rebalancing events
- System tracks both total NAV and price-only NAV for comparison

### 4. Biweekly Rebalancing

- Every 14 days, portfolio rebalances to top 20 subnets by emissions
- Weights recalculated based on emission proportions
- NAV continues (does not reset) - only holdings change

## Quick Start

### Installation

Ensure dependencies are installed:

```bash
cd /Users/alexanderlange/Desktop/ETF
source venv/bin/activate
pip install -r requirements.txt
```

### Basic Usage

Run the full backtest:

```bash
python tao20_unified_backtest.py
```

**Expected Runtime:**
- Daily data fetch for 20 subnets × 260 days: **40-60 minutes**
- NAV calculations: **~1 minute**
- Report generation: **~30 seconds**
- **Total: ~1-1.5 hours** for full backtest

### Configuration

Edit `config.py` to customize:

```python
# Backtest period
START_DATE = datetime(2025, 2, 1)
END_DATE = datetime(2025, 10, 22)

# Rebalancing frequency
REBALANCE_WEEKS = 2  # Every 2 weeks = 14 days

# APY settings
INCLUDE_APY_IN_NAV = True
APY_CALCULATION_METHOD = 'emissions_stake_ratio'
```

Or use environment variables:

```bash
export REBALANCE_WEEKS=2
export INCLUDE_APY_IN_NAV=true
export LOG_LEVEL=INFO
```

## Output Files

The system generates comprehensive output files in `backtest_results/`:

### 1. Full NAV Data CSV

**File:** `tao20_full_nav_data_YYYYMMDD_HHMMSS.csv`

```csv
day,date,nav,price_only_nav,apy_contribution,num_holdings,rebalanced
0,2025-02-01,1.000000,1.000000,0.000000,20,True
1,2025-02-02,1.003245,1.002100,0.001145,20,False
14,2025-02-15,1.045678,1.035000,0.010678,20,True
...
```

**Columns:**
- `day` - Day number (0-based)
- `date` - Calendar date
- `nav` - Total NAV (price + APY)
- `price_only_nav` - NAV from price changes only
- `apy_contribution` - Absolute APY contribution to NAV
- `num_holdings` - Number of subnets held
- `rebalanced` - Boolean flag for rebalancing events

### 2. APY Analysis CSV

**File:** `tao20_apy_analysis_YYYYMMDD_HHMMSS.csv`

```csv
date,nav,price_only_nav,apy_contribution,price_return_pct,apy_return_pct,total_return_pct
2025-02-01,1.000000,1.000000,0.000000,0.00,0.00,0.00
2025-02-02,1.003245,1.002100,0.001145,0.21,0.11,0.32
...
```

**Useful for:**
- Analyzing price vs APY contribution over time
- Understanding return breakdown
- Identifying APY impact on performance

### 3. Performance Chart

**File:** `tao20_performance_YYYYMMDD_HHMMSS.png`

**Features:**
- Main chart: Total NAV vs Price-Only NAV
- Sub-chart: APY contribution over time
- Vertical lines marking rebalancing events
- Date-labeled x-axis

### 4. Returns Breakdown Chart

**File:** `tao20_returns_breakdown_YYYYMMDD_HHMMSS.png`

**Shows:**
- Price Return (%)
- APY Return (%)
- Total Return (%)

As bar chart for easy comparison.

## Data Caching

The system implements intelligent caching to speed up repeated runs:

- Cache location: `data/cache/`
- Cache key includes: date range and subnet list
- Automatically used on subsequent runs
- **Reduces runtime from 1 hour to ~5 minutes** for same parameters

To force fresh data fetch, delete cache:

```bash
rm -rf data/cache/
```

## Understanding the Results

### Example Output

```
Final NAV: 1.125000
  - Price-Only NAV: 1.080000
  - APY Contribution: 0.045000

Total Return: +12.50%
  - Price Return: +8.00%
  - APY Return: +4.50%
```

**Interpretation:**
- Total portfolio gained 12.5% over the period
- 8% came from subnet token price appreciation
- 4.5% came from validator staking rewards (APY)
- APY added meaningful value to the strategy

### APY Contribution Analysis

The system tracks two NAVs:

1. **Total NAV**: Includes both price returns and APY yields
2. **Price-Only NAV**: Only includes token price changes

The difference shows the **exact contribution of APY** to performance.

This is critical for understanding:
- How much value staking rewards add
- Whether APY compensates for price declines
- True cost/benefit of holding subnet tokens

## Performance Metrics

Beyond basic NAV, the system provides:

- **Daily returns** (price + APY separated)
- **Rebalancing impact** (holdings changes)
- **Subnet contribution** (which subnets drove performance)
- **Volatility** (day-to-day NAV changes)

## Technical Architecture

### Main Components

1. **DailyHistoricalDataFetcher** - Fetches daily prices, emissions, stake from archive
2. **APY Calculator** - Computes daily APY from emissions/stake ratio
3. **NAV Calculator** - Compounds price returns with APY yields
4. **Rebalancing Logic** - Updates holdings every 14 days
5. **Visualization Engine** - Creates comprehensive charts

### Data Flow

```
Archive Node → Daily Prices/Emissions/Stake → APY Calculation
                                              ↓
                                    NAV Calculation with Rebalancing
                                              ↓
                                    CSV Outputs + Charts
```

### Error Handling

- Exponential backoff for API retries
- Forward-fill for missing data points
- Graceful degradation if historical emissions unavailable
- Comprehensive logging at each step

## Limitations & Assumptions

### 1. Historical APY Data

**Issue:** Archive node may not preserve historical emissions/stake data.

**Mitigation:** System attempts to fetch historical data but falls back to current values if unavailable.

**Assumption:** Current emissions are a reasonable proxy for historical emissions over the backtest period.

### 2. APY Calculation Simplification

**Assumption:** APY is distributed uniformly to all subnet token holders.

**Reality:** APY is earned by validators; token holders only benefit if they stake.

**Justification:** For index tracking purposes, we model the theoretical maximum return available to participants.

### 3. Rebalancing Costs

**Not Included:**
- Transaction fees
- Slippage
- Price impact

**Reason:** Difficult to model accurately without real execution data.

**Impact:** Actual returns may be slightly lower than backtested results.

## Comparison with Previous System

### Old System (`tao_index_backtest_dynamic.py`)

- Weekly price snapshots
- No APY integration
- Less granular NAV tracking

### New System (`tao20_unified_backtest.py`)

- ✅ Daily price snapshots
- ✅ APY integration from primary sources
- ✅ Comprehensive analytics
- ✅ Caching for faster reruns
- ✅ Price vs APY separation
- ✅ Better visualizations

## Troubleshooting

### Issue: "Archive node timeout"

**Solution:**
```bash
export REQUEST_TIMEOUT=300
export RETRY_ATTEMPTS=5
python tao20_unified_backtest.py
```

### Issue: "Insufficient historical data"

**Cause:** Archive node missing data for some subnets

**Solution:** System automatically skips subnets with < 2 valid data points

### Issue: "APY values are zero"

**Cause:** Historical emissions data not available from archive

**Impact:** NAV will only reflect price returns

**Check logs:** Look for "emissions/stake unavailable" messages

### Issue: Long runtime

**Solutions:**
1. Use cached data (automatic on subsequent runs)
2. Reduce date range in `config.py`
3. Test with fewer subnets first

## Advanced Usage

### Custom Date Range

Test a specific period:

```python
# In config.py
START_DATE = datetime(2025, 9, 1)
END_DATE = datetime(2025, 10, 22)
```

### Different Rebalancing Frequency

Test weekly rebalancing:

```python
REBALANCE_WEEKS = 1  # Weekly instead of biweekly
```

### Disable APY Integration

Compare price-only performance:

```python
INCLUDE_APY_IN_NAV = False
```

(Note: APY will still be calculated and shown for comparison)

### Different Index Sizes

Test TAO10 or TAO30:

```python
# In tao20_unified_backtest.py, main()
TOP_N_SUBNETS = 10  # or 30, or any number
```

## Next Steps

1. **Run Initial Backtest**
   ```bash
   python tao20_unified_backtest.py
   ```

2. **Review Results**
   - Check NAV performance
   - Analyze APY contribution
   - Examine rebalancing impact

3. **Iterate**
   - Adjust rebalancing frequency
   - Test different time periods
   - Compare with benchmarks

4. **Production Deployment**
   - Schedule regular backtests
   - Track strategy performance over time
   - Use insights for live trading decisions

## Support & Documentation

- **Main Script:** `tao20_unified_backtest.py`
- **Configuration:** `config.py`
- **Logs:** `logs/tao20_unified_backtest.log`
- **Cache:** `data/cache/`
- **Results:** `backtest_results/`

## Version History

- **v1.0** (Oct 22, 2025) - Initial unified backtest system
  - Daily price snapshots
  - APY integration from SDK
  - Biweekly rebalancing
  - Comprehensive analytics

---

**Author:** Alexander Lange  
**Date:** October 22, 2025  
**License:** MIT


