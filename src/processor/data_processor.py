"""
Data Processor Module
~~~~~~~~~~~~~~~~~~~~~

Orchestrates data cleaning, deduplication, and validation.
"""

import json
from pathlib import Path
from typing import Dict, List

from ..utils.logger import LoggerMixin
from .data_cleaner import DataCleaner
from .deduplicator import Deduplicator
from .validator import DataValidator


class DataProcessor(LoggerMixin):
    """Orchestrates data processing pipeline."""

    def __init__(self, config: Dict):
        """
        Initialize data processor.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.cleaner = DataCleaner()
        self.deduplicator = Deduplicator()
        self.validator = DataValidator()

    def process(self, raw_jobs: List[Dict]) -> List[Dict]:
        """
        Process raw jobs through full pipeline.

        Args:
            raw_jobs: List of raw job dictionaries

        Returns:
            List of processed job dictionaries
        """
        self.logger.info(f"Starting data processing pipeline for {len(raw_jobs)} jobs")

        # 1. Clean data
        self.logger.info("Step 1: Cleaning data")
        cleaned = self.cleaner.clean_all(raw_jobs)

        # 2. Deduplicate
        if self.config.get("deduplicate", True):
            self.logger.info("Step 2: Deduplicating")
            deduped = self.deduplicator.deduplicate(cleaned)
            removed = len(cleaned) - len(deduped)
            self.logger.info(f"Removed {removed} duplicates")
        else:
            self.logger.info("Step 2: Skipping deduplication (disabled in config)")
            deduped = cleaned

        # 3. Validate and calculate quality scores
        self.logger.info("Step 3: Validating and scoring")
        validated = self.validator.validate_all(deduped)

        # 4. Filter by minimum quality score if configured
        min_quality = self.config.get("min_quality_score", 0.0)
        if min_quality > 0:
            before_filter = len(validated)
            validated = [j for j in validated if j.get("data_quality_score", 0) >= min_quality]
            filtered = before_filter - len(validated)
            self.logger.info(
                f"Filtered {filtered} jobs below quality threshold {min_quality}"
            )

        self.logger.info(f"Processing complete. Final job count: {len(validated)}")

        return validated

    def save_processed_data(self, jobs: List[Dict], output_dir: str) -> str:
        """
        Save processed data to JSON file.

        Args:
            jobs: List of processed job dictionaries
            output_dir: Output directory path

        Returns:
            Path to saved file
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"processed_jobs_{timestamp}.json"
        filepath = output_path / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(jobs, f, indent=2, ensure_ascii=False)

        self.logger.info(f"Saved {len(jobs)} processed jobs to {filepath}")
        return str(filepath)

    def generate_processing_report(self, jobs: List[Dict]) -> Dict:
        """
        Generate processing statistics report.

        Args:
            jobs: List of processed job dictionaries

        Returns:
            Dictionary with processing statistics
        """
        quality_stats = self.validator.get_quality_stats(jobs)

        # Role breakdown
        role_counts = {}
        for job in jobs:
            role = job.get("role_category", "Unknown")
            role_counts[role] = role_counts.get(role, 0) + 1

        # Company count
        unique_companies = len(set(j.get("company_name") for j in jobs))

        report = {
            "total_jobs": len(jobs),
            "unique_companies": unique_companies,
            "quality_stats": quality_stats,
            "role_breakdown": role_counts,
        }

        return report

    def __repr__(self) -> str:
        """String representation."""
        return "DataProcessor()"
