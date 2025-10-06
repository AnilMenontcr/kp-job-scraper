"""
Indeed Selenium Scraper for WSL
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Uses Windows Chrome from WSL environment.
"""

import os
from .indeed_selenium_scraper import IndeedSeleniumScraper
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


class IndeedSeleniumScraperWSL(IndeedSeleniumScraper):
    """Selenium scraper that uses Windows Chrome from WSL."""

    def initialize_driver(self, headless: bool = True):
        """
        Initialize Chrome WebDriver using Windows Chrome.

        Args:
            headless: Run browser in headless mode (no GUI)
        """
        self.logger.info("Initializing Chrome WebDriver (WSL -> Windows Chrome)...")

        chrome_options = Options()
        
        if headless:
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--disable-gpu')
        
        # Anti-detection options
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Realistic user agent
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        try:
            # Try to find Windows Chrome and ChromeDriver
            # Common Windows Chrome locations from WSL
            windows_chrome_paths = [
                '/mnt/c/Program Files/Google/Chrome/Application/chrome.exe',
                '/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe',
            ]
            
            chrome_path = None
            for path in windows_chrome_paths:
                if os.path.exists(path):
                    chrome_path = path
                    break
            
            if chrome_path:
                chrome_options.binary_location = chrome_path
                self.logger.info(f"Found Windows Chrome at: {chrome_path}")
            
            # Try to use system ChromeDriver
            self.driver = webdriver.Chrome(options=chrome_options)
            
            # Remove webdriver property to avoid detection
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                '''
            })
            
            self.logger.info("✓ Chrome WebDriver initialized (using Windows Chrome)")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize WebDriver: {e}")
            self.logger.error("Please install ChromeDriver or use Option 3 below")
            raise
