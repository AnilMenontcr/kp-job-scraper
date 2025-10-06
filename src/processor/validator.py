"""
Validator Module
~~~~~~~~~~~~~~~~

Validates job data quality and calculates completeness scores.
"""

import re
from typing import Dict, List

from ..utils.logger import LoggerMixin


class DataValidator(LoggerMixin):
    """Validates job data quality."""

    # Required fields that must be present
    REQUIRED_FIELDS = ["job_title", "company_name", "location", "job_url", "date_scraped"]

    # Optional fields that contribute to quality score
    OPTIONAL_FIELDS = [
        "job_summary",
        "date_posted",
        "company_revenue_range",
        "company_size",
        "funding_stage",
    ]

    # US state abbreviations for location validation
    US_STATES = [
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    ]

    def __init__(self):
        """Initialize validator."""
        pass

    def validate_all(self, jobs: List[Dict]) -> List[Dict]:
        """
        Validate all job records and add quality scores.

        Args:
            jobs: List of job dictionaries

        Returns:
            List of validated job dictionaries with quality scores
        """
        self.logger.info(f"Validating {len(jobs)} job records")

        validated_jobs = []
        invalid_count = 0

        for job in jobs:
            if self.validate_job(job):
                job["data_quality_score"] = self.calculate_quality_score(job)
                validated_jobs.append(job)
            else:
                invalid_count += 1
                self.logger.warning(
                    f"Invalid job skipped: {job.get('company_name')} - "
                    f"{job.get('job_title')}"
                )

        self.logger.info(
            f"Validation complete. Valid: {len(validated_jobs)}, "
            f"Invalid: {invalid_count}"
        )

        return validated_jobs

    def validate_job(self, job: Dict) -> bool:
        """
        Validate job has required fields.

        Args:
            job: Job dictionary

        Returns:
            True if valid, False otherwise
        """
        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if not job.get(field):
                self.logger.debug(f"Job missing required field: {field}")
                return False

        # Validate company name length
        company_name = job.get("company_name", "")
        if len(company_name) < 2 or len(company_name) > 200:
            self.logger.debug(f"Invalid company name length: {len(company_name)}")
            return False

        # Validate job title length
        job_title = job.get("job_title", "")
        if len(job_title) < 2 or len(job_title) > 200:
            self.logger.debug(f"Invalid job title length: {len(job_title)}")
            return False

        # Validate URL format
        job_url = job.get("job_url", "")
        if not self._is_valid_url(job_url):
            self.logger.debug(f"Invalid URL format: {job_url}")
            return False

        # Validate location (should contain US state or "United States")
        location = job.get("location", "")
        if not self._is_valid_us_location(location):
            self.logger.debug(f"Invalid US location: {location}")
            # Don't fail validation, just warn
            # return False

        return True

    def calculate_quality_score(self, job: Dict) -> float:
        """
        Calculate data quality score (0.0-1.0).

        Args:
            job: Job dictionary

        Returns:
            Quality score between 0.0 and 1.0
        """
        # Required fields: 60% of score
        required_present = sum(1 for f in self.REQUIRED_FIELDS if job.get(f))
        required_score = (required_present / len(self.REQUIRED_FIELDS)) * 0.6

        # Optional fields: 40% of score
        optional_present = sum(1 for f in self.OPTIONAL_FIELDS if job.get(f))
        optional_score = (optional_present / len(self.OPTIONAL_FIELDS)) * 0.4

        total_score = required_score + optional_score
        return round(total_score, 2)

    def _is_valid_url(self, url: str) -> bool:
        """
        Check if URL is valid.

        Args:
            url: URL string

        Returns:
            True if valid URL format
        """
        if not url:
            return False

        # Simple URL validation
        url_pattern = re.compile(
            r"^https?://"  # http:// or https://
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain
            r"localhost|"  # localhost
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # or IP
            r"(?::\d+)?"  # optional port
            r"(?:/?|[/?]\S+)$",
            re.IGNORECASE,
        )

        return bool(url_pattern.match(url))

    def _is_valid_us_location(self, location: str) -> bool:
        """
        Check if location is valid US location.

        Args:
            location: Location string

        Returns:
            True if valid US location
        """
        if not location:
            return False

        location_upper = location.upper()

        # Check for US state abbreviations
        for state in self.US_STATES:
            if state in location_upper:
                return True

        # Check for "United States" or "USA"
        if "UNITED STATES" in location_upper or "USA" in location_upper:
            return True

        # Check for common US city names (partial list)
        us_cities = [
            "NEW YORK", "LOS ANGELES", "CHICAGO", "HOUSTON", "PHOENIX",
            "PHILADELPHIA", "SAN ANTONIO", "SAN DIEGO", "DALLAS", "SAN JOSE",
            "AUSTIN", "SEATTLE", "DENVER", "BOSTON", "SAN FRANCISCO",
            "PORTLAND", "ATLANTA", "MIAMI", "DETROIT", "WASHINGTON",
        ]

        for city in us_cities:
            if city in location_upper:
                return True

        return False

    def get_quality_stats(self, jobs: List[Dict]) -> Dict:
        """
        Get quality statistics for job list.

        Args:
            jobs: List of job dictionaries

        Returns:
            Dictionary with quality statistics
        """
        if not jobs:
            return {
                "total_jobs": 0,
                "avg_quality_score": 0.0,
                "high_quality_count": 0,
                "medium_quality_count": 0,
                "low_quality_count": 0,
            }

        scores = [job.get("data_quality_score", 0.0) for job in jobs]
        avg_score = sum(scores) / len(scores)

        high_quality = sum(1 for s in scores if s >= 0.8)
        medium_quality = sum(1 for s in scores if 0.5 <= s < 0.8)
        low_quality = sum(1 for s in scores if s < 0.5)

        return {
            "total_jobs": len(jobs),
            "avg_quality_score": round(avg_score, 2),
            "high_quality_count": high_quality,
            "high_quality_pct": round((high_quality / len(jobs)) * 100, 1),
            "medium_quality_count": medium_quality,
            "medium_quality_pct": round((medium_quality / len(jobs)) * 100, 1),
            "low_quality_count": low_quality,
            "low_quality_pct": round((low_quality / len(jobs)) * 100, 1),
        }

    def __repr__(self) -> str:
        """String representation."""
        return "DataValidator()"
