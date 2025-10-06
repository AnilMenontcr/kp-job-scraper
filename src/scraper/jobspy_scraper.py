"""
JobSpy Scraper Wrapper
~~~~~~~~~~~~~~~~~~~~~~

Wrapper around the python-jobspy library to integrate with our architecture.
Provides anti-bot detection and multi-site scraping capabilities.
"""

from typing import Dict, List
import pandas as pd
import re

try:
    from jobspy import scrape_jobs
    JOBSPY_AVAILABLE = True
except ImportError:
    JOBSPY_AVAILABLE = False

from ..utils.logger import LoggerMixin


class JobSpyScraper(LoggerMixin):
    """Wrapper around JobSpy library for scraping jobs."""
    
    def __init__(self, config: Dict = None):
        """
        Initialize JobSpy scraper.
        
        Args:
            config: Configuration dictionary
        """
        if not JOBSPY_AVAILABLE:
            raise ImportError(
                "JobSpy not installed. Install with: pip install python-jobspy"
            )
        
        self.config = config or {}
        self.logger.info("Initialized JobSpy scraper")
    
    def scrape_all_roles(self) -> List[Dict]:
        """
        Scrape jobs for all configured roles.
        
        Returns:
            List of job dictionaries
        """
        all_jobs = []
        target_roles = self.config.get("target_roles", [])
        location = self.config.get("location", "United States")
        max_companies = self.config.get("max_companies", 100)
        results_wanted = self.config.get("results_wanted", 100)
        hours_old = self.config.get("hours_old", None)
        site_name = self.config.get("site_name", ["indeed"])  # Get site name from config
        
        self.logger.info(f"Starting JobSpy scrape for {len(target_roles)} roles on {', '.join(site_name)}")
        
        for role in target_roles:
            self.logger.info(f"Scraping role: {role}")
            
            try:
                # Use JobSpy to scrape jobs
                scrape_params = {
                    'site_name': site_name,
                    'search_term': role,
                    'location': location,
                    'results_wanted': results_wanted,
                    'hours_old': hours_old,
                    'verbose': 1  # Errors + warnings
                }
                
                # Add site-specific parameters
                if 'indeed' in site_name:
                    scrape_params['country_indeed'] = 'USA'
                elif 'linkedin' in site_name:
                    scrape_params['linkedin_fetch_description'] = True  # This enables company data for LinkedIn!
                    scrape_params['country_indeed'] = 'USA'  # LinkedIn also benefits from country spec
                
                jobs_df = scrape_jobs(**scrape_params)
                
                if jobs_df is None or jobs_df.empty:
                    self.logger.warning(f"No jobs found for role: {role}")
                    continue
                
                # Convert DataFrame to list of dicts matching our schema
                role_jobs = self._convert_jobspy_to_schema(jobs_df, role)
                all_jobs.extend(role_jobs)
                
                self.logger.info(f"✓ Found {len(role_jobs)} jobs for {role}")
                
                # Check if we have enough unique companies
                unique_companies = len(set(j["company_name"] for j in all_jobs))
                self.logger.info(
                    f"Total jobs so far: {len(all_jobs)}, "
                    f"Unique companies: {unique_companies}"
                )
                
                if unique_companies >= max_companies:
                    self.logger.info(f"Reached target of {max_companies} companies")
                    break
                    
            except Exception as e:
                self.logger.error(f"Error scraping {role}: {e}")
                continue
        
        self.logger.info(
            f"Scraping complete. Total jobs: {len(all_jobs)}, "
            f"Unique companies: {len(set(j['company_name'] for j in all_jobs))}"
        )
        
        return all_jobs
    
    def _convert_jobspy_to_schema(self, jobs_df: pd.DataFrame, role: str) -> List[Dict]:
        """
        Convert JobSpy DataFrame to our internal schema.
        
        Args:
            jobs_df: JobSpy DataFrame
            role: Job role searched for
            
        Returns:
            List of job dictionaries matching our schema
        """
        from datetime import datetime
        import re
        
        jobs = []
        
        for _, row in jobs_df.iterrows():
            # Skip if missing critical fields
            if pd.isna(row.get('title')) or pd.isna(row.get('company')):
                continue
            
            # Get the site to determine field mapping
            site = str(row.get('site', 'indeed'))
            
            # Base job data
            job = {
                # Required fields for validator
                'job_title': str(row.get('title', '')),
                'company_name': str(row.get('company', '')),
                'location': self._format_location(row),
                'job_url': str(row.get('job_url', '')),
                'date_scraped': datetime.now().strftime('%Y-%m-%d'),  # Required by validator
                
                # Additional fields
                'job_role': role,
                'job_type': str(row.get('job_type', '')),
                'job_summary': str(row.get('description', ''))[:500] if not pd.isna(row.get('description')) else '',
                
                # Salary information
                'salary_min': self._safe_float(row.get('min_amount')),
                'salary_max': self._safe_float(row.get('max_amount')),
                'salary_interval': str(row.get('interval', '')),
                
                # Metadata
                'site': site,
                'date_posted': str(row.get('date_posted', '')) if not pd.isna(row.get('date_posted')) else '',
            }
            
            # Site-specific company field mapping
            if site == 'linkedin':
                # LinkedIn-specific mapping
                job.update({
                    'company_size': self._extract_linkedin_company_size(row),
                    'company_revenue_range': self._extract_linkedin_company_revenue(row),
                    'headquarters': self._extract_linkedin_headquarters(row),
                    'industry': str(row.get('company_industry', 'Unknown')) if not pd.isna(row.get('company_industry')) else 'Unknown',
                    'founded_year': self._extract_linkedin_founded_year(row),
                    'funding_stage': 'Unknown',
                    'company_url': str(row.get('company_url', '')) if not pd.isna(row.get('company_url')) else '',
                })
            else:
                # Default mapping (works for Indeed and others)
                job.update({
                    'company_size': str(row.get('company_num_employees', 'Unknown')) if not pd.isna(row.get('company_num_employees')) else 'Unknown',
                    'company_revenue_range': str(row.get('company_revenue', 'Unknown')) if not pd.isna(row.get('company_revenue')) else 'Unknown',
                    'headquarters': str(row.get('company_addresses', 'Unknown')) if not pd.isna(row.get('company_addresses')) else 'Unknown',
                    'industry': str(row.get('company_industry', 'Unknown')) if not pd.isna(row.get('company_industry')) else 'Unknown',
                    'founded_year': 'Unknown',  # JobSpy doesn't provide this
                    'funding_stage': 'Unknown',  # Optional field for quality score
                    'company_url': str(row.get('company_url', '')) if not pd.isna(row.get('company_url')) else '',
                })
            
            jobs.append(job)
        
        return jobs
    
    def _extract_linkedin_company_size(self, row) -> str:
        """Extract company size from LinkedIn job description."""
        description = str(row.get('description', ''))
        
        # Look for company size patterns in description
        size_patterns = [
            r'(\d+\s*to\s*\d+\s*employees|\d+\+\s*employees)',
            r'(\d+\s*to\s*\d+|\d+\+)\s*people',
            r'(more than\s*\d+\s*employees)',
            r'(over\s*\d+\s*employees)',
            r'(10000\+|5001\+|1001\+|501\+|201\+|51\+|11\+|1\+)',
            r'(large|medium|small)\s*company',
            r'(fortune\s*500|fortune\s*1000)',
            r'(startup|established)\s*company'
        ]
        
        for pattern in size_patterns:
            matches = re.findall(pattern, description, re.I)
            if matches:
                return matches[0]
        
        return 'Unknown'
    
    def _extract_linkedin_company_revenue(self, row) -> str:
        """Extract company revenue from LinkedIn job description."""
        description = str(row.get('description', ''))
        
        # Look for revenue patterns
        revenue_patterns = [
            r'\$(\d+(?:\.\d+)?)\s*(billion|million|thousand)\s*revenue',
            r'revenue.*?\$?(\d+(?:\.\d+)?)\s*(b|m|k)',
            r'(\d+(?:\.\d+)?)\s*(billion|million|thousand)\s*revenue',
            r'annual\s*revenue.*?\$?(\d+(?:\.\d+)?)',
            r'generates.*?\$?(\d+(?:\.\d+)?)\s*(b|m|k)'
        ]
        
        for pattern in revenue_patterns:
            matches = re.findall(pattern, description, re.I)
            if matches:
                match = matches[0]
                if isinstance(match, tuple):
                    # Handle pattern groups
                    amount, unit = match
                    return f"${amount} {unit}"
                else:
                    return f"${match}"
        
        return 'Unknown'
    
    def _extract_linkedin_headquarters(self, row) -> str:
        """Extract headquarters from LinkedIn job description."""
        description = str(row.get('description', ''))
        location = str(row.get('location', ''))
        
        # If we have a good location, use that
        if location and location != 'Unknown' and len(location) > 3:
            return location
        
        # Look for headquarters patterns in description
        hq_patterns = [
            r'headquartered\s*in\s*([^\.]+)',
            r'based\s*in\s*([^\.]+)',
            r'located\s*in\s*([^\.]+)',
            r'office\s*in\s*([^\.]+)'
        ]
        
        for pattern in hq_patterns:
            matches = re.findall(pattern, description, re.I)
            if matches:
                return matches[0].strip()
        
        return 'Unknown'
    
    def _extract_linkedin_founded_year(self, row) -> str:
        """Extract founded year from LinkedIn job description."""
        description = str(row.get('description', ''))
        
        # Look for founded year patterns
        founded_patterns = [
            r'founded\s*in\s*(\d{4})',
            r'established\s*in\s*(\d{4})',
            r'since\s*(\d{4})',
            r'founded\s*(\d{4})'
        ]
        
        for pattern in founded_patterns:
            matches = re.findall(pattern, description, re.I)
            if matches:
                return matches[0]
        
        return 'Unknown'
    
    def _format_location(self, row) -> str:
        """Format location from JobSpy row."""
        city = str(row.get('city', ''))
        state = str(row.get('state', ''))
        
        if city and state:
            return f"{city}, {state}"
        elif city:
            return city
        elif state:
            return state
        else:
            return "Remote"
    
    def _safe_float(self, value) -> float:
        """Safely convert value to float."""
        try:
            if pd.isna(value) or value is None or value == '':
                return 0.0
            return float(value)
        except (ValueError, TypeError):
            return 0.0

