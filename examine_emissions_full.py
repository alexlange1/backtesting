#!/usr/bin/env python3
"""Examine emissions data structure comprehensively"""
import json
import glob

# Get a sample file
files = sorted(glob.glob('data/emissions_v2/*.json'))
print(f"Total files: {len(files)}")
print(f"Date range: {files[0].split('_')[-1][:8]} to {files[-1].split('_')[-1][:8]}")

# Load one file
with open(files[13]) as f:  # Feb 27
    data = json.load(f)

print(f"\nFile: {files[13]}")
print("="*80)

# Show all top-level keys
print("\nTop-level keys:")
for key in data.keys():
    print(f"  - {key}: {type(data[key])}")

# Check emissions
print("\nEmissions data:")
emissions = data['emissions']
print(f"  Subnets: {list(emissions.keys())[:10]}...")
print(f"  Sample values: {[emissions[k] for k in list(emissions.keys())[:3]]}")

# Check validators in detail
print("\nValidators data:")
validators = data['validators']
sample_subnet = list(validators.keys())[0]
print(f"  Sample subnet {sample_subnet}:")
print(f"  Keys: {list(validators[sample_subnet].keys())}")
print(json.dumps(validators[sample_subnet], indent=2)[:500])

# Look for any price-related fields
print("\n" + "="*80)
print("Searching for price-related data...")

def search_dict(d, search_terms=['price', 'cost', 'alpha', 'tao'], prefix=''):
    """Recursively search for keys containing search terms"""
    found = []
    if isinstance(d, dict):
        for k, v in d.items():
            k_lower = str(k).lower()
            if any(term in k_lower for term in search_terms):
                found.append(f"{prefix}.{k}" if prefix else k)
            if isinstance(v, (dict, list)):
                found.extend(search_dict(v, search_terms, f"{prefix}.{k}" if prefix else k))
    elif isinstance(d, list) and d:
        found.extend(search_dict(d[0], search_terms, f"{prefix}[0]"))
    return found

price_fields = search_dict(data)
if price_fields:
    print(f"Found fields: {price_fields}")
else:
    print("No direct price fields found")

print("\nConclusion: Need to calculate alpha prices from emissions + supply data")
print("Or fetch prices from blockchain using btcli subnet price")









