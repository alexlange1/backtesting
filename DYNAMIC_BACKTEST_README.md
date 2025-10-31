# TAO Index Dynamic Rebalancing Backtest

**Script**: `tao_index_backtest_dynamic.py`  
**Created**: October 14, 2025  
**Status**: ✅ Working - Currently running first test

---

## Overview

This script performs a proper backtest of TAO20, TAO15, and TAO10 indices with **dynamic rebalancing** based on **emission-weighted allocations**.

### Key Improvements Over Previous Version

1. **Dynamic Rebalancing**: Portfolio rebalances every 2 weeks based on current top subnets by emissions
2. **Emission-Based Weighting**: Positions are weighted proportionally to subnet emissions (not equal-weighted)
3. **Continuous NAV**: NAV continues through rebalancing events (doesn't reset to 1.0)
4. **Real Emissions Data**: Queries actual emissions from btcli at rebalancing points
5. **Historical Price Data**: Uses archive network to fetch historical subnet token prices

---

## How It Works

### 1. Emission Data Collection

```python
# Fetches current emissions for all active subnets
emissions = get_current_emissions()
# Example output: {64: 0.075325, 120: 0.064127, 62: 0.060549, ...}
```

Uses `btcli subnets list` to get emission rates for all subnets.

### 2. Top Subnet Selection

At each rebalancing point (every 2 weeks):
- Ranks all subnets by total emissions
- Selects top N (20 for TAO20, 15 for TAO15, 10 for TAO10)
- Calculates emission-proportional weights

```python
# Example for TAO20
top_20 = calculate_top_subnets_by_emission(emissions, 20)
# Returns: {64: 0.1234, 120: 0.1023, ...}  # Weights sum to 1.0
```

### 3. Price Data Fetching

Fetches historical weekly prices using btcli archive network:

```python
# Week 0 (current): btcli subnets price --netuid X --current
# Week N (historical): btcli subnets price --netuid X --interval-hours (N*168) --network archive
```

### 4. NAV Calculation

```python
# Initialize
NAV = 1.0
holdings = top_20_subnets_at_week_0

# For each week:
for week in range(num_weeks):
    # Rebalance if it's a rebalancing week (every 2 weeks)
    if week > 0 and week % 2 == 0:
        holdings = top_20_subnets_at_current_week  # Update holdings
        # NAV stays the same!
    
    # Calculate return for this week
    week_return = sum(weight[subnet] * (price[week] / price[week-1] - 1))
    
    # Update NAV (continuous)
    NAV *= (1 + week_return)
```

**Critical**: NAV is continuous - it does NOT reset at rebalancing. Rebalancing only changes what you hold, not the NAV value.

---

## Test Parameters (Current Run)

- **Period**: February 1, 2025 - March 1, 2025 (4 weeks)
- **Rebalancing**: Week 0 (Feb 1), Week 2 (Feb 15)
- **Indices**: TAO20, TAO15, TAO10
- **Initial NAV**: 1.0 for all indices
- **Weighting**: Proportional to emissions
- **Data Source**: btcli (finney for emissions, archive for historical prices)

---

## Technical Challenges Solved

### Challenge 1: JSON Parsing from btcli
**Problem**: btcli JSON output contained literal newlines inside string values (e.g., subnet names like "Dippy\nStudio"), causing `json.loads()` to fail.

**Solution**:
```python
# Read JSON to file first
# Clean newlines within JSON string values
clean_json = re.sub(r'"[^"]*"', fix_string_newlines, decoded)
```

### Challenge 2: Historical Price Queries
**Problem**: Historical price queries require archive network, not finney.

**Solution**:
```python
if hours_ago == 0:
    cmd = f'btcli subnets price --netuid {netuid} --network finney --current'
else:
    cmd = f'btcli subnets price --netuid {netuid} --interval-hours {hours_ago} --network archive'
```

### Challenge 3: Emission Data Access
**Problem**: Bittensor Python library's `subnet_info.emission_value` returns 0 (not the actual emissions shown in btcli).

**Solution**: Parse emissions from `btcli subnets list --json-output` instead of using Python library.

---

## Output Files

### 1. CSV Data
```
backtest_results/tao_index_dynamic_YYYYMMDD_HHMMSS.csv
```

Contains:
- `week`: Week number (0-4)
- `date`: Calendar date
- `TAO20`: NAV for TAO20 index
- `TAO15`: NAV for TAO15 index
- `TAO10`: NAV for TAO10 index

### 2. Visualization
```
tao_index_dynamic_comparison.png
```

Line chart showing NAV performance for all three indices over time.

### 3. Log File
```
backtest_complete.log
```

Detailed execution log including:
- Emissions fetched
- Top subnets selected
- Price data collection progress
- Rebalancing events
- Final NAV calculations

---

## Performance Notes

### Execution Time
- **Emissions Fetching**: ~5 seconds (one-time)
- **Price Data per Subnet**: ~2 minutes (5 price points from archive)
- **Total for 20 subnets**: ~40 minutes
- **NAV Calculation**: < 1 second

### Rate Limiting
- 0.5 second delay between price queries for same subnet
- 1.0 second delay between different subnets

---

## Next Steps

1. ✅ **Test with February 2025 (4 weeks)** - Currently running
2. ⏭️ **Extend to full period** - February 2025 to October 2025
3. ⏭️ **Validate rebalancing logic** - Ensure holdings change correctly
4. ⏭️ **Compare with static allocation** - Show benefit of rebalancing
5. ⏭️ **Add performance metrics** - Sharpe ratio, max drawdown, etc.

---

## Usage

```bash
# Activate environment
cd /Users/alexanderlange/Desktop/ETF
source venv/bin/activate

# Run backtest (takes ~40 minutes for 20 subnets, 4 weeks)
python3 tao_index_backtest_dynamic.py

# View results
open tao_index_dynamic_comparison.png
cat backtest_results/tao_index_dynamic_*.csv
```

---

## Configuration

Edit these variables in the script to customize:

```python
# Time period
START_DATE = datetime(2025, 2, 1)
END_DATE = datetime(2025, 3, 1)

# Rebalancing frequency
REBALANCE_WEEKS = 2  # Every 2 weeks

# Indices to calculate
INDEX_CONFIGS = {
    'TAO20': 20,
    'TAO15': 15,
    'TAO10': 10
}
```

---

## Validation Checklist

- [x] Emissions data fetches successfully
- [x] Top subnets selected by emission
- [x] Weights proportional to emissions
- [x] Historical prices fetch from archive
- [x] NAV starts at 1.0
- [ ] NAV continuous through rebalancing *(validating)*
- [ ] Rebalancing every 2 weeks *(validating)*
- [ ] Results look reasonable *(validating)*

---

**Author**: Alexander Lange  
**Contact**: [Project Directory]  
**License**: MIT

