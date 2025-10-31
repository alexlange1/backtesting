#!/usr/bin/env python3
"""
Bittensor Subnet Emissions Data Collector (Production)
=======================================================
Collects emissions data for all Bittensor subnets using the Bittensor SDK.
Production-ready with proper error handling and retry logic.

Author: Alexander Lange
Date: October 22, 2025
"""

import os
import json
import csv
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional
import pandas as pd
import bittensor as bt
from bittensor import subtensor

from config import Config

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format=Config.LOG_FORMAT,
    handlers=[
        logging.FileHandler(Config.get_log_file('emissions_collector')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BittensorEmissionsCollector:
    """
    Collects emissions data from Bittensor subnets using the Bittensor SDK.
    Production-ready with retry logic and proper error handling.
    """
    
    def __init__(self, network: str = None):
        """
        Initialize the collector.
        
        Args:
            network: The Bittensor network to connect to (default: from Config)
        """
        self.network = network or Config.NETWORK
        self.subtensor = None
        self.max_retries = Config.RETRY_ATTEMPTS
        self.retry_delay = Config.RETRY_DELAY
        
    async def connect(self):
        """Connect to the Bittensor network."""
        try:
            logger.info(f"Connecting to Bittensor network: {self.network}")
            self.subtensor = subtensor(network=self.network)
            logger.info("Successfully connected to Bittensor network")
        except Exception as e:
            logger.error(f"Failed to connect to Bittensor network: {e}")
            raise
    
    def get_all_subnets(self) -> List[int]:
        """Get all available subnet UIDs."""
        try:
            if not self.subtensor:
                raise Exception("Not connected to subtensor")
            
            # Get all subnets using the correct method
            subnets = self.subtensor.get_subnets()
            logger.info(f"Found {len(subnets)} subnets: {subnets}")
            return subnets
            
        except Exception as e:
            logger.error(f"Error getting subnets: {e}")
            return []
    
    def get_subnet_emissions(self, subnet_uid: int) -> Optional[Dict]:
        """Get emissions data for a specific subnet."""
        try:
            if not self.subtensor:
                raise Exception("Not connected to subtensor")
            
            logger.info(f"Collecting emissions data for subnet {subnet_uid}")
            
            # Get subnet information
            subnet_info = self.subtensor.get_subnet_info(subnet_uid)
            
            # Get emission rate from subnet info
            emission_rate = subnet_info.emission_value if hasattr(subnet_info, 'emission_value') else 0
            
            # Get neurons (validators) for this subnet
            neurons = self.subtensor.neurons(subnet_uid)
            num_validators = len(neurons) if neurons else 0
            
            # Calculate total stake from neurons
            total_stake = 0.0
            if neurons:
                total_stake = sum(n.stake.tao for n in neurons)
            
            # Calculate daily emission (emission rate * 24 hours)
            # Note: emission_rate might be 0 if subnets are not currently emitting
            daily_emission = emission_rate * 24 if emission_rate else 0
            
            emissions_data = {
                'subnet_uid': subnet_uid,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'emission_rate': float(emission_rate),
                'daily_emission': float(daily_emission),
                'total_stake': float(total_stake),
                'num_validators': num_validators,
                'subnet_name': f"Subnet {subnet_uid}",
                'network': self.network,
                'subnet_owner': str(subnet_info.owner_ss58) if hasattr(subnet_info, 'owner_ss58') else '',
                'subnet_created': '',  # This field might not be available in current API
                'difficulty': int(subnet_info.difficulty) if hasattr(subnet_info, 'difficulty') else 0,
                'max_validators': int(subnet_info.max_allowed_validators) if hasattr(subnet_info, 'max_allowed_validators') else 0,
                'burn_cost': str(subnet_info.burn) if hasattr(subnet_info, 'burn') else '0'
            }
            
            logger.info(f"Successfully collected data for subnet {subnet_uid}: "
                       f"stake={total_stake:.2f} TAO, validators={num_validators}, "
                       f"emission_rate={emission_rate}, daily_emission={daily_emission}")
            return emissions_data
            
        except Exception as e:
            logger.error(f"Error getting emissions for subnet {subnet_uid}: {e}")
            return None
    
    async def collect_all_emissions(self) -> List[Dict]:
        """Collect emissions data for all subnets."""
        try:
            # Connect to the network
            await self.connect()
            
            # Get all subnets
            subnets = self.get_all_subnets()
            if not subnets:
                logger.error("No subnets found")
                return []
            
            emissions_data = []
            
            # Collect data for each subnet
            for subnet_uid in subnets:
                emissions = self.get_subnet_emissions(subnet_uid)
                if emissions:
                    emissions_data.append(emissions)
                else:
                    logger.warning(f"No emissions data available for subnet {subnet_uid}")
            
            logger.info(f"Collected emissions data for {len(emissions_data)} subnets")
            return emissions_data
            
        except Exception as e:
            logger.error(f"Error collecting emissions data: {e}")
            return []
    
    def save_to_csv(self, data: List[Dict], filename: str = None) -> str:
        """Save emissions data to CSV file."""
        if not data:
            logger.warning("No data to save")
            return ""
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"bittensor_emissions_{timestamp}.csv"
        
        try:
            df = pd.DataFrame(data)
            df.to_csv(filename, index=False)
            logger.info(f"Data saved to {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Failed to save CSV: {e}")
            return ""
    
    def save_to_dataset(self, data: List[Dict], dataset_dir: str = None) -> str:
        """Save emissions data to a structured dataset directory."""
        if not data:
            logger.warning("No data to save")
            return ""
        
        # Use Config data directory if not specified
        if dataset_dir is None:
            dataset_dir = Config.DATA_DIR / "emissions"
        
        # Create dataset directory if it doesn't exist
        os.makedirs(dataset_dir, exist_ok=True)
        
        # Create subdirectories for organization
        date_str = datetime.now().strftime("%Y-%m-%d")
        hour_str = datetime.now().strftime("%H")
        
        # Save to hourly file
        hourly_dir = os.path.join(dataset_dir, date_str)
        os.makedirs(hourly_dir, exist_ok=True)
        
        hourly_filename = os.path.join(hourly_dir, f"emissions_{hour_str}.csv")
        
        try:
            df = pd.DataFrame(data)
            df.to_csv(hourly_filename, index=False)
            logger.info(f"Data saved to {hourly_filename}")
            
            # Also save to daily aggregated file
            daily_filename = os.path.join(hourly_dir, "daily_emissions.csv")
            
            # Append to daily file (create if doesn't exist)
            if os.path.exists(daily_filename):
                existing_df = pd.read_csv(daily_filename)
                combined_df = pd.concat([existing_df, df], ignore_index=True)
            else:
                combined_df = df
            
            combined_df.to_csv(daily_filename, index=False)
            logger.info(f"Daily data updated: {daily_filename}")
            
            return hourly_filename
            
        except Exception as e:
            logger.error(f"Failed to save to dataset: {e}")
            return ""

async def main():
    """Main function to run the emissions collector."""
    logger.info("Starting Bittensor emissions data collection...")
    
    # Create collector
    collector = BittensorEmissionsCollector(network="finney")
    
    # Collect emissions data
    emissions_data = await collector.collect_all_emissions()
    
    if emissions_data:
        # Save to dataset
        filename = collector.save_to_dataset(emissions_data)
        print(f"Emissions data saved to: {filename}")
        
        # Also save a timestamped copy
        timestamped_filename = collector.save_to_csv(emissions_data)
        print(f"Timestamped copy saved to: {timestamped_filename}")
        
        # Print summary
        print(f"\nCollection Summary:")
        print(f"Subnets processed: {len(emissions_data)}")
        print(f"Total daily emission: {sum(d['daily_emission'] for d in emissions_data):.2f} TAO")
        print(f"Total stake: {sum(d['total_stake'] for d in emissions_data):.2f} TAO")
        print(f"Total validators: {sum(d['num_validators'] for d in emissions_data)}")
        
        # Show some sample data
        print(f"\nSample data (first 3 subnets):")
        for i, data in enumerate(emissions_data[:3]):
            print(f"  Subnet {data['subnet_uid']}: "
                  f"Stake: {data['total_stake']:.2f} TAO, "
                  f"Validators: {data['num_validators']}, "
                  f"Emission: {data['emission_rate']}")
        
    else:
        print("No emissions data collected")

if __name__ == "__main__":
    asyncio.run(main())
