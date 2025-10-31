#!/usr/bin/env python3
import json

# Load Feb 27 data
with open('data/emissions_v2/emissions_v2_20250227.json') as f:
    data = json.load(f)

print("Top-level keys:", list(data.keys()))
print("\n" + "="*80)

# Check validators structure
validators = data.get('validators', {})
print(f"\nValidators type: {type(validators)}")

if isinstance(validators, dict):
    sample_keys = list(validators.keys())[:3]
    print(f"Sample validator keys: {sample_keys}")
    
    if sample_keys:
        print(f"\nSample validator data for {sample_keys[0]}:")
        print(json.dumps(validators[sample_keys[0]], indent=2)[:800])
elif isinstance(validators, list):
    print(f"Validators is a list with {len(validators)} items")
    if validators:
        print(f"\nFirst validator:")
        print(json.dumps(validators[0], indent=2)[:800])









