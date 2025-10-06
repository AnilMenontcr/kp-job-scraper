"""
Production Configuration for Railway Deployment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Production-specific settings for Railway deployment environment.
"""

import os
from pathlib import Path

class ProductionConfig:
    """Production configuration for Railway deployment."""
    
    # Flask settings
    DEBUG = False
    TESTING = False
    
    # Railway will set PORT environment variable
    PORT = int(os.environ.get('PORT', 5000))
    
    # Host binding (Railway requires 0.0.0.0)
    HOST = '0.0.0.0'
    
    # File paths for Railway
    BASE_DIR = Path(__file__).parent
    OUTPUT_DIR = BASE_DIR / 'output'
    LOGS_DIR = BASE_DIR / 'logs'
    STATIC_DIR = BASE_DIR / 'static'
    
    # Ensure directories exist
    @classmethod
    def ensure_directories(cls):
        """Create required directories if they don't exist."""
        cls.OUTPUT_DIR.mkdir(exist_ok=True)
        cls.LOGS_DIR.mkdir(exist_ok=True)
        cls.STATIC_DIR.mkdir(exist_ok=True)
    
    # Job scraping settings for production
    MAX_COMPANIES = int(os.environ.get('MAX_COMPANIES', 50))
    RESULTS_WANTED = int(os.environ.get('RESULTS_WANTED', 100))
    
    # Timeout settings (Railway has resource limits)
    SCRAPE_TIMEOUT = int(os.environ.get('SCRAPE_TIMEOUT', 300))  # 5 minutes
    ENRICHMENT_TIMEOUT = int(os.environ.get('ENRICHMENT_TIMEOUT', 180))  # 3 minutes
    
    # Browser settings for production (headless only)
    BROWSER_HEADLESS = os.environ.get('BROWSER_HEADLESS', 'true').lower() == 'true'
    
    # Rate limiting for production (avoid getting blocked)
    RATE_LIMIT_DELAY = float(os.environ.get('RATE_LIMIT_DELAY', 2.0))
    MAX_CONCURRENT_REQUESTS = int(os.environ.get('MAX_CONCURRENT_REQUESTS', 3))
    
    # Logging configuration for production
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    
    # Security settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-here-change-in-production')
    
    @classmethod
    def get_flask_config(cls):
        """Get Flask configuration dictionary."""
        return {
            'DEBUG': cls.DEBUG,
            'TESTING': cls.TESTING,
            'SECRET_KEY': cls.SECRET_KEY
        }
    
    def __init__(self):
        """Initialize production configuration."""
        self.ensure_directories()
