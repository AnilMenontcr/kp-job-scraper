"""
Indeed Scraper Module
~~~~~~~~~~~~~~~~~~~~~

Scrapes job listings from Indeed.com - no authentication required.
"""

import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from ..utils.logger import LoggerMixin
from .rate_limiter import RateLimiter
from .user_agent_rotator import UserAgentRotator


class IndeedScraper(LoggerMixin):
    """Scraper for Indeed job listings."""

    def __init__(
        self,
        config: Dict,
        rate_limiter: RateLimiter,
        ua_rotator: UserAgentRotator,
    ):
        """
        Initialize Indeed scraper.

        Args:
            config: Configuration dictionary
            rate_limiter: Rate limiter instance
            ua_rotator: User agent rotator instance
        """
        self.config = config
        self.rate_limiter = rate_limiter
        self.ua_rotator = ua_rotator
        self.session = requests.Session()
        self.jobs_scraped: List[Dict] = []
        self.base_url = "https://www.indeed.com"

    def scrape_all_roles(self) -> List[Dict]:
        """
        Scrape jobs for all target roles.

        Returns:
            List of job dictionaries
        """
        all_jobs = []
        target_roles = self.config.get("target_roles", [])
        max_companies = self.config.get("max_companies", 100)

        self.logger.info(f"Starting Indeed scrape for {len(target_roles)} roles")

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
        start = 0  # Indeed uses pagination with 'start' parameter
        max_pages = self.config.get("max_pages_per_role", 10)
        location = self.config.get("location", "United States")

        for page in range(max_pages):
            self.logger.info(f"Scraping {role} - Page {page + 1}")

            url = self._build_search_url(role, location, start)
            html = self._fetch_page(url)

            if not html:
                self.logger.warning(f"Failed to fetch page {page + 1}, stopping")
                break

            job_cards = self._parse_job_listings(html, role)

            if not job_cards:
                self.logger.info(f"No more jobs found on page {page + 1}")
                break

            jobs.extend(job_cards)
            self.logger.info(f"Found {len(job_cards)} jobs on page {page + 1}")

            # Indeed shows 10-15 jobs per page
            start += 10

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
        # URL encode the search terms
        query = quote_plus(role)
        loc = quote_plus(location)

        # Indeed URL structure: /jobs?q=QUERY&l=LOCATION&start=START
        url = f"{self.base_url}/jobs?q={query}&l={loc}"

        if start > 0:
            url += f"&start={start}"

        return url

    def _fetch_page(self, url: str) -> Optional[str]:
        """
        Fetch page with rate limiting and error handling.

        Args:
            url: URL to fetch

        Returns:
            HTML content or None if failed
        """
        # Wait for rate limiter
        wait_time = self.rate_limiter.wait_if_needed()
        self.logger.debug(f"Rate limiter wait: {wait_time:.2f}s")

        # Build headers - Indeed is less strict than Wellfound
        headers = {
            "User-Agent": self.ua_rotator.get_next(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        # Retry logic
        max_retries = self.config.get("retry_attempts", 3)
        backoff_base = self.config.get("retry_backoff_base", 2)

        for attempt in range(max_retries):
            try:
                self.logger.debug(f"Fetching URL (attempt {attempt + 1}): {url}")

                response = self.session.get(
                    url,
                    headers=headers,
                    timeout=self.config.get("timeout_seconds", 15),
                )

                # Handle different status codes
                if response.status_code == 200:
                    self.logger.debug(f"Successfully fetched {url}")
                    return response.text

                elif response.status_code == 429:
                    self.logger.warning("Rate limit detected (429), waiting 60 seconds")
                    time.sleep(60)
                    continue

                elif response.status_code in [403, 451]:
                    self.logger.error(
                        f"Blocked (status {response.status_code}) for URL: {url}"
                    )
                    # Try with different user agent
                    headers["User-Agent"] = self.ua_rotator.get_random()
                    if attempt < max_retries - 1:
                        time.sleep(5)
                        continue
                    return None

                elif response.status_code == 404:
                    self.logger.warning(f"Page not found (404): {url}")
                    return None

                else:
                    self.logger.warning(
                        f"Unexpected status code {response.status_code} for {url}"
                    )
                    return None

            except requests.exceptions.Timeout:
                self.logger.error(f"Timeout fetching {url} (attempt {attempt + 1})")
                if attempt < max_retries - 1:
                    time.sleep(backoff_base**attempt)
                    continue

            except requests.exceptions.RequestException as e:
                self.logger.error(
                    f"Request failed for {url} (attempt {attempt + 1}): {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(backoff_base**attempt)
                    continue

        self.logger.error(f"Failed to fetch {url} after {max_retries} attempts")
        return None

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

        # Indeed uses consistent class names (as of 2025)
        # Main job card container
        cards = soup.select('div.job_seen_beacon, div.jobsearch-SerpJobCard, div[data-jk]')

        if not cards:
            self.logger.debug("No job cards found with primary selectors, trying alternatives")
            # Try alternative selectors
            cards = soup.select('div.slider_container div, td.resultContent')

        self.logger.debug(f"Found {len(cards)} potential job cards")

        for card in cards:
            try:
                job = self._extract_job_data(card, role_category)
                if job and self._validate_job_data(job):
                    job_cards.append(job)
                else:
                    self.logger.debug("Skipping invalid job card")

            except Exception as e:
                self.logger.error(f"Error parsing job card: {e}", exc_info=True)
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
            title_elem = card.select_one('h2.jobTitle span[title], h2 a span[title], h2 span')
            job_title = None
            if title_elem:
                job_title = title_elem.get('title') or title_elem.text.strip()

            # Extract company name
            company_elem = card.select_one('span.companyName, span[data-testid="company-name"]')
            company_name = company_elem.text.strip() if company_elem else None

            # Extract location
            location_elem = card.select_one('div.companyLocation, div[data-testid="text-location"]')
            location = location_elem.text.strip() if location_elem else None

            # Extract job URL
            link_elem = card.select_one('h2.jobTitle a, a.jcs-JobTitle')
            job_url = None
            if link_elem and link_elem.get("href"):
                href = link_elem["href"]
                # Indeed uses relative URLs
                if href.startswith('/'):
                    job_url = f"{self.base_url}{href}"
                elif href.startswith('http'):
                    job_url = href
                else:
                    job_url = f"{self.base_url}/viewjob?jk={href}"

            # Extract description/summary
            desc_elem = card.select_one('div.job-snippet, div.summary, td.snippetColumn')
            job_summary = None
            if desc_elem:
                job_summary = desc_elem.text.strip()[:500]  # First 500 chars

            # Extract date posted (if available)
            date_elem = card.select_one('span.date, span[data-testid="myJobsStateDate"]')
            date_posted = None
            if date_elem:
                date_posted = date_elem.text.strip()

            # Extract salary (if available)
            salary_elem = card.select_one('div.salary-snippet, span.salary-snippet-container')
            salary = salary_elem.text.strip() if salary_elem else None

            # Create job dictionary
            job = {
                "job_id": self._generate_job_id(company_name, job_title),
                "job_title": job_title,
                "company_name": company_name,
                "location": location,
                "job_summary": job_summary,
                "job_url": job_url,
                "date_posted": date_posted,
                "date_scraped": datetime.now().isoformat(),
                "role_category": role_category,
                "validation_status": "PENDING",
                "scraper_version": "1.0.0",
                "salary": salary,  # Extra field for Indeed
            }

            return job

        except Exception as e:
            self.logger.error(f"Error extracting job data: {e}")
            return None

    def _generate_job_id(self, company_name: Optional[str], job_title: Optional[str]) -> str:
        """
        Generate unique job ID.

        Args:
            company_name: Company name
            job_title: Job title

        Returns:
            Unique job ID
        """
        timestamp = str(time.time())
        data = f"{company_name}_{job_title}_{timestamp}"
        hash_obj = hashlib.md5(data.encode())
        return f"IND_{hash_obj.hexdigest()[:10].upper()}"

    def _validate_job_data(self, job: Dict) -> bool:
        """
        Validate job data has required fields.

        Args:
            job: Job dictionary

        Returns:
            True if valid, False otherwise
        """
        required_fields = ["job_title", "company_name"]

        for field in required_fields:
            if not job.get(field):
                self.logger.debug(f"Job missing required field: {field}")
                return False

        return True

    def save_raw_data(self, jobs: List[Dict], output_dir: str) -> str:
        """
        Save raw scraped data to JSON file.

        Args:
            jobs: List of job dictionaries
            output_dir: Output directory path

        Returns:
            Path to saved file
        """
        import json
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"raw_jobs_indeed_{timestamp}.json"
        filepath = output_path / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(jobs, f, indent=2, ensure_ascii=False)

        self.logger.info(f"Saved {len(jobs)} jobs to {filepath}")
        return str(filepath)

    def __repr__(self) -> str:
        """String representation."""
        return f"IndeedScraper(jobs_scraped={len(self.jobs_scraped)})"
