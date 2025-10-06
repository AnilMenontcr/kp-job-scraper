"""
Indeed Selenium Scraper Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Uses Selenium WebDriver to scrape Indeed (bypasses 403 errors).
"""

import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote_plus

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup

try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

from ..utils.logger import LoggerMixin


class IndeedSeleniumScraper(LoggerMixin):
    """Selenium-based scraper for Indeed job listings."""

    def __init__(self, config: Dict):
        """
        Initialize Indeed Selenium scraper.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.driver = None
        self.jobs_scraped: List[Dict] = []
        self.base_url = "https://www.indeed.com"

    def initialize_driver(self, headless: bool = True):
        """
        Initialize Chrome WebDriver.

        Args:
            headless: Run browser in headless mode (no GUI)
        """
        self.logger.info("Initializing Chrome WebDriver...")

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
            # Try system ChromeDriver first (more reliable in WSL)
            try:
                self.driver = webdriver.Chrome(options=chrome_options)
                self.logger.info("Using system ChromeDriver")
            except Exception as e:
                self.logger.debug(f"System ChromeDriver failed: {e}")
                
                # Fallback to webdriver-manager
                if WEBDRIVER_MANAGER_AVAILABLE:
                    self.logger.info("Trying webdriver-manager...")
                    service = Service(ChromeDriverManager().install())
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                else:
                    raise Exception("ChromeDriver not found. Please install: sudo apt-get install chromium-chromedriver")
            
            # Remove webdriver property to avoid detection
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                '''
            })
            
            self.logger.info("✓ Chrome WebDriver initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize WebDriver: {e}")
            raise

    def scrape_all_roles(self) -> List[Dict]:
        """
        Scrape jobs for all target roles.

        Returns:
            List of job dictionaries
        """
        if not self.driver:
            self.initialize_driver(headless=self.config.get('headless', True))

        all_jobs = []
        target_roles = self.config.get("target_roles", [])
        max_companies = self.config.get("max_companies", 100)

        self.logger.info(f"Starting Indeed scrape for {len(target_roles)} roles")

        try:
            for role in target_roles:
                self.logger.info(f"Scraping role: {role}")
                jobs = self.scrape_role(role)
                all_jobs.extend(jobs)

                # Check if we have enough unique companies
                unique_companies = len(set(j["company_name"] for j in all_jobs))
                self.logger.info(
                    f"Total jobs so far: {len(all_jobs)}, "
                    f"Unique companies: {unique_companies}"
                )

                if unique_companies >= max_companies:
                    self.logger.info(f"Reached target of {max_companies} companies")
                    break

        finally:
            self.close()

        self.logger.info(
            f"Scraping complete. Total jobs: {len(all_jobs)}, "
            f"Unique companies: {len(set(j['company_name'] for j in all_jobs))}"
        )

        return all_jobs

    def scrape_role(self, role: str) -> List[Dict]:
        """
        Scrape jobs for a specific role.

        Args:
            role: Job role to search for

        Returns:
            List of job dictionaries
        """
        jobs = []
        max_pages = self.config.get("max_pages_per_role", 10)
        location = self.config.get("location", "United States")

        for page in range(max_pages):
            self.logger.info(f"Scraping {role} - Page {page + 1}")

            url = self._build_search_url(role, location, page * 10)
            
            try:
                self.driver.get(url)
                
                # Wait for job cards to load (increased timeout)
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.job_seen_beacon, td.resultContent"))
                    )
                except TimeoutException:
                    # Try alternative selector
                    try:
                        WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-jk], div.slider_item"))
                        )
                    except TimeoutException:
                        self.logger.warning(f"Timeout loading page {page + 1}, trying to parse anyway...")
                
                # Random delay to appear more human-like  
                time.sleep(3 + (page % 2))  # 3-4 seconds
                
                # Scroll to load all content
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
                # Get page source and parse
                html = self.driver.page_source
                job_cards = self._parse_job_listings(html, role)

                if not job_cards:
                    self.logger.warning(f"No jobs found on page {page + 1}, stopping pagination")
                    print(f"DEBUG: Page {page + 1} returned 0 jobs - stopping")
                    break

                jobs.extend(job_cards)
                self.logger.info(f"✓ Page {page + 1}: Found {len(job_cards)} jobs (total: {len(jobs)})")
                print(f"DEBUG: Page {page + 1}: {len(job_cards)} jobs, total: {len(jobs)}")

            except TimeoutException:
                self.logger.warning(f"Timeout loading page {page + 1}, stopping")
                # Return what we have so far
                break
            except Exception as e:
                self.logger.error(f"Error on page {page + 1}: {e}")
                break

        self.logger.info(f"Scraped {len(jobs)} jobs for role: {role}")
        return jobs

    def _build_search_url(self, role: str, location: str, start: int = 0) -> str:
        """
        Construct Indeed search URL.

        Args:
            role: Job role
            location: Location filter
            start: Pagination offset

        Returns:
            Search URL
        """
        query = quote_plus(role)
        loc = quote_plus(location)
        url = f"{self.base_url}/jobs?q={query}&l={loc}"

        if start > 0:
            url += f"&start={start}"

        return url

    def _parse_job_listings(self, html: str, role_category: str) -> List[Dict]:
        """
        Parse job cards from Indeed HTML.

        Args:
            html: HTML content
            role_category: Role category for this search

        Returns:
            List of job dictionaries
        """
        soup = BeautifulSoup(html, "lxml")
        job_cards = []

        # Indeed job card selectors
        cards = soup.select('div.job_seen_beacon, div.jobsearch-SerpJobCard, td.resultContent')

        if not cards:
            self.logger.debug("No job cards found with primary selectors")
            # Try alternative
            cards = soup.select('div[data-jk], div.slider_item')

        self.logger.debug(f"Found {len(cards)} potential job cards")

        for card in cards:
            try:
                job = self._extract_job_data(card, role_category)
                if job and self._validate_job_data(job):
                    job_cards.append(job)

            except Exception as e:
                self.logger.debug(f"Error parsing job card: {e}")
                continue

        return job_cards

    def _extract_job_data(self, card, role_category: str) -> Optional[Dict]:
        """
        Extract job data from Indeed card element.

        Args:
            card: BeautifulSoup element
            role_category: Role category

        Returns:
            Job dictionary or None
        """
        try:
            # Extract job title
            title_elem = card.select_one('h2.jobTitle span[title], h2 a span[title], h2 span, a.jcs-JobTitle')
            job_title = None
            if title_elem:
                job_title = title_elem.get('title') or title_elem.text.strip()

            # Extract company name and profile URL
            company_elem = card.select_one('span.companyName, span[data-testid="company-name"], div.company')
            company_name = company_elem.text.strip() if company_elem else None
            
            # Extract company profile URL (link on company name)
            company_profile_url = None
            if company_elem:
                # Look for link in or around company name
                company_link = company_elem.find_parent('a') or company_elem.find('a')
                if company_link and company_link.get('href'):
                    href = company_link.get('href')
                    if '/cmp/' in href:  # Indeed company profile link
                        if href.startswith('/'):
                            company_profile_url = f"{self.base_url}{href}"
                        else:
                            company_profile_url = href

            # Extract location
            location_elem = card.select_one('div.companyLocation, div[data-testid="text-location"], div.location')
            location = location_elem.text.strip() if location_elem else None

            # Extract job URL
            link_elem = card.select_one('h2.jobTitle a, a.jcs-JobTitle, a[data-jk]')
            job_url = None
            if link_elem and link_elem.get("href"):
                href = link_elem["href"]
                if href.startswith('/'):
                    job_url = f"{self.base_url}{href}"
                elif href.startswith('http'):
                    job_url = href

            # Extract description
            desc_elem = card.select_one('div.job-snippet, div.summary, td.snippetColumn, div[class*="snippet"]')
            job_summary = None
            if desc_elem:
                job_summary = desc_elem.text.strip()[:500]

            # Extract date posted
            date_elem = card.select_one('span.date, span[data-testid="myJobsStateDate"]')
            date_posted = date_elem.text.strip() if date_elem else None

            # Extract salary
            salary_elem = card.select_one('div.salary-snippet, span.salary-snippet-container')
            salary = salary_elem.text.strip() if salary_elem else None

            # Only return if we have minimum data
            if job_title and company_name:
                return {
                    "job_id": self._generate_job_id(company_name, job_title),
                    "job_title": job_title,
                    "company_name": company_name,
                    "company_profile_url": company_profile_url,  # Indeed company page URL
                    "location": location or "Remote",
                    "job_summary": job_summary,
                    "job_url": job_url,
                    "date_posted": date_posted,
                    "date_scraped": datetime.now().isoformat(),
                    "role_category": role_category,
                    "validation_status": "PENDING",
                    "scraper_version": "1.0.0-selenium",
                    "salary": salary,
                    # Hiring manager fields - not available from Indeed search results
                    # Would require clicking into each job + often behind Apply button
                    "hiring_manager_name": "Not available",
                    "hiring_manager_title": "Not available",
                    "hiring_manager_contact": "Not available",
                    "contact_source": "Indeed (contact via Apply button)",
                }

            return None

        except Exception as e:
            self.logger.debug(f"Error extracting job data: {e}")
            return None

    def _generate_job_id(self, company_name: str, job_title: str) -> str:
        """Generate unique job ID."""
        timestamp = str(time.time())
        data = f"{company_name}_{job_title}_{timestamp}"
        hash_obj = hashlib.md5(data.encode())
        return f"IND_{hash_obj.hexdigest()[:10].upper()}"

    def _validate_job_data(self, job: Dict) -> bool:
        """Validate job data has required fields."""
        required_fields = ["job_title", "company_name"]
        for field in required_fields:
            if not job.get(field):
                return False
        return True

    def save_raw_data(self, jobs: List[Dict], output_dir: str) -> str:
        """Save raw scraped data to JSON file."""
        import json

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"raw_jobs_indeed_selenium_{timestamp}.json"
        filepath = output_path / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(jobs, f, indent=2, ensure_ascii=False)

        self.logger.info(f"Saved {len(jobs)} jobs to {filepath}")
        return str(filepath)

    def close(self):
        """Close the browser."""
        if self.driver:
            self.driver.quit()
            self.logger.info("Browser closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def __repr__(self) -> str:
        """String representation."""
        return f"IndeedSeleniumScraper(jobs_scraped={len(self.jobs_scraped)})"
