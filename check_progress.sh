#!/bin/bash
# Check progress of subnet price collection

echo "================================================================================"
echo "SUBNET PRICE COLLECTION - PROGRESS CHECK"
echo "================================================================================"
echo ""

# Check if process is running
if pgrep -f "fetch_all_subnet_prices.py" > /dev/null; then
    echo "✅ Status: RUNNING"
else
    echo "⚠️  Status: NOT RUNNING (may be complete or stopped)"
fi

echo ""
echo "Latest progress:"
echo "--------------------------------------------------------------------------------"
tail -20 /Users/alexanderlange/Desktop/ETF/all_prices_collection.log
echo ""
echo "================================================================================"
echo "Full log: /Users/alexanderlange/Desktop/ETF/all_prices_collection.log"
echo "Output file: /Users/alexanderlange/Desktop/ETF/all_subnet_prices.csv"
echo "================================================================================"
