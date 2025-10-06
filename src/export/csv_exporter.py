"""
CSV Exporter Module
~~~~~~~~~~~~~~~~~~~

Generates CSV output and summary statistics.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd

from ..utils.logger import LoggerMixin


class CSVExporter(LoggerMixin):
    """Exports job data to CSV format."""

    # Column order for CSV output
    COLUMN_ORDER = [
        "job_id",
        "job_title",
        "company_name",
        "location",
        "job_summary",
        "job_url",
        "date_posted",
        "date_scraped",
        "role_category",
        "company_revenue_range",
        "company_size",
        "funding_stage",
        "hiring_manager_name",
        "hiring_manager_title",
        "hiring_manager_contact",
        "contact_source",
        "validation_status",
        "data_quality_score",
        "notes",
    ]

    def __init__(self, config: Dict = None):
        """
        Initialize CSV exporter.

        Args:
            config: Configuration dictionary (optional, uses defaults if None)
        """
        self.config = config or {}

    def export(self, jobs: List[Dict], output_dir: str) -> str:
        """
        Export jobs to CSV file.

        Args:
            jobs: List of job dictionaries
            output_dir: Output directory path

        Returns:
            Path to exported CSV file
        """
        self.logger.info(f"Exporting {len(jobs)} jobs to CSV")

        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"job_leads_{timestamp}.csv"
        filepath = output_path / filename

        # Convert to DataFrame
        df = pd.DataFrame(jobs)

        # Ensure all columns exist (add missing ones with empty values)
        for col in self.COLUMN_ORDER:
            if col not in df.columns:
                df[col] = ""

        # Reorder columns
        df = df[self.COLUMN_ORDER]

        # Export to CSV with UTF-8 BOM for Excel compatibility
        csv_config = self.config.get("csv", {})
        encoding = csv_config.get("encoding", "utf-8-sig")
        line_terminator = csv_config.get("line_terminator", "\r\n")

        df.to_csv(
            filepath,
            index=False,
            encoding=encoding,
            lineterminator=line_terminator,
        )

        self.logger.info(f"Exported CSV to {filepath}")
        return str(filepath)

    def generate_summary(self, jobs: List[Dict], output_dir: str) -> str:
        """
        Generate summary statistics file.

        Args:
            jobs: List of job dictionaries
            output_dir: Output directory path

        Returns:
            Path to summary file
        """
        self.logger.info("Generating summary statistics")

        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"summary_{timestamp}.txt"
        filepath = output_path / filename

        # Create DataFrame for analysis
        df = pd.DataFrame(jobs)

        # Generate summary text
        summary = self._build_summary_text(df)

        # Write to file
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(summary)

        self.logger.info(f"Generated summary at {filepath}")
        return str(filepath)

    def _build_summary_text(self, df: pd.DataFrame) -> str:
        """
        Build summary statistics text.

        Args:
            df: DataFrame of jobs

        Returns:
            Summary text
        """
        summary_lines = [
            "=" * 60,
            "Job Scraping Summary",
            "=" * 60,
            f"Execution Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Scraper Version: 1.0.0",
            "",
            "-" * 60,
            "Scraping Results",
            "-" * 60,
            f"Total Jobs Scraped: {len(df)}",
            f"Unique Companies: {df['company_name'].nunique()}",
            "",
        ]

        # Role breakdown
        if "role_category" in df.columns:
            summary_lines.extend([
                "-" * 60,
                "Role Breakdown",
                "-" * 60,
            ])
            role_counts = df["role_category"].value_counts()
            for role, count in role_counts.items():
                pct = (count / len(df)) * 100
                summary_lines.append(f"{role}: {count} jobs ({pct:.1f}%)")
            summary_lines.append("")

        # Data quality
        if "data_quality_score" in df.columns:
            summary_lines.extend([
                "-" * 60,
                "Data Quality",
                "-" * 60,
            ])
            high_quality = len(df[df["data_quality_score"] >= 0.8])
            high_quality_pct = (high_quality / len(df)) * 100
            summary_lines.append(
                f"Complete Records (≥80% fields): {high_quality} ({high_quality_pct:.1f}%)"
            )

            avg_quality = df["data_quality_score"].mean()
            summary_lines.append(f"Average Quality Score: {avg_quality:.2f}")

            # Missing field counts
            for field in ["job_url", "date_posted", "job_summary"]:
                if field in df.columns:
                    missing = df[field].isna().sum() + (df[field] == "").sum()
                    missing_pct = (missing / len(df)) * 100
                    summary_lines.append(
                        f"Missing {field}: {missing} ({missing_pct:.1f}%)"
                    )
            summary_lines.append("")

        # Geographic distribution
        if "location" in df.columns:
            summary_lines.extend([
                "-" * 60,
                "Geographic Distribution (Top 10)",
                "-" * 60,
            ])

            # Extract state from location
            df_copy = df.copy()
            df_copy["state"] = df_copy["location"].str.extract(r", ([A-Z]{2})$")[0]

            state_counts = df_copy["state"].value_counts().head(10)
            for state, count in state_counts.items():
                if pd.notna(state):
                    pct = (count / len(df)) * 100
                    summary_lines.append(f"{state}: {count} jobs ({pct:.1f}%)")
            summary_lines.append("")

        # Validation status
        if "validation_status" in df.columns:
            summary_lines.extend([
                "-" * 60,
                "Enrichment Status",
                "-" * 60,
            ])
            status_counts = df["validation_status"].value_counts()
            for status, count in status_counts.items():
                summary_lines.append(f"{status}: {count} records")
            summary_lines.append("")

        summary_lines.extend([
            "=" * 60,
            "End of Summary",
            "=" * 60,
        ])

        return "\n".join(summary_lines)

    def generate_enrichment_template(
        self, jobs: List[Dict], output_dir: str, crunchbase_base_url: str = None
    ) -> str:
        """
        Generate enrichment template CSV for manual validation.

        Args:
            jobs: List of job dictionaries
            output_dir: Output directory path
            crunchbase_base_url: Base URL for Crunchbase search

        Returns:
            Path to enrichment template file
        """
        self.logger.info("Generating enrichment template")

        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"companies_to_validate_{timestamp}.csv"
        filepath = output_path / filename

        # Get unique companies
        df = pd.DataFrame(jobs)
        companies = df.groupby("company_name").first().reset_index()

        # Build enrichment template
        template_data = []
        for _, row in companies.iterrows():
            company_name = row["company_name"]

            # Generate Crunchbase search URL
            if crunchbase_base_url:
                search_query = company_name.replace(" ", "%20")
                crunchbase_url = f"{crunchbase_base_url}?q={search_query}"
            else:
                crunchbase_url = f"https://www.crunchbase.com/search?q={company_name.replace(' ', '%20')}"

            template_data.append({
                "Company Name": company_name,
                "Wellfound URL": row.get("job_url", ""),
                "Crunchbase Search URL": crunchbase_url,
                "Revenue Range": "",  # Manual entry
                "Company Size": "",  # Manual entry
                "Funding Stage": "",  # Manual entry
                "Validation Status": "PENDING",
                "Notes": "",
            })

        # Create DataFrame and export
        template_df = pd.DataFrame(template_data)
        template_df.to_csv(filepath, index=False, encoding="utf-8-sig")

        self.logger.info(
            f"Generated enrichment template with {len(template_data)} companies at {filepath}"
        )
        return str(filepath)

    def __repr__(self) -> str:
        """String representation."""
        return "CSVExporter()"
