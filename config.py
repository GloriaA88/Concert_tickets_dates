"""
Configuration management for the Italian Concert Bot
"""
import os
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

class Config:
    def __init__(self):
        # Load environment variables from .env file
        load_dotenv()
        
        # Telegram Bot Configuration
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not self.telegram_token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
        
        # TicketMaster API Configuration
        self.ticketmaster_api_key = os.getenv('TICKETMASTER_API_KEY')
        if not self.ticketmaster_api_key:
            raise ValueError("TICKETMASTER_API_KEY environment variable is required")
        
        # Database Configuration
        self.database_path = os.getenv('DATABASE_PATH', 'concert_bot.db')
        
        # Scheduler Configuration
        self.check_interval_hours = int(os.getenv('CHECK_INTERVAL_HOURS', '4'))
        self.cleanup_days = int(os.getenv('CLEANUP_DAYS', '30'))
        
        # Rate Limiting
        self.rate_limit_delay = float(os.getenv('RATE_LIMIT_DELAY', '0.2'))
        
        # Logging Configuration
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        
        # Concert Search Configuration
        self.default_country = os.getenv('DEFAULT_COUNTRY', 'IT')
        self.search_months_ahead = int(os.getenv('SEARCH_MONTHS_AHEAD', '6'))
        self.max_concerts_per_notification = int(os.getenv('MAX_CONCERTS_PER_NOTIFICATION', '10'))
        
        # Validate configuration
        self._validate_config()
        
        logger.info("Configuration loaded successfully")
    
    def _validate_config(self):
        """Validate configuration values"""
        if self.check_interval_hours < 1:
            raise ValueError("CHECK_INTERVAL_HOURS must be at least 1")
        
        if self.cleanup_days < 1:
            raise ValueError("CLEANUP_DAYS must be at least 1")
        
        if self.rate_limit_delay < 0:
            raise ValueError("RATE_LIMIT_DELAY cannot be negative")
        
        if self.search_months_ahead < 1 or self.search_months_ahead > 12:
            raise ValueError("SEARCH_MONTHS_AHEAD must be between 1 and 12")
        
        if self.max_concerts_per_notification < 1:
            raise ValueError("MAX_CONCERTS_PER_NOTIFICATION must be at least 1")
        
        # Validate log level
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self.log_level not in valid_log_levels:
            raise ValueError(f"LOG_LEVEL must be one of: {valid_log_levels}")
    
    def get_database_url(self) -> str:
        """Get the database connection URL"""
        return f"sqlite:///{self.database_path}"
    
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return os.getenv('ENVIRONMENT', 'development').lower() == 'production'
    
    def get_config_summary(self) -> dict:
        """Get a summary of current configuration (without sensitive data)"""
        return {
            'database_path': self.database_path,
            'check_interval_hours': self.check_interval_hours,
            'cleanup_days': self.cleanup_days,
            'rate_limit_delay': self.rate_limit_delay,
            'log_level': self.log_level,
            'default_country': self.default_country,
            'search_months_ahead': self.search_months_ahead,
            'max_concerts_per_notification': self.max_concerts_per_notification,
            'is_production': self.is_production()
        }
