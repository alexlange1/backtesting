#!/usr/bin/env python3
"""
Configuration Management for Bittensor TAO Index
=================================================
Centralized configuration with environment variable support.

Author: Alexander Lange
Date: October 22, 2025
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List


class Config:
    """Centralized configuration for all Bittensor TAO Index applications."""
    
    # ============================================================================
    # Network Settings
    # ============================================================================
    
    NETWORK = os.getenv('BITTENSOR_NETWORK', 'finney')
    ARCHIVE_NETWORK = os.getenv('BITTENSOR_ARCHIVE_NETWORK', 'archive')
    
    # ============================================================================
    # Directory Settings
    # ============================================================================
    
    BASE_DIR = Path(__file__).parent.absolute()
    RESULTS_DIR = BASE_DIR / 'backtest_results'
    LOGS_DIR = BASE_DIR / 'logs'
    DATA_DIR = BASE_DIR / 'data'
    
    # Create directories if they don't exist
    for directory in [RESULTS_DIR, LOGS_DIR, DATA_DIR]:
        directory.mkdir(exist_ok=True)
    
    # ============================================================================
    # Backtest Settings
    # ============================================================================
    
    START_DATE = datetime(2025, 2, 1)
    END_DATE = datetime(2025, 10, 22)
    REBALANCE_WEEKS = int(os.getenv('REBALANCE_WEEKS', '2'))
    
    # Price fetching settings
    PRICE_FETCH_INTERVAL = os.getenv('PRICE_FETCH_INTERVAL', 'daily')  # 'daily' or 'weekly'
    PRICE_BLOCKS_PER_INTERVAL = 7200  # ~1 day of blocks (12 sec per block)
    
    # APY calculation settings
    APY_CALCULATION_METHOD = os.getenv('APY_CALCULATION_METHOD', 'emissions_stake_ratio')
    INCLUDE_APY_IN_NAV = os.getenv('INCLUDE_APY_IN_NAV', 'true').lower() == 'true'
    BLOCKS_PER_DAY = 7200  # Approximate blocks per day
    
    # Index configurations
    INDEX_CONFIGS: Dict[str, int] = {
        'TAO20': 20,
        'TAO15': 15,
        'TAO10': 10
    }
    
    # ============================================================================
    # API Settings
    # ============================================================================
    
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '120'))
    RETRY_ATTEMPTS = int(os.getenv('RETRY_ATTEMPTS', '3'))
    RETRY_DELAY = int(os.getenv('RETRY_DELAY', '5'))
    
    # ============================================================================
    # Logging Settings
    # ============================================================================
    
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # ============================================================================
    # Emissions Collector Settings
    # ============================================================================
    
    COLLECTION_INTERVAL_HOURS = int(os.getenv('COLLECTION_INTERVAL_HOURS', '1'))
    SAVE_HOURLY_SNAPSHOTS = os.getenv('SAVE_HOURLY_SNAPSHOTS', 'true').lower() == 'true'
    
    @classmethod
    def get_log_file(cls, name: str) -> Path:
        """Get log file path for a specific module."""
        return cls.LOGS_DIR / f'{name}.log'
    
    @classmethod
    def get_results_file(cls, name: str, extension: str = 'csv') -> Path:
        """Get results file path with timestamp."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return cls.RESULTS_DIR / f'{name}_{timestamp}.{extension}'
    
    @classmethod
    def validate(cls) -> List[str]:
        """Validate configuration and return list of errors."""
        errors = []
        
        if cls.REBALANCE_WEEKS < 1:
            errors.append("REBALANCE_WEEKS must be >= 1")
        
        if cls.REQUEST_TIMEOUT < 1:
            errors.append("REQUEST_TIMEOUT must be >= 1")
        
        if cls.RETRY_ATTEMPTS < 0:
            errors.append("RETRY_ATTEMPTS must be >= 0")
        
        if cls.START_DATE >= cls.END_DATE:
            errors.append("START_DATE must be before END_DATE")
        
        return errors
    
    @classmethod
    def print_config(cls):
        """Print current configuration."""
        print("=" * 80)
        print("BITTENSOR TAO INDEX - CONFIGURATION")
        print("=" * 80)
        print(f"Network: {cls.NETWORK}")
        print(f"Archive Network: {cls.ARCHIVE_NETWORK}")
        print(f"Base Directory: {cls.BASE_DIR}")
        print(f"Results Directory: {cls.RESULTS_DIR}")
        print(f"Logs Directory: {cls.LOGS_DIR}")
        print(f"Data Directory: {cls.DATA_DIR}")
        print(f"Backtest Period: {cls.START_DATE.date()} to {cls.END_DATE.date()}")
        print(f"Rebalance Frequency: Every {cls.REBALANCE_WEEKS} weeks")
        print(f"Indices: {', '.join(cls.INDEX_CONFIGS.keys())}")
        print(f"Request Timeout: {cls.REQUEST_TIMEOUT}s")
        print(f"Retry Attempts: {cls.RETRY_ATTEMPTS}")
        print(f"Log Level: {cls.LOG_LEVEL}")
        print("=" * 80)
        print()


# Validate configuration on import
config_errors = Config.validate()
if config_errors:
    raise ValueError(f"Configuration errors: {', '.join(config_errors)}")


