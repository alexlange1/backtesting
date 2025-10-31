#!/usr/bin/env python3
"""
Bittensor Emissions Data Scheduler (Production)
===============================================
Runs the emissions collector at scheduled intervals.
Production-ready with proper error handling and monitoring.

Author: Alexander Lange
Date: October 22, 2025
"""

import os
import sys
import time
import logging
import asyncio
import schedule
from datetime import datetime, timezone
from pathlib import Path

# Add current directory to path to import our collector
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import Config
from emissions_collector import BittensorEmissionsCollector

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format=Config.LOG_FORMAT,
    handlers=[
        logging.FileHandler(Config.get_log_file('emissions_scheduler')),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class EmissionsScheduler:
    """
    Scheduler for running emissions collection at configured intervals.
    Production-ready with monitoring and error recovery.
    """
    
    def __init__(self, network: str = None):
        self.network = network or Config.NETWORK
        self.collector = BittensorEmissionsCollector(network=self.network)
        self.running = False
        self.collection_interval = Config.COLLECTION_INTERVAL_HOURS
        
    async def collect_emissions(self):
        """Run one emissions collection cycle."""
        try:
            logger.info("=" * 60)
            logger.info(f"Starting emissions collection at {datetime.now()}")
            
            # Collect emissions data
            emissions_data = await self.collector.collect_all_emissions()
            
            if emissions_data:
                # Save to dataset
                filename = self.collector.save_to_dataset(emissions_data)
                
                # Calculate summary statistics
                total_daily_emission = sum(d['daily_emission'] for d in emissions_data)
                total_stake = sum(d['total_stake'] for d in emissions_data)
                total_validators = sum(d['num_validators'] for d in emissions_data)
                
                logger.info(f"✅ Collection completed successfully!")
                logger.info(f"📊 Data saved to: {filename}")
                logger.info(f"📈 Summary:")
                logger.info(f"   - Subnets processed: {len(emissions_data)}")
                logger.info(f"   - Total daily emission: {total_daily_emission:.2f} TAO")
                logger.info(f"   - Total stake: {total_stake:.2f} TAO")
                logger.info(f"   - Total validators: {total_validators}")
                
                # Save summary to a log file
                self.save_summary(emissions_data, total_daily_emission, total_stake, total_validators)
                
            else:
                logger.error("❌ No emissions data collected")
                
        except Exception as e:
            logger.error(f"❌ Error during emissions collection: {e}")
            logger.exception("Full traceback:")
    
    def save_summary(self, data, total_daily_emission, total_stake, total_validators):
        """Save a summary of the collection to a log file."""
        try:
            summary_dir = Path("dataset/summaries")
            summary_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y-%m-%d")
            summary_file = summary_dir / f"summary_{timestamp}.txt"
            
            with open(summary_file, "a") as f:
                f.write(f"\n{'='*50}\n")
                f.write(f"Collection Time: {datetime.now()}\n")
                f.write(f"Subnets Processed: {len(data)}\n")
                f.write(f"Total Daily Emission: {total_daily_emission:.2f} TAO\n")
                f.write(f"Total Stake: {total_stake:.2f} TAO\n")
                f.write(f"Total Validators: {total_validators}\n")
                
                # Add per-subnet breakdown
                f.write(f"\nPer-Subnet Breakdown:\n")
                for subnet in data:
                    f.write(f"  Subnet {subnet['subnet_uid']}: "
                           f"Daily Emission: {subnet['daily_emission']:.2f} TAO, "
                           f"Stake: {subnet['total_stake']:.2f} TAO, "
                           f"Validators: {subnet['num_validators']}\n")
                
        except Exception as e:
            logger.error(f"Error saving summary: {e}")
    
    def run_collection_sync(self):
        """Run collection in a synchronous wrapper for the scheduler."""
        asyncio.run(self.collect_emissions())
    
    def start_scheduler(self):
        """Start the scheduler at configured interval."""
        Config.print_config()
        
        logger.info("🚀 Starting Bittensor Emissions Scheduler")
        logger.info(f"📅 Will collect data every {self.collection_interval} hour(s)")
        logger.info(f"🌐 Network: {self.network}")
        logger.info(f"📁 Data will be saved to: {Config.DATA_DIR / 'emissions'}")
        
        # Schedule the job to run at configured interval
        schedule.every(self.collection_interval).hours.do(self.run_collection_sync)
        
        # Also run immediately on startup
        logger.info("🔄 Running initial collection...")
        self.run_collection_sync()
        
        self.running = True
        
        # Keep the scheduler running
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except KeyboardInterrupt:
                logger.info("🛑 Scheduler stopped by user")
                self.running = False
            except Exception as e:
                logger.error(f"❌ Scheduler error: {e}")
                time.sleep(60)  # Wait before retrying
    
    def stop_scheduler(self):
        """Stop the scheduler."""
        self.running = False
        logger.info("🛑 Scheduler stopped")

def main():
    """Main function to run the scheduler."""
    try:
        # Install schedule if not available
        try:
            import schedule
        except ImportError:
            logger.info("Installing schedule package...")
            os.system("pip3 install schedule")
            import schedule
        
        # Create and start scheduler
        scheduler = EmissionsScheduler(network="finney")
        scheduler.start_scheduler()
        
    except KeyboardInterrupt:
        logger.info("🛑 Application stopped by user")
    except Exception as e:
        logger.error(f"❌ Application error: {e}")
        logger.exception("Full traceback:")

if __name__ == "__main__":
    main()
