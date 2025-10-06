"""
Deduplicator Module
~~~~~~~~~~~~~~~~~~~

Removes duplicate job listings.
"""

from typing import Dict, List

from ..utils.logger import LoggerMixin


class Deduplicator(LoggerMixin):
    """Removes duplicate job records."""

    def __init__(self):
        """Initialize deduplicator."""
        pass

    def deduplicate(self, jobs: List[Dict]) -> List[Dict]:
        """
        Remove duplicate jobs based on company name and job title.

        Args:
            jobs: List of job dictionaries

        Returns:
            List of unique job dictionaries
        """
        self.logger.info(f"Deduplicating {len(jobs)} job records")

        seen = {}
        unique_jobs = []
        duplicates_removed = 0

        for job in jobs:
            key = self._generate_key(job)

            if key not in seen:
                seen[key] = job
                unique_jobs.append(job)
            else:
                # Keep most recent job
                existing = seen[key]
                if self._is_more_recent(job, existing):
                    # Replace in both dict and list
                    seen[key] = job
                    idx = unique_jobs.index(existing)
                    unique_jobs[idx] = job
                    self.logger.debug(f"Replaced older duplicate: {key}")
                else:
                    self.logger.debug(f"Skipped older duplicate: {key}")

                duplicates_removed += 1

        self.logger.info(
            f"Deduplication complete. Removed {duplicates_removed} duplicates. "
            f"Unique jobs: {len(unique_jobs)}"
        )

        return unique_jobs

    def _generate_key(self, job: Dict) -> str:
        """
        Generate unique key for deduplication.

        Args:
            job: Job dictionary

        Returns:
            Unique key string
        """
        company = job.get("company_name", "").lower().strip()
        title = job.get("job_title", "").lower().strip()
        return f"{company}::{title}"

    def _is_more_recent(self, job1: Dict, job2: Dict) -> bool:
        """
        Check if job1 is more recent than job2.

        Args:
            job1: First job dictionary
            job2: Second job dictionary

        Returns:
            True if job1 is more recent
        """
        # Try date_posted first
        date1 = job1.get("date_posted")
        date2 = job2.get("date_posted")

        if date1 and date2:
            return date1 > date2

        # Fall back to date_scraped
        date1 = job1.get("date_scraped")
        date2 = job2.get("date_scraped")

        if date1 and date2:
            return date1 > date2

        # If no dates, keep first one (return False)
        return False

    def get_duplicate_stats(self, jobs: List[Dict]) -> Dict:
        """
        Get statistics about duplicates without removing them.

        Args:
            jobs: List of job dictionaries

        Returns:
            Dictionary with duplicate statistics
        """
        seen = set()
        duplicates = []

        for job in jobs:
            key = self._generate_key(job)
            if key in seen:
                duplicates.append(key)
            else:
                seen.add(key)

        return {
            "total_jobs": len(jobs),
            "unique_jobs": len(seen),
            "duplicate_count": len(duplicates),
            "duplicate_keys": duplicates,
        }

    def __repr__(self) -> str:
        """String representation."""
        return "Deduplicator()"
