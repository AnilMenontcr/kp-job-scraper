"""
Data Cleaner Module
~~~~~~~~~~~~~~~~~~~

Cleans and normalizes scraped job data.
"""

import re
from typing import Dict, List

from ..utils.logger import LoggerMixin


class DataCleaner(LoggerMixin):
    """Cleans and normalizes job data."""

    # Company name suffixes to remove for normalization
    COMPANY_SUFFIXES = [
        ", Inc.",
        " Inc.",
        ", LLC",
        " LLC",
        ", Ltd.",
        " Ltd.",
        ", Corp.",
        " Corp.",
        ", Corporation",
        " Corporation",
        ", Co.",
        " Co.",
    ]

    def __init__(self):
        """Initialize data cleaner."""
        pass

    def clean_all(self, jobs: List[Dict]) -> List[Dict]:
        """
        Clean all job records.

        Args:
            jobs: List of job dictionaries

        Returns:
            List of cleaned job dictionaries
        """
        self.logger.info(f"Cleaning {len(jobs)} job records")
        cleaned_jobs = [self.clean_job(job) for job in jobs]
        self.logger.info("Cleaning complete")
        return cleaned_jobs

    def clean_job(self, job: Dict) -> Dict:
        """
        Clean individual job record.

        Args:
            job: Job dictionary

        Returns:
            Cleaned job dictionary
        """
        cleaned = job.copy()

        # Clean company name
        if "company_name" in cleaned and cleaned["company_name"]:
            cleaned["company_name"] = self._clean_company_name(cleaned["company_name"])

        # Clean location
        if "location" in cleaned and cleaned["location"]:
            cleaned["location"] = self._clean_location(cleaned["location"])

        # Clean job title
        if "job_title" in cleaned and cleaned["job_title"]:
            cleaned["job_title"] = self._clean_text(cleaned["job_title"])

        # Clean job summary
        if "job_summary" in cleaned and cleaned["job_summary"]:
            cleaned["job_summary"] = self._clean_text(cleaned["job_summary"])

        return cleaned

    def _clean_company_name(self, name: str) -> str:
        """
        Normalize company name.

        Args:
            name: Company name

        Returns:
            Normalized company name
        """
        # Remove extra whitespace
        name = " ".join(name.split())

        # Remove common suffixes for better deduplication
        for suffix in self.COMPANY_SUFFIXES:
            if name.endswith(suffix):
                name = name[: -len(suffix)]
                break

        return name.strip()

    def _clean_location(self, location: str) -> str:
        """
        Standardize location format.

        Args:
            location: Location string

        Returns:
            Standardized location
        """
        # Remove extra whitespace
        location = " ".join(location.split())

        # Remove "United States" if present
        location = location.replace(", United States", "")
        location = location.replace("United States", "")

        # Remove "USA" if present
        location = location.replace(", USA", "")
        location = location.replace("USA", "")

        return location.strip()

    def _clean_text(self, text: str) -> str:
        """
        Clean general text field.

        Args:
            text: Text to clean

        Returns:
            Cleaned text
        """
        # Remove extra whitespace
        text = " ".join(text.split())

        # Remove special characters that might cause issues
        text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")

        return text.strip()

    def __repr__(self) -> str:
        """String representation."""
        return "DataCleaner()"
