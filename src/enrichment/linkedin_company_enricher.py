"""
LinkedIn Company Page Enricher
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Scrapes LinkedIn company pages to get detailed company information.
"""

import re
import time
from typing import Dict, List
from bs4 import BeautifulSoup
from ..utils.logger import LoggerMixin

try:
    import undetected_chromedriver as uc
    UNDETECTED_AVAILABLE = True
except ImportError:
    UNDETECTED_AVAILABLE = False

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


class LinkedInCompanyEnricher(LoggerMixin):
    """
    Enriches company data by scraping LinkedIn company pages.
    
    Uses company URLs from job listings to extract:
    - Company size
    - Revenue
    - Industry
    - Headquarters
    - Founded year
    - Website
    - Company description
    """
    
    def __init__(self, headless: bool = True, delay_range: tuple = (2, 5)):
        """
        Initialize the LinkedIn company enricher.
        
        Args:
            headless: Whether to run browser in headless mode
            delay_range: Random delay range between requests (min, max) seconds
        """
        self.headless = headless
        self.delay_range = delay_range
        self.driver = None
        self.base_url = "https://www.linkedin.com"
        
    def __enter__(self):
        """Context manager entry."""
        self.initialize_driver()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.driver:
            self.driver.quit()
    
    def initialize_driver(self):
        """Initialize the web driver."""
        try:
            if UNDETECTED_AVAILABLE:
                # Use undetected-chromedriver to bypass LinkedIn's bot detection
                options = uc.ChromeOptions()
                
                if self.headless:
                    options.add_argument('--headless=new')
                
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--disable-blink-features=AutomationControlled')
                
                # Create undetected Chrome instance
                self.driver = uc.Chrome(options=options, version_main=140)
                
                self.logger.info("✓ Undetected Chrome initialized for LinkedIn")
                
            elif SELENIUM_AVAILABLE:
                # Fallback to regular Selenium (will likely get blocked)
                self.logger.warning("undetected-chromedriver not available, using regular Selenium (may be blocked)")
                
                options = Options()
                if self.headless:
                    options.add_argument('--headless=new')
                
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
                
                self.driver = webdriver.Chrome(options=options)
                
            else:
                raise ImportError("Neither Selenium nor undetected-chromedriver is available")
            
            # Set page load timeout (shorter timeout to fail fast)
            self.driver.set_page_load_timeout(15)
            
        except Exception as e:
            self.logger.error(f"Failed to initialize WebDriver: {e}")
            raise
    
    def enrich_companies_from_jobs(self, jobs: List[Dict]) -> Dict[str, Dict]:
        """
        Enrich company data for a list of jobs.
        
        Args:
            jobs: List of job dictionaries with company_url field
            
        Returns:
            Dictionary mapping company names to enrichment data
        """
        enrichment_map = {}
        
        # Extract unique company URLs
        company_urls = {}
        for job in jobs:
            company_name = job.get('company_name')
            company_url = job.get('company_url')
            
            if company_name and company_url and company_url.startswith('https://www.linkedin.com/company/'):
                if company_name not in company_urls:
                    company_urls[company_name] = company_url
        
        self.logger.info(f"Enriching {len(company_urls)} unique companies from LinkedIn company pages")
        
        # Enrich each company
        enriched_count = 0
        for company_name, company_url in company_urls.items():
            try:
                # Random delay to avoid rate limiting
                if enriched_count > 0:
                    delay = time.sleep(1 + (self.delay_range[1] - self.delay_range[0]) * 0.5)
                
                enrichment_data = self._scrape_company_page(company_url)
                
                if enrichment_data and enrichment_data.get('status') == 'SUCCESS':
                    enrichment_map[company_name] = enrichment_data
                    enriched_count += 1
                    
                    self.logger.info(f"✓ Enriched: {company_name}")
                    
                    # Show some sample data
                    size = enrichment_data.get('company_size', 'Unknown')
                    revenue = enrichment_data.get('revenue_range', 'Unknown')
                    industry = enrichment_data.get('industry', 'Unknown')
                    
                    if size != 'Unknown' or revenue != 'Unknown' or industry != 'Unknown':
                        self.logger.info(f"   Size: {size}, Revenue: {revenue}, Industry: {industry}")
                else:
                    self.logger.warning(f"✗ Failed to enrich: {company_name}")
                
            except Exception as e:
                self.logger.error(f"Error enriching {company_name}: {e}")
                continue
        
        self.logger.info(f"✓ Enriched {enriched_count}/{len(company_urls)} companies from LinkedIn")
        return enrichment_map
    
    def _scrape_company_page(self, company_url: str) -> Dict:
        """
        Scrape a LinkedIn company page for company information.
        
        Args:
            company_url: LinkedIn company page URL
            
        Returns:
            Dictionary with scraped company data
        """
        data = {
            'company_name': 'Unknown',
            'company_size': 'Unknown',
            'revenue_range': 'Unknown',
            'headquarters': 'Unknown',
            'industry': 'Unknown',
            'founded_year': 'Unknown',
            'website': 'Unknown',
            'company_description': 'Unknown',
            'status': 'FAILED'
        }
        
        try:
            # Extract company name from URL for logging
            company_slug = company_url.split('/')[-1] if '/' in company_url else company_url
            
            self.logger.info(f"Scraping LinkedIn company page: {company_slug}")
            
            # Load the page with timeout handling
            try:
                self.driver.set_page_load_timeout(10)  # Even shorter timeout
                self.driver.get(company_url)
                time.sleep(1)  # Reduced wait time
            except Exception as timeout_error:
                self.logger.warning(f"Timeout loading {company_slug}: {timeout_error}")
                # Return fallback data instead of failing completely
                data['status'] = 'TIMEOUT'
                data['company_size'] = 'Not available (timeout)'
                return data
            
            # Check if we got blocked or redirected
            current_url = self.driver.current_url.lower()
            if 'login' in current_url or 'blocked' in current_url or 'checkpoint' in current_url:
                self.logger.warning(f"LinkedIn login required or blocked for {company_slug}")
                data['status'] = 'BLOCKED'
                data['company_size'] = 'Not available (login required)'
                return data
            
            # Get page source
            html = self.driver.page_source
            if not html or len(html) < 1000:  # Empty or minimal page
                self.logger.warning(f"Empty page content for {company_slug}")
                data['status'] = 'EMPTY_PAGE'
                return data
            
            soup = BeautifulSoup(html, 'lxml')
            
            # Extract company name
            name_elem = soup.find('h1', class_=re.compile(r'org-top-card-summary__title', re.I))
            if name_elem:
                data['company_name'] = name_elem.get_text(strip=True)
            
            # Extract company size (look for employee count)
            size_patterns = [
                r'(\d+\s*to\s*\d+\s*employees|\d+\+\s*employees)',
                r'(\d+\s*to\s*\d+|\d+)\s*employees',
                r'(\d+)\s*employees'
            ]
            
            # Look in the whole page for size information
            page_text = soup.get_text()
            for pattern in size_patterns:
                matches = re.findall(pattern, page_text, re.I)
                if matches:
                    data['company_size'] = matches[0]
                    break
            
            # Extract industry
            industry_elem = soup.find(string=re.compile(r'industry', re.I))
            if industry_elem:
                parent = industry_elem.find_parent()
                if parent:
                    # Look for industry value in nearby elements
                    siblings = parent.find_next_siblings()
                    for sibling in siblings[:3]:
                        text = sibling.get_text(strip=True)
                        if text and len(text) < 100:  # Reasonable industry name length
                            data['industry'] = text
                            break
            
            # Extract headquarters
            hq_patterns = [
                r'headquarters[^\n]+?([^\n]+)',
                r'location[^\n]+?([^\n]+)',
                r'based[^\n]+?([^\n]+)'
            ]
            
            for pattern in hq_patterns:
                matches = re.findall(pattern, page_text, re.I)
                if matches:
                    data['headquarters'] = matches[0].strip()
                    break
            
            # Extract founded year
            founded_patterns = [
                r'founded\s*(\d{4})',
                r'established\s*(\d{4})',
                r'since\s*(\d{4})'
            ]
            
            for pattern in founded_patterns:
                matches = re.findall(pattern, page_text, re.I)
                if matches:
                    data['founded_year'] = matches[0]
                    break
            
            # Extract website
            website_elem = soup.find('a', href=re.compile(r'^http', re.I))
            if website_elem:
                href = website_elem.get('href', '')
                if href and not 'linkedin.com' in href:
                    data['website'] = href
            
            # Extract company description
            desc_elem = soup.find('div', class_=re.compile(r'description|about', re.I))
            if desc_elem:
                desc_text = desc_elem.get_text(strip=True)
                if desc_text and len(desc_text) > 50:
                    data['company_description'] = desc_text[:500]
            
            # Look for revenue (less common on LinkedIn)
            revenue_patterns = [
                r'\$(\d+(?:\.\d+)?)\s*(billion|million|thousand)',
                r'revenue.*?\$?(\d+(?:\.\d+)?)\s*(b|m|k)'
            ]
            
            for pattern in revenue_patterns:
                matches = re.findall(pattern, page_text, re.I)
                if matches:
                    match = matches[0]
                    if isinstance(match, tuple):
                        amount, unit = match
                        data['revenue_range'] = f"${amount} {unit}"
                    else:
                        data['revenue_range'] = f"${match}"
                    break
            
            # If we got at least some data, mark as success
            if (data['company_size'] != 'Unknown' or 
                data['industry'] != 'Unknown' or 
                data['headquarters'] != 'Unknown' or
                data['founded_year'] != 'Unknown'):
                data['status'] = 'SUCCESS'
            else:
                data['status'] = 'NO_DATA'
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error scraping company page: {e}")
            data['status'] = 'ERROR'
            return data
