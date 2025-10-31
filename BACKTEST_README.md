# TAO20 Index Backtest System

This system backtests the TAO20 index using historical subnet token prices from the Bittensor network via `btcli` archive node.

## Overview

The TAO20 backtest simulates a portfolio starting with 1 TAO allocated across the top 20 subnets according to emission-weighted allocations from September 14, 2025. It tracks the Net Asset Value (NAV) daily by valuing each position at historical prices.

## Key Results (Sept 14 - Oct 12, 2025)

- **Initial NAV**: 1.0000 TAO
- **Final NAV**: 0.8492 TAO  
- **Total Return**: -15.08%
- **Period**: 28 days

### Individual Subnet Performance

| Rank | NetUID | Weight | Allocation | Initial Price | Current Price | Return % |
|------|--------|--------|------------|---------------|---------------|----------|
| 1 | 64 | 15.49% | 0.1549 TAO | 0.10545 | 0.07701 | -26.97% |
| 2 | 120 | 11.50% | 0.1150 TAO | 0.07591 | 0.06606 | -12.98% |
| 3 | 62 | 11.33% | 0.1133 TAO | 0.07554 | 0.06610 | -12.49% |
| 14 | 9 | 2.50% | 0.0250 TAO | 0.01731 | 0.01901 | +9.81% |
| 19 | 33 | 1.82% | 0.0182 TAO | 0.01228 | 0.01762 | +43.42% |

*Only 2 out of 20 subnets showed positive returns during this period.*

### Worst Performers

- **Subnet 93**: -52.18% (worst)
- **Subnet 11**: -44.95%
- **Subnet 123**: -32.73%

### Best Performers

- **Subnet 33**: +43.42% (best)
- **Subnet 9**: +9.81%

## How It Works

### 1. Data Collection

The backtest fetches historical price data using `btcli`:

```bash
btcli subnets price --netuid <NETUID> --interval-hours <HOURS> --network archive
```

For each of the 20 TAO20 constituents, it retrieves:
- Current price
- Historical price (28 days back)
- Price change percentage
- High/low prices

### 2. Position Calculation

Starting with 1 TAO:
1. Allocate capital according to each subnet's weight
2. Calculate initial purchase price (backdated using change %)
3. Compute tokens purchased: `tokens = allocation_tao / initial_price`

### 3. NAV Simulation

For each day from Sept 14 to Oct 12:
- Interpolate prices linearly from initial to current
- Value each position: `value = tokens × price_at_day`
- Sum all positions to get total NAV

### 4. Visualization & Export

Generates:
- **Performance Chart**: NAV over time with statistics
- **Return Chart**: Cumulative return percentage
- **CSV Files**: Daily NAV and position details
- **JSON Summary**: Complete backtest metadata and results

## Files Generated

```
backtest_results/
├── tao20_nav_history_YYYYMMDD_HHMMSS.csv     # Daily NAV values
├── tao20_positions_YYYYMMDD_HHMMSS.csv       # Position details per subnet
└── tao20_backtest_summary_YYYYMMDD_HHMMSS.json  # Complete summary with metadata

tao20_nav_performance.png                     # Visualization chart
```

## Running the Backtest

### Prerequisites

```bash
# Ensure btcli is installed and accessible
which btcli

# Install Python dependencies
pip install -r requirements.txt
```

### Execute

```bash
# Activate virtual environment
source venv/bin/activate

# Run backtest (takes ~15 minutes due to archive node queries)
python tao20_backtest.py
```

### Expected Output

```
================================================================================
TAO20 INDEX BACKTEST
================================================================================
Rebalance Date: 2025-09-14
Initial Capital: 1.0 TAO
Constituents: 20
================================================================================

[Step 1/5] Fetching historical prices from btcli archive node...
[Step 2/5] Calculating initial positions...
[Step 3/5] Simulating NAV history...
[Step 4/5] Generating performance visualization...
[Step 5/5] Exporting results...

================================================================================
BACKTEST COMPLETE
================================================================================
Period: 2025-09-14 to 2025-10-12
Initial NAV: 1.0000 TAO
Final NAV: 0.8492 TAO
Total Return: -15.08%
Max NAV: 1.0000 TAO
Min NAV: 0.8492 TAO
================================================================================
```

## Understanding the Results

### NAV Chart (Top)

Shows the portfolio value over time:
- Orange line: TAO20 Index NAV
- Dashed grey line: Initial value (1 TAO)
- Statistics box shows key metrics

### Cumulative Return Chart (Bottom)

Shows percentage gain/loss:
- Green area: Positive return periods
- Red area: Negative return periods
- The index showed consistent decline over the 28-day period

## Methodology

### Data Source
- **Primary**: `btcli` archive node for historical prices
- **Fallback**: Current price with 0% change assumption if archive fails

### Assumptions
1. Perfect execution at calculated prices
2. No transaction costs or slippage
3. No rebalancing during the period
4. Linear price interpolation between start and end dates

### Limitations
1. Archive node queries are slow (30-60 seconds per subnet)
2. Historical data limited to what's available in archive
3. Linear interpolation may not reflect actual price movements
4. Does not account for:
   - Trading costs
   - Liquidity constraints
   - Rebalancing requirements
   - Token availability

## Customization

### Change Rebalance Date

```python
backtest = TAO20Backtest(rebalance_date="2025-08-01")
```

### Modify Constituents

Edit the `_load_tao20_constituents()` method in `tao20_backtest.py`:

```python
constituents = [
    {"netuid": 64, "weight": 0.20, "rank": 1},
    {"netuid": 120, "weight": 0.15, "rank": 2},
    # ... add more
]
```

### Adjust Initial Capital

```python
self.initial_capital = 10.0  # Start with 10 TAO
```

## Technical Details

### Architecture
- **Language**: Python 3.7+
- **Data Source**: btcli (Bittensor CLI)
- **Visualization**: matplotlib
- **Data Processing**: pandas, numpy

### Performance
- Single run: ~15 minutes (20 subnets × ~45 sec/subnet)
- Archive queries: Most time-consuming step
- Current price fallback: Much faster (~5 seconds)

### Error Handling
- Timeout protection (90 seconds per query)
- Fallback to current prices if historical data unavailable
- Graceful handling of missing subnets
- Comprehensive logging throughout

## Interpretation

### Portfolio Insights

1. **Concentration Risk**: Top 3 subnets = 38% of portfolio
2. **Market Correlation**: Most subnets declined together
3. **Outliers**: Subnets 33 and 9 showed resilience
4. **Volatility**: Subnet 93 had extreme -52% decline

### Index Performance

The -15.08% return suggests:
- General market downturn in subnet tokens
- Emission weighting may not protect against broad declines  
- Diversification helped (vs. -52% worst case)
- Regular rebalancing might improve performance

## Next Steps

1. **Extended Backtest**: Run for longer periods to assess long-term performance
2. **Rebalancing Strategy**: Test monthly/quarterly rebalancing
3. **Comparison**: Compare against individual subnet performance
4. **Risk Metrics**: Add Sharpe ratio, max drawdown, volatility
5. **What-if Analysis**: Test different weighting schemes

## Support

For issues or questions:
1. Check `btcli` is installed and archive node is accessible
2. Verify network connectivity
3. Review logs for specific errors
4. Ensure all dependencies are installed

## License

MIT License - See main project README

---

**Last Updated**: October 12, 2025
**Backtest Period**: September 14 - October 12, 2025 (28 days)


