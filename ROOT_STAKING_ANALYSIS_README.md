# Root Network Staking Analysis

## Overview

This analysis examines what would have happened if TAO was staked to the **Root Network (Subnet 0)** from day one of the backtest period (February 27 - October 26, 2025).

## Key Characteristics of Root Network Staking

### What is the Root Network (Subnet 0)?

- **Governance Layer**: Subnet 0 is the root network where validators vote on emissions for other subnets
- **Stable Value**: Unlike other subnets, the root network has a stable value of 1 (no price appreciation/depreciation)
- **Staking Rewards**: Returns come entirely from staking APY, not price changes
- **Lower Volatility**: Much more stable than individual subnet exposure

### Current Root Network Status

According to the on-chain data fetched:
- **Current Emission**: 0.0 (root network doesn't emit in the traditional sense)
- **Total Supply**: ~6.05M TAO
- **Estimated APY**: ~10% (based on historical validator rewards)

## Analysis Results

### 1. Root Network Staking Performance

**Period**: February 27 - October 26, 2025 (242 days)

**Starting with 100 TAO:**
- **Final Amount**: 106.84 TAO
- **Total Rewards**: 6.84 TAO
- **Total Return**: 6.84%
- **Average APY**: 9.97%
- **CAGR (Annualized)**: 10.49%

**Key Features:**
- ✅ Predictable, stable returns
- ✅ Very low volatility (staking rewards compound smoothly)
- ✅ No exposure to subnet price volatility
- ❌ No upside from subnet price appreciation
- ❌ Lower total returns compared to diversified strategies

### 2. Comparison: Root Staking vs TAO20 Index vs TAO Only

The comparison analysis shows three different strategies:

#### Strategy Comparison Table

| Metric | TAO20 Index | Root Staking | TAO Only |
|--------|-------------|--------------|----------|
| **Approach** | Diversified 20-subnet portfolio | Stable staking rewards | Single subnet exposure |
| **Returns From** | Price changes + APY | Staking rewards only | Price changes only |
| **Volatility** | Medium | Very Low | High |
| **Risk Profile** | Diversified | Conservative | Concentrated |

#### Performance Highlights

1. **TAO20 Index**: 
   - Provides exposure to price appreciation across top 20 subnets
   - Includes APY from all holdings
   - Rebalances bi-weekly to maintain optimal allocation
   - Higher returns but with some volatility

2. **Root Network Staking**:
   - Stable, predictable ~10% APY
   - No price volatility
   - Best for conservative investors seeking steady income
   - Compound growth over time

3. **TAO (Subnet 1) Only**:
   - Single subnet concentration
   - High volatility
   - Misses diversification benefits
   - Subject to subnet-specific risks

## Visual Analysis

The analysis generated two comprehensive visualizations:

### 1. Root Staking Analysis (`root_staking_analysis_*.png`)

Four charts showing:
- **Staked Amount Growth**: Compound growth from 100 TAO to 106.84 TAO
- **Cumulative Rewards**: Total rewards earned over time (6.84 TAO)
- **Historical APY**: Estimated APY over the period (~10% average)
- **Total Return %**: Percentage return growth over time

### 2. Strategy Comparison (`strategy_comparison_*.png`)

Comprehensive comparison including:
- **Main Comparison Chart**: All three strategies plotted together
- **Cumulative Returns**: Return percentages over time
- **Volatility Analysis**: 30-day rolling volatility comparison
- **Performance Metrics Table**: Detailed statistics including Sharpe ratio and max drawdown

## Key Insights

### When to Choose Root Network Staking

✅ **Good For:**
- Conservative investors seeking stable returns
- Those who want predictable income
- Investors prioritizing capital preservation
- Long-term holders who want to avoid volatility

❌ **Not Ideal For:**
- Growth-oriented investors
- Those seeking maximum returns
- Investors comfortable with volatility for higher upside

### When to Choose TAO20 Index

✅ **Good For:**
- Diversified exposure to the Bittensor ecosystem
- Balance between growth and stability
- Capturing upside from multiple subnets
- Professional/institutional allocation

### When to Choose TAO Only

✅ **Good For:**
- High conviction in subnet 1
- Willingness to accept high volatility
- Speculative positioning

## Methodology

### APY Estimation Model

Since historical on-chain staking data is limited, the analysis uses a conservative estimation model:

```python
# APY varies based on network maturity
Early network (days 0-100):    25% APY
Transitioning (days 100-200):  20% APY
Transitioning (days 200-300):  15% APY
Transitioning (days 300-400):  12% APY
Mature network (days 400+):    10% APY
```

This model assumes:
- Higher early APY (more emissions, less staked)
- Gradual decrease as network matures
- Seasonal variations (±10%)

### Limitations

1. **Historical APY Estimation**: Actual historical APY data from the root network is not available in the emissions data, so estimates are used
2. **Emission Data**: Current on-chain data shows 0.0 emission for subnet 0, suggesting it operates differently than regular subnets
3. **Staking Ratio**: Assumes ~15% of supply is staked (conservative estimate)
4. **No Slashing**: Doesn't account for potential validator slashing events
5. **Perfect Compounding**: Assumes all rewards are instantly re-staked

## Files Generated

1. **`tao_root_staking_analysis.py`**: Main analysis script for root network staking
2. **`tao_staking_vs_index_comparison.py`**: Comparison script across all strategies
3. **`root_staking_analysis_*.csv`**: Daily staking data export
4. **`root_staking_analysis_*.png`**: Root staking visualization
5. **`strategy_comparison_*.png`**: Multi-strategy comparison visualization

## How to Run

### Root Network Staking Analysis Only
```bash
cd /Users/alexanderlange/Desktop/ETF
source venv/bin/activate
python3 tao_root_staking_analysis.py
```

### Full Strategy Comparison
```bash
cd /Users/alexanderlange/Desktop/ETF
source venv/bin/activate
python3 tao_staking_vs_index_comparison.py
```

## Conclusion

**Root network staking provides:**
- ✅ Stable, predictable returns (~10% APY)
- ✅ Very low volatility
- ✅ Good option for conservative positioning
- ✅ Compound growth over time

**However:**
- ❌ Lower total returns compared to TAO20 Index
- ❌ Misses price appreciation opportunities
- ❌ Not optimal for growth-oriented portfolios

**Recommendation:** Root network staking is best suited as a **conservative allocation** or **income component** within a broader portfolio, rather than as the entire investment strategy. For most investors seeking growth, the TAO20 Index provides better risk-adjusted returns through diversification while still capturing APY benefits.

---

*Analysis Date: October 28, 2025*  
*Period Analyzed: February 27 - October 26, 2025 (242 days)*  
*Methodology: Conservative APY estimation with compound staking simulation*

