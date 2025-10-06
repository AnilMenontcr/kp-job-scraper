"""
Indeed Company Page Enricher
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Extracts company information from Indeed company profile pages.
This provides accurate data directly from Indeed (no Cloudflare issues).
"""

import time
import re
from typing import Dict, List, Optional
from bs4 import BeautifulSoup

try:
    import undetected_chromedriver as uc
    UNDETECTED_AVAILABLE = True
except ImportError:
    UNDETECTED_AVAILABLE = False
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from ..utils.logger import LoggerMixin


class IndeedCompanyEnricher(LoggerMixin):
    """Extract company data from Indeed company profile pages."""
    
    def __init__(self, headless: bool = True):
        """
        Initialize Indeed company enricher.
        
        Args:
            headless: Run browser in headless mode
        """
        self.headless = headless
        self.driver = None
        self.base_url = "https://www.indeed.com"
    
    def initialize_driver(self):
        """Initialize Chrome WebDriver with anti-detection."""
        if self.driver:
            return
        
        self.logger.info("Initializing Chrome for Indeed company enrichment (with anti-detection)...")
        
        try:
            if UNDETECTED_AVAILABLE:
                # Use undetected-chromedriver to bypass Indeed's bot detection
                options = uc.ChromeOptions()
                
                if self.headless:
                    options.add_argument('--headless=new')
                
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--disable-blink-features=AutomationControlled')
                
                # Create undetected Chrome instance - specify Chrome 140 to match browser
                self.driver = uc.Chrome(options=options, version_main=140)
                
                self.logger.info("✓ Undetected Chrome initialized (anti-bot bypass enabled)")
                
            else:
                # Fallback to regular Selenium (will likely get blocked)
                self.logger.warning("undetected-chromedriver not available, using regular Selenium (may be blocked)")
                
                from selenium.webdriver.chrome.options import Options
                chrome_options = Options()
                
                if self.headless:
                    chrome_options.add_argument('--headless')
                    chrome_options.add_argument('--disable-gpu')
                
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                chrome_options.add_argument('--disable-blink-features=AutomationControlled')
                chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
                chrome_options.add_experimental_option('useAutomationExtension', False)
                
                from selenium import webdriver
                self.driver = webdriver.Chrome(options=chrome_options)
                
                self.logger.info("✓ Regular Chrome initialized")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize WebDriver: {e}")
            raise
    
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
    
    def enrich_companies_from_jobs(self, jobs: List[Dict]) -> Dict[str, Dict]:
        """
        Enrich companies using company URLs from job listings.
        
        Args:
            jobs: List of job dictionaries with company names and profile URLs
            
        Returns:
            Dict mapping company name to enrichment data
        """
        self.initialize_driver()
        
        # Extract unique companies and their profile URLs
        company_urls = {}
        
        for job in jobs:
            company_name = job.get('company_name')
            if not company_name:
                continue
            
            # Get company profile URL directly from job listing
            if company_name not in company_urls:
                company_profile_url = job.get('company_profile_url')
                company_urls[company_name] = company_profile_url  # Can be None
        
        self.logger.info(f"Found {len(company_urls)} unique companies to enrich")
        
        # Enrich each company
        results = {}
        for i, (company_name, profile_url) in enumerate(company_urls.items(), 1):
            self.logger.info(f"[{i}/{len(company_urls)}] Enriching: {company_name}")
            
            try:
                # Use direct URL if available, otherwise try to find it
                if profile_url:
                    self.logger.debug(f"Using direct URL: {profile_url}")
                    data = self.enrich_company_from_url(company_name, profile_url)
                else:
                    self.logger.debug(f"No direct URL, searching for: {company_name}")
                    data = self.enrich_company(company_name)
                
                results[company_name] = data
                
                # Be polite - delay between requests
                time.sleep(2)
                
            except Exception as e:
                self.logger.error(f"Error enriching {company_name}: {e}")
                results[company_name] = {
                    'company_name': company_name,
                    'company_size': 'Unknown',
                    'revenue_range': 'Unknown',
                    'headquarters': 'Unknown',
                    'industry': 'Unknown',
                    'founded_year': 'Unknown',
                    'status': 'ERROR'
                }
        
        return results
    
    def enrich_company_from_url(self, company_name: str, company_url: str) -> Dict:
        """
        Enrich a company directly from its Indeed profile URL.
        
        Args:
            company_name: Name of the company
            company_url: Direct URL to Indeed company profile
            
        Returns:
            Dictionary with enriched data
        """
        data = {
            'company_name': company_name,
            'company_size': 'Unknown',
            'revenue_range': 'Unknown',
            'headquarters': 'Unknown',
            'industry': 'Unknown',
            'founded_year': 'Unknown',
            'status': 'SUCCESS'
        }
        
        try:
            # Visit company page directly
            self.driver.get(company_url)
            time.sleep(3)  # Wait for page to load
            
            # Parse company data
            data = self._parse_company_page(company_name)
            
        except Exception as e:
            self.logger.error(f"Error parsing company page: {e}")
            data['status'] = 'ERROR'
        
        return data
    
    def enrich_company(self, company_name: str) -> Dict:
        """
        Enrich a single company from Indeed company page.
        
        Args:
            company_name: Name of the company
            
        Returns:
            Dictionary with enriched data
        """
        data = {
            'company_name': company_name,
            'company_size': 'Unknown',
            'revenue_range': 'Unknown',
            'headquarters': 'Unknown',
            'industry': 'Unknown',
            'founded_year': 'Unknown',
            'status': 'SUCCESS'
        }
        
        try:
            # Try direct URL construction first (most reliable!)
            company_url = self._construct_indeed_url(company_name)
            self.logger.debug(f"Trying direct URL: {company_url}")
            
            # Visit company page
            self.driver.get(company_url)
            time.sleep(3)  # Wait for page to load
            
            # Check if page exists (not 404)
            if "Page Not Found" in self.driver.page_source or "404" in self.driver.title:
                self.logger.warning(f"Direct URL failed for: {company_name}, trying search...")
                # Fallback to search
                company_url = self._find_company_page(company_name)
                if company_url:
                    self.driver.get(company_url)
                    time.sleep(3)
                else:
                    self.logger.warning(f"Could not find Indeed page for: {company_name}")
                    data['status'] = 'NOT_FOUND'
                    return data
            
            # Parse company data
            data = self._parse_company_page(company_name)
            
        except Exception as e:
            self.logger.error(f"Error parsing company page: {e}")
            data['status'] = 'ERROR'
        
        return data
    
    def _construct_indeed_url(self, company_name: str) -> str:
        """
        Construct Indeed company URL from company name.
        
        Indeed uses pattern: https://www.indeed.com/cmp/{company-slug}
        
        Args:
            company_name: Company name
            
        Returns:
            Indeed company profile URL
        """
        import re
        
        # Convert company name to URL slug
        slug = company_name.lower()
        
        # Remove common suffixes
        slug = re.sub(r'\s+(inc\.?|corp\.?|corporation|llc|ltd\.?|limited|company|co\.?)$', '', slug, flags=re.IGNORECASE)
        
        # Remove special characters, keep alphanumeric and spaces
        slug = re.sub(r'[^\w\s-]', '', slug)
        
        # Replace spaces and multiple dashes with single dash
        slug = re.sub(r'[\s_]+', '-', slug)
        slug = re.sub(r'-+', '-', slug)
        
        # Remove leading/trailing dashes
        slug = slug.strip('-')
        
        # Construct URL
        url = f"{self.base_url}/cmp/{slug}"
        
        return url
    
    def _parse_company_page(self, company_name: str) -> Dict:
        """
        Parse company data from the current page.
        
        Args:
            company_name: Company name
            
        Returns:
            Dictionary with parsed company data
        """
        data = {
            'company_name': company_name,
            'company_size': 'Unknown',
            'revenue_range': 'Unknown',
            'headquarters': 'Unknown',
            'industry': 'Unknown',
            'founded_year': 'Unknown',
            'status': 'SUCCESS'
        }
        
        try:
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'lxml')
            
            # Extract company size - Look for specific patterns
            size_patterns = [
                r'(\d+\s*to\s*\d+\s*employees|\d+\+\s*employees)',
                r'(\d+\s*to\s*\d+|\d+\+)',
                r'(more than\s*\d+)',
                r'(10000\+|5001\+|1001\+|501\+|201\+|51\+|11\+|1\+)'
            ]
            
            for pattern in size_patterns:
                size_matches = soup.find_all(string=re.compile(pattern, re.I))
                if size_matches:
                    for match in size_matches:
                        text = match.strip()
                        # Skip if it's about job posting age
                        if 'day' in text.lower() or 'hour' in text.lower() or 'minute' in text.lower():
                            continue
                        # Take the first reasonable match
                        if any(char.isdigit() for char in text):
                            data['company_size'] = text
                            break
                    if data['company_size'] != 'Unknown':
                        break
            
            # Alternative: Look for company size in specific containers
            if data['company_size'] == 'Unknown':
                # Try to find company info sections
                info_sections = soup.find_all(['div', 'span'], class_=re.compile(r'company|info|about', re.I))
                for section in info_sections:
                    text = section.get_text(strip=True)
                    # Look for size indicators
                    if any(keyword in text.lower() for keyword in ['employee', 'size', 'people']):
                        size_match = re.search(r'(\d+\s*to\s*\d+|\d+\+|more than\s*\d+)', text, re.I)
                        if size_match:
                            data['company_size'] = size_match.group(1)
                            break
            
            # Extract revenue
            revenue_elem = soup.find(string=re.compile('Revenue', re.I))
            if revenue_elem:
                parent = revenue_elem.find_parent()
                if parent:
                    siblings = parent.find_next_siblings()
                    for sibling in siblings[:3]:
                        text = sibling.get_text(strip=True)
                        if '$' in text or 'USD' in text:
                            data['revenue_range'] = text
                            break
            
            # Extract headquarters
            hq_elem = soup.find(string=re.compile('Headquarters', re.I))
            if hq_elem:
                parent = hq_elem.find_parent()
                if parent:
                    siblings = parent.find_next_siblings()
                    for sibling in siblings[:3]:
                        text = sibling.get_text(strip=True)
                        if text and len(text) > 5:
                            data['headquarters'] = text[:100]  # Limit length
                            break
            
            # Extract industry
            industry_elem = soup.find(string=re.compile('Industry', re.I))
            if industry_elem:
                parent = industry_elem.find_parent()
                if parent:
                    siblings = parent.find_next_siblings()
                    for sibling in siblings[:3]:
                        text = sibling.get_text(strip=True)
                        if text and len(text) > 3:
                            data['industry'] = text
                            break
            
            # Extract founded year
            founded_elem = soup.find(string=re.compile('Founded', re.I))
            if founded_elem:
                parent = founded_elem.find_parent()
                if parent:
                    siblings = parent.find_next_siblings()
                    for sibling in siblings[:3]:
                        text = sibling.get_text(strip=True)
                        year_match = re.search(r'\b(19|20)\d{2}\b', text)
                        if year_match:
                            data['founded_year'] = year_match.group(0)
                            break
            
            # Log what we found
            self.logger.info(
                f"  ✓ Size: {data['company_size']}, "
                f"Revenue: {data['revenue_range']}, "
                f"Location: {data['headquarters']}"
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing page: {e}")
            data['status'] = 'ERROR'
        
        return data
    
    def _find_company_page(self, company_name: str) -> Optional[str]:
        """
        Find Indeed company profile URL for a company.
        
        Args:
            company_name: Company name to search
            
        Returns:
            Company profile URL or None
        """
        try:
            # Search for company
            from urllib.parse import quote_plus
            search_query = quote_plus(f"{company_name} company")
            search_url = f"{self.base_url}/cmp?q={search_query}"
            
            self.driver.get(search_url)
            time.sleep(2)
            
            # Look for company link
            # Indeed company links are typically: /cmp/{company-slug}
            soup = BeautifulSoup(self.driver.page_source, 'lxml')
            
            # Try to find exact company match
            company_links = soup.find_all('a', href=re.compile(r'/cmp/[^/]+'))
            
            for link in company_links:
                link_text = link.get_text(strip=True).lower()
                if company_name.lower() in link_text:
                    href = link.get('href')
                    if href.startswith('/'):
                        return f"{self.base_url}{href}"
                    return href
            
            # If no exact match, return first result
            if company_links:
                href = company_links[0].get('href')
                if href.startswith('/'):
                    return f"{self.base_url}{href}"
                return href
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Error finding company page: {e}")
            return None
