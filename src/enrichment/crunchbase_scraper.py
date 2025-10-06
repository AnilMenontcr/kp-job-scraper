"""
Automated Crunchbase Enrichment Scraper
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Automatically enriches company data from Crunchbase.
Uses undetected-chromedriver to bypass Cloudflare protection.
"""

import time
from typing import Dict, Optional, List

try:
    import undetected_chromedriver as uc
    UNDETECTED_AVAILABLE = True
except ImportError:
    UNDETECTED_AVAILABLE = False
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from ..utils.logger import LoggerMixin


class CrunchbaseScraper(LoggerMixin):
    """Automated scraper for Crunchbase company data."""

    def __init__(self, headless: bool = True, debug: bool = False):
        """
        Initialize Crunchbase scraper.

        Args:
            headless: Run browser in headless mode
            debug: Save screenshots and HTML for debugging
        """
        self.headless = headless
        self.debug = debug
        self.driver = None
        self.base_url = "https://www.crunchbase.com"

    def initialize_driver(self):
        """Initialize Chrome WebDriver with Cloudflare bypass."""
        if self.driver:
            return

        self.logger.info("Initializing Chrome WebDriver for Crunchbase (with Cloudflare bypass)...")

        try:
            if UNDETECTED_AVAILABLE:
                # Use undetected-chromedriver to bypass Cloudflare
                options = uc.ChromeOptions()
                
                if self.headless:
                    options.add_argument('--headless=new')
                
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--disable-blink-features=AutomationControlled')
                
                # Create undetected Chrome instance
                self.driver = uc.Chrome(options=options, version_main=None)
                
                self.logger.info("✓ Undetected Chrome WebDriver initialized (Cloudflare bypass enabled)")
                
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
                
                self.logger.info("✓ Regular Chrome WebDriver initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize WebDriver: {e}")
            raise

    def enrich_companies(self, companies: List[str]) -> List[Dict]:
        """
        Enrich multiple companies.

        Args:
            companies: List of company names

        Returns:
            List of enriched company dictionaries
        """
        if not self.driver:
            self.initialize_driver()

        enriched_data = []
        total = len(companies)

        self.logger.info(f"Starting enrichment for {total} companies...")

        for i, company_name in enumerate(companies, 1):
            self.logger.info(f"Processing {i}/{total}: {company_name}")
            
            try:
                data = self.enrich_company(company_name)
                enriched_data.append(data)
                
                # Brief delay to avoid rate limiting
                time.sleep(2)
                
            except Exception as e:
                self.logger.error(f"Failed to enrich {company_name}: {e}")
                enriched_data.append({
                    'company_name': company_name,
                    'revenue_range': 'Unknown',
                    'company_size': 'Unknown',
                    'funding_stage': 'Unknown',
                    'status': 'ERROR',
                    'error': str(e)
                })

        self.logger.info(f"Enrichment complete. {len(enriched_data)} companies processed.")
        return enriched_data

    def enrich_company(self, company_name: str) -> Dict:
        """
        Enrich a single company from Crunchbase.

        Args:
            company_name: Name of the company

        Returns:
            Dictionary with enriched data
        """
        # Try direct URL first (more reliable)
        slug = self._company_name_to_slug(company_name)
        direct_url = f"{self.base_url}/organization/{slug}"
        
        try:
            self.logger.debug(f"Trying direct URL: {direct_url}")
            self.driver.get(direct_url)
            time.sleep(3)  # Wait for page load
            
            # Check if page loaded successfully (not 404)
            page_source = self.driver.page_source.lower()
            
            if 'page not found' in page_source or '404' in page_source or 'no results' in page_source:
                # Direct URL failed, try search
                self.logger.debug(f"Direct URL failed, trying search for: {company_name}")
                return self._search_and_enrich(company_name)
            
            # Page found, extract data
            data = self._extract_company_data(company_name)
            data['status'] = 'SUCCESS'
            data['crunchbase_url'] = direct_url
            
            return data
                
        except Exception as e:
            self.logger.error(f"Error enriching {company_name}: {e}")
            # Try search as fallback
            try:
                return self._search_and_enrich(company_name)
            except:
                return {
                    'company_name': company_name,
                    'revenue_range': 'Unknown',
                    'company_size': 'Unknown',
                    'funding_stage': 'Private',
                    'total_funding': 'Unknown',
                    'last_funding_date': 'Unknown',
                    'status': 'ERROR',
                    'error': str(e)
                }

    def _company_name_to_slug(self, company_name: str) -> str:
        """
        Convert company name to Crunchbase URL slug.
        
        Examples:
            "AccessHope" -> "accesshope"
            "Blue Cross Blue Shield" -> "blue-cross-blue-shield"
            "McKinsey & Company" -> "mckinsey-company"
        """
        import re
        
        # Convert to lowercase
        slug = company_name.lower()
        
        # Remove special characters and replace with hyphen
        slug = re.sub(r'[^\w\s-]', '', slug)  # Remove &, ., etc.
        slug = re.sub(r'[\s_]+', '-', slug)   # Replace spaces with hyphens
        slug = re.sub(r'-+', '-', slug)       # Remove multiple hyphens
        slug = slug.strip('-')                # Remove leading/trailing hyphens
        
        return slug

    def _search_and_enrich(self, company_name: str) -> Dict:
        """
        Search for company and enrich (fallback method).
        
        Args:
            company_name: Company name to search
            
        Returns:
            Enriched company data
        """
        search_url = f"{self.base_url}/search?q={company_name.replace(' ', '%20')}"
        
        try:
            self.driver.get(search_url)
            time.sleep(2)
            
            # Try to find and click the first company result
            try:
                first_result = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/organization/']"))
                )
                company_url = first_result.get_attribute('href')
                
                # Navigate to company page
                self.driver.get(company_url)
                time.sleep(3)
                
                # Extract company data
                data = self._extract_company_data(company_name)
                data['status'] = 'SUCCESS'
                data['crunchbase_url'] = company_url
                
                return data
                
            except TimeoutException:
                self.logger.warning(f"No Crunchbase profile found for: {company_name}")
                return {
                    'company_name': company_name,
                    'revenue_range': 'Unknown',
                    'company_size': 'Unknown',
                    'funding_stage': 'Private',
                    'total_funding': 'Unknown',
                    'last_funding_date': 'Unknown',
                    'status': 'NOT_FOUND'
                }
                
        except Exception as e:
            self.logger.error(f"Search failed for {company_name}: {e}")
            return {
                'company_name': company_name,
                'revenue_range': 'Unknown',
                'company_size': 'Unknown',
                'funding_stage': 'Private',
                'total_funding': 'Unknown',
                'last_funding_date': 'Unknown',
                'status': 'NOT_FOUND'
            }

    def _extract_company_data(self, company_name: str) -> Dict:
        """Extract data from Crunchbase company page."""
        data = {
            'company_name': company_name,
            'revenue_range': 'Unknown',
            'company_size': 'Unknown',
            'funding_stage': 'Unknown',
            'total_funding': 'Unknown',
            'last_funding_date': 'Unknown',
            'headquarters': 'Unknown',
            'founded_year': 'Unknown',
        }

        try:
            # Wait for page to fully load
            time.sleep(3)
            
            # Wait for main content to load
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except:
                pass
            
            # Get visible text (better than page source)
            try:
                body_elem = self.driver.find_element(By.TAG_NAME, "body")
                visible_text = body_elem.text
            except:
                visible_text = ""
            
            # Get all text content for searching
            page_text = self.driver.page_source
            
            self.logger.debug(f"Page loaded, extracting data for {company_name}...")
            
            # Debug mode: save screenshot and HTML
            if self.debug:
                try:
                    import os
                    os.makedirs('debug_crunchbase', exist_ok=True)
                    
                    slug = self._company_name_to_slug(company_name)
                    screenshot_path = f'debug_crunchbase/{slug}.png'
                    html_path = f'debug_crunchbase/{slug}.html'
                    
                    self.driver.save_screenshot(screenshot_path)
                    with open(html_path, 'w', encoding='utf-8') as f:
                        f.write(self.driver.page_source)
                    
                    self.logger.debug(f"Debug files saved: {screenshot_path}, {html_path}")
                except Exception as e:
                    self.logger.debug(f"Failed to save debug files: {e}")
            
            # Try multiple strategies to extract company size
            try:
                # Strategy 1: Look for employee range in visible text (e.g., "101-250")
                employee_patterns = [
                    r'(\d+-\d+)\s*(?:employees)?',
                    r'(\d+,\d+)\s*(?:employees)?',
                ]
                
                # Try direct text search
                import re
                for pattern in employee_patterns:
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        employees = match.group(1).replace(',', '')
                        data['company_size'] = employees
                        self.logger.debug(f"Found employee count: {employees}")
                        break
                
                # If not found, try XPath
                if data['company_size'] == 'Unknown':
                    try:
                        # Look for employee info in various locations
                        employee_selectors = [
                            "//dd[contains(@class, 'employee')]",
                            "//*[contains(text(), '101-250')]",
                            "//*[contains(text(), '51-200')]",
                            "//*[contains(text(), '201-500')]",
                            "//*[contains(text(), '11-50')]",
                            "//*[contains(text(), '1-10')]",
                            "//*[contains(text(), '501-1000')]",
                            "//*[contains(text(), '1001-5000')]",
                            "//*[contains(text(), '5000+')]",
                        ]
                        
                        for selector in employee_selectors:
                            try:
                                elem = self.driver.find_element(By.XPATH, selector)
                                employees = elem.text.strip()
                                if employees and any(char.isdigit() for char in employees):
                                    data['company_size'] = employees
                                    break
                            except:
                                continue
                                
                    except Exception as e:
                        self.logger.debug(f"Employee count extraction failed: {e}")
                        
            except Exception as e:
                self.logger.debug(f"Employee extraction error: {e}")

            # Extract funding stage - look for Series A, Series B, etc.
            try:
                funding_keywords = ['Seed', 'Series A', 'Series B', 'Series C', 'Series D', 'Series E', 
                                   'Series F', 'IPO', 'Private', 'Public', 'Acquired']
                
                for keyword in funding_keywords:
                    if keyword in page_text:
                        # Verify it's actually the funding stage, not just mentioned
                        if re.search(rf'\b{keyword}\b', page_text, re.IGNORECASE):
                            data['funding_stage'] = keyword
                            self.logger.debug(f"Found funding stage: {keyword}")
                            break
                            
            except Exception as e:
                self.logger.debug(f"Funding stage extraction error: {e}")

            # Extract headquarters/location
            try:
                # Look for location patterns
                location_patterns = [
                    r'([A-Z][a-z]+,\s*[A-Z][a-z]+,\s*United States)',
                    r'([A-Z][a-z]+,\s*[A-Z]{2})',
                ]
                
                for pattern in location_patterns:
                    match = re.search(pattern, page_text)
                    if match:
                        data['headquarters'] = match.group(1)
                        break
                        
            except Exception as e:
                self.logger.debug(f"Headquarters extraction error: {e}")

            # Extract founded year
            try:
                # Look for 4-digit year
                founded_match = re.search(r'Founded[:\s]+(\d{4})', page_text, re.IGNORECASE)
                if founded_match:
                    data['founded_year'] = founded_match.group(1)
                    
            except Exception as e:
                self.logger.debug(f"Founded year extraction error: {e}")

            # Infer revenue from funding if we found funding info
            if data['funding_stage'] != 'Unknown':
                data['revenue_range'] = self._infer_revenue_from_stage(data['funding_stage'])

        except Exception as e:
            self.logger.error(f"Error extracting data: {e}")

        return data
    
    def _infer_revenue_from_stage(self, stage: str) -> str:
        """Infer approximate revenue range from funding stage."""
        stage_lower = stage.lower()
        
        if 'seed' in stage_lower or 'pre-seed' in stage_lower:
            return '<$1M'
        elif 'series a' in stage_lower:
            return '$1M-$10M'
        elif 'series b' in stage_lower:
            return '$10M-$50M'
        elif 'series c' in stage_lower:
            return '$50M-$100M'
        elif 'series d' in stage_lower or 'series e' in stage_lower:
            return '$100M-$500M'
        elif 'ipo' in stage_lower or 'public' in stage_lower:
            return '$500M+'
        else:
            return 'Unknown'

    def _normalize_company_size(self, size_text: str) -> str:
        """Normalize company size to standard ranges."""
        size_text = size_text.lower().replace(',', '')
        
        # Try to extract number
        import re
        numbers = re.findall(r'\d+', size_text)
        
        if not numbers:
            return 'Unknown'
        
        size = int(numbers[0])
        
        if size <= 10:
            return '1-10'
        elif size <= 50:
            return '11-50'
        elif size <= 200:
            return '51-200'
        elif size <= 500:
            return '201-500'
        elif size <= 1000:
            return '501-1000'
        elif size <= 5000:
            return '1001-5000'
        else:
            return '5000+'

    def _infer_revenue_from_funding(self, funding_text: str) -> str:
        """Infer revenue range from total funding amount."""
        if funding_text == 'Unknown':
            return 'Unknown'
        
        # Extract amount
        import re
        funding_text = funding_text.upper()
        
        if 'M' in funding_text:
            numbers = re.findall(r'[\d.]+', funding_text)
            if numbers:
                amount = float(numbers[0])
                if amount < 1:
                    return '<$1M'
                elif amount < 10:
                    return '$1M-$10M'
                elif amount < 50:
                    return '$10M-$50M'
                elif amount < 100:
                    return '$50M-$100M'
                else:
                    return '$100M+'
        elif 'B' in funding_text:
            return '$500M+'
        
        return 'Unknown'

    def close(self):
        """Close the browser."""
        if self.driver:
            self.driver.quit()
            self.logger.info("Browser closed")

    def __enter__(self):
        """Context manager entry."""
        self.initialize_driver()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def __repr__(self) -> str:
        """String representation."""
        return "CrunchbaseScraper()"
