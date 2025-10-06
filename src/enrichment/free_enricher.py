"""
Free Company Enrichment
~~~~~~~~~~~~~~~~~~~~~~~

Uses free sources to enrich company data:
- Google Search (for basic info)
- Company websites (About pages)
- DuckDuckGo Instant Answer API (free, no auth)
"""

import re
import time
import requests
from typing import Dict, List
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

from ..utils.logger import LoggerMixin


class FreeEnricher(LoggerMixin):
    """Free company enrichment using Google Search and web scraping."""
    
    def __init__(self, headless: bool = True):
        """
        Initialize free enricher.
        
        Args:
            headless: Run browser in headless mode
        """
        self.headless = headless
        self.driver = None
    
    def initialize_driver(self):
        """Initialize Chrome WebDriver."""
        if self.driver:
            return
        
        self.logger.info("Initializing Chrome for free enrichment...")
        
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--disable-gpu')
        
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.logger.info("✓ Chrome initialized for free enrichment")
    
    def close(self):
        """Close the browser."""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def __enter__(self):
        """Context manager entry."""
        self.initialize_driver()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def enrich_companies(self, companies: List[str], max_companies: int = 50) -> List[Dict]:
        """
        Enrich multiple companies.
        
        Args:
            companies: List of company names
            max_companies: Maximum number to enrich
            
        Returns:
            List of enriched company data
        """
        self.initialize_driver()
        
        results = []
        companies_to_process = companies[:max_companies]
        
        self.logger.info(f"Enriching {len(companies_to_process)} companies (free sources)...")
        
        for i, company in enumerate(companies_to_process, 1):
            self.logger.info(f"[{i}/{len(companies_to_process)}] Enriching: {company}")
            
            try:
                data = self.enrich_company(company)
                results.append(data)
                
                # Be polite - add delay between requests
                time.sleep(2)
                
            except Exception as e:
                self.logger.error(f"Error enriching {company}: {e}")
                results.append({
                    'company_name': company,
                    'company_size': 'Unknown',
                    'revenue_range': 'Unknown',
                    'funding_stage': 'Unknown',
                    'headquarters': 'Unknown',
                    'industry': 'Unknown',
                    'status': 'ERROR'
                })
        
        return results
    
    def enrich_company(self, company_name: str) -> Dict:
        """
        Enrich a single company using free sources.
        
        Args:
            company_name: Name of the company
            
        Returns:
            Dictionary with enriched data
        """
        data = {
            'company_name': company_name,
            'company_size': 'Unknown',
            'revenue_range': 'Unknown',
            'funding_stage': 'Unknown',
            'headquarters': 'Unknown',
            'industry': 'Unknown',
            'status': 'SUCCESS'
        }
        
        try:
            # Strategy 1: Google Search for quick info
            google_data = self._search_google(company_name)
            if google_data:
                data.update(google_data)
            
            # Strategy 2: Try to find and scrape company website
            if data['company_size'] == 'Unknown' or data['headquarters'] == 'Unknown':
                website_data = self._scrape_company_website(company_name)
                if website_data:
                    # Only update if we got better data
                    for key, value in website_data.items():
                        if data[key] == 'Unknown' and value != 'Unknown':
                            data[key] = value
            
            # Log what we found
            self.logger.info(
                f"  ✓ Size: {data['company_size']}, "
                f"Location: {data['headquarters']}, "
                f"Industry: {data['industry']}"
            )
            
        except Exception as e:
            self.logger.error(f"Error enriching {company_name}: {e}")
            data['status'] = 'ERROR'
        
        return data
    
    def _search_google(self, company_name: str) -> Dict:
        """
        Search Google for company information.
        
        Args:
            company_name: Company name to search
            
        Returns:
            Extracted data
        """
        data = {}
        
        try:
            # Google search query
            query = f"{company_name} company employees headquarters location"
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            
            self.driver.get(search_url)
            time.sleep(2)
            
            # Get page text
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            
            # Extract employee count
            employee_patterns = [
                r'(\d+(?:,\d+)?)\+?\s+employees?',
                r'employees?[:\s]+(\d+(?:,\d+)?)',
                r'(\d+)\s+to\s+(\d+)\s+employees?',
                r'(\d+-\d+)\s+employees?',
            ]
            
            for pattern in employee_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    size = match.group(1)
                    data['company_size'] = self._normalize_size(size)
                    break
            
            # Extract headquarters/location
            location_patterns = [
                r'(?:headquarters|located|based)\s+(?:in|at)?\s+([A-Z][a-z]+(?:,\s*[A-Z][a-z]+)*)',
                r'([A-Z][a-z]+,\s*[A-Z]{2}(?:,\s*(?:USA|United States))?)',
                r'([A-Z][a-z]+,\s*[A-Z][a-z]+,\s*United States)',
            ]
            
            for pattern in location_patterns:
                match = re.search(pattern, page_text)
                if match:
                    data['headquarters'] = match.group(1).strip()
                    break
            
            # Extract industry (from description)
            industry_keywords = [
                'technology', 'software', 'healthcare', 'finance', 'consulting',
                'manufacturing', 'retail', 'education', 'insurance', 'real estate',
                'telecommunications', 'aerospace', 'automotive', 'biotechnology',
                'pharmaceutical', 'energy', 'logistics', 'marketing', 'media'
            ]
            
            for keyword in industry_keywords:
                if keyword in page_text.lower():
                    data['industry'] = keyword.capitalize()
                    break
            
        except Exception as e:
            self.logger.debug(f"Google search failed for {company_name}: {e}")
        
        return data
    
    def _scrape_company_website(self, company_name: str) -> Dict:
        """
        Try to find and scrape company website.
        
        Args:
            company_name: Company name
            
        Returns:
            Extracted data
        """
        data = {}
        
        try:
            # Search for company website
            search_query = f"{company_name} official website"
            search_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
            
            self.driver.get(search_url)
            time.sleep(2)
            
            # Try to find the official website link
            links = self.driver.find_elements(By.CSS_SELECTOR, "a[href]")
            company_url = None
            
            # Look for likely company domain
            for link in links[:10]:  # Check first 10 results
                href = link.get_attribute('href')
                if href and 'http' in href and 'google' not in href:
                    # Simple heuristic: first non-Google link
                    company_url = href
                    break
            
            if company_url:
                self.logger.debug(f"Found website: {company_url}")
                
                # Visit the website
                try:
                    self.driver.get(company_url)
                    time.sleep(2)
                    
                    # Get page text
                    page_text = self.driver.find_element(By.TAG_NAME, "body").text
                    
                    # Try to extract info from About page
                    about_keywords = ['about', 'company', 'team']
                    about_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='about'], a[href*='company'], a[href*='team']")
                    
                    if about_links:
                        try:
                            about_links[0].click()
                            time.sleep(2)
                            page_text = self.driver.find_element(By.TAG_NAME, "body").text
                        except:
                            pass
                    
                    # Extract employee count from website
                    employee_patterns = [
                        r'(\d+(?:,\d+)?)\+?\s+employees?',
                        r'team\s+of\s+(\d+)',
                        r'over\s+(\d+)\s+people',
                    ]
                    
                    for pattern in employee_patterns:
                        match = re.search(pattern, page_text, re.IGNORECASE)
                        if match:
                            data['company_size'] = self._normalize_size(match.group(1))
                            break
                    
                    # Extract location
                    location_patterns = [
                        r'(?:headquarters|office|located|based)\s+(?:in|at)?\s+([A-Z][a-z]+(?:,\s*[A-Z][a-z]+)*)',
                    ]
                    
                    for pattern in location_patterns:
                        match = re.search(pattern, page_text)
                        if match:
                            data['headquarters'] = match.group(1).strip()
                            break
                    
                except Exception as e:
                    self.logger.debug(f"Could not scrape website {company_url}: {e}")
        
        except Exception as e:
            self.logger.debug(f"Website scraping failed for {company_name}: {e}")
        
        return data
    
    def _normalize_size(self, size_text: str) -> str:
        """
        Normalize company size to standard ranges.
        
        Args:
            size_text: Raw size text (e.g., "150", "100-200", "1,500")
            
        Returns:
            Normalized size range
        """
        # Remove commas and convert to int
        size_text = size_text.replace(',', '').strip()
        
        try:
            # If it's a range (e.g., "100-200")
            if '-' in size_text:
                return size_text
            
            # If it's a single number
            size = int(size_text)
            
            # Convert to ranges
            if size < 10:
                return '1-10'
            elif size < 50:
                return '11-50'
            elif size < 200:
                return '51-200'
            elif size < 500:
                return '201-500'
            elif size < 1000:
                return '501-1000'
            elif size < 5000:
                return '1001-5000'
            else:
                return '5000+'
        
        except:
            return size_text
