"""
Main Orchestrator
~~~~~~~~~~~~~~~~~

Entry point for the Wellfound Job Scraper PoC.
"""

import sys
from pathlib import Path

from .export.csv_exporter import CSVExporter
from .processor.data_processor import DataProcessor
from .scraper.rate_limiter import RateLimiter
from .scraper.user_agent_rotator import UserAgentRotator
from .scraper.wellfound_scraper import WellfoundScraper
from .scraper.indeed_scraper import IndeedScraper
from .scraper.indeed_selenium_scraper import IndeedSeleniumScraper
from .utils.config import Config
from .utils.logger import setup_logger


def main():
    """Main execution function."""
    print("=" * 60)
    print("Wellfound Job Scraper PoC v1.0.0")
    print("=" * 60)
    print()

    try:
        # 1. Load configuration
        print("Loading configuration...")
        config = Config("config.yaml")
        config.ensure_directories()
        print("✓ Configuration loaded")

        # 2. Setup logger
        print("Setting up logger...")
        logger = setup_logger(
            name="wellfound_scraper",
            log_dir=config.logging.get("directory", "./logs"),
            log_level=config.logging.get("level", "INFO"),
            console_output=config.logging.get("console_output", True),
            log_format=config.logging.get("format"),
            date_format=config.logging.get("date_format"),
        )
        print("✓ Logger initialized")
        logger.info("=" * 60)
        logger.info("Starting Wellfound Job Scraper PoC")
        logger.info("=" * 60)

        # 3. Initialize components
        logger.info("Initializing scraper components...")
        rate_limiter = RateLimiter(
            max_requests_per_hour=config.rate_limiting.get("max_requests_per_hour", 50),
            min_delay_seconds=config.rate_limiting.get("min_delay_seconds", 3.0),
            max_delay_seconds=config.rate_limiting.get("max_delay_seconds", 8.0),
        )
        logger.info(f"✓ Rate limiter initialized: {rate_limiter}")

        ua_rotator = UserAgentRotator()
        logger.info(f"✓ User agent rotator initialized: {ua_rotator}")

        # Select scraper based on configuration
        job_board = config.scraping.get("job_board", "indeed").lower()
        use_selenium = config.scraping.get("use_selenium", True)
        
        if job_board == "indeed":
            if use_selenium:
                # Use Selenium scraper (bypasses 403 errors)
                scraper = IndeedSeleniumScraper(config=config.scraping)
                logger.info("✓ Indeed Selenium scraper initialized")
                print("Using job board: Indeed (Selenium)")
            else:
                # Use requests-based scraper (may get 403 errors)
                scraper = IndeedScraper(
                    config=config.scraping,
                    rate_limiter=rate_limiter,
                    ua_rotator=ua_rotator,
                )
                logger.info("✓ Indeed scraper initialized")
                print("Using job board: Indeed (requests)")
        elif job_board == "wellfound":
            scraper = WellfoundScraper(
                config=config.scraping,
                rate_limiter=rate_limiter,
                ua_rotator=ua_rotator,
            )
            logger.info("✓ Wellfound scraper initialized")
            print("Using job board: Wellfound")
        else:
            logger.error(f"Unknown job board: {job_board}")
            print(f"✗ Error: Unknown job board '{job_board}' in config.yaml")
            print("  Valid options: 'indeed' or 'wellfound'")
            return 1

        # 4. Scraping phase
        logger.info("")
        logger.info("=" * 60)
        logger.info("PHASE 1: SCRAPING")
        logger.info("=" * 60)
        print("\nPhase 1: Scraping job listings...")

        raw_jobs = scraper.scrape_all_roles()
        logger.info(f"Scraping complete. Total jobs: {len(raw_jobs)}")

        if not raw_jobs:
            logger.warning("No jobs scraped. Exiting.")
            print("⚠ No jobs found. Please check the logs for details.")
            return 1

        # Save raw data
        raw_data_path = scraper.save_raw_data(
            raw_jobs, config.data.get("raw_dir", "./data/raw")
        )
        print(f"✓ Scraped {len(raw_jobs)} jobs")
        print(f"✓ Raw data saved to: {raw_data_path}")

        # 5. Processing phase
        logger.info("")
        logger.info("=" * 60)
        logger.info("PHASE 2: DATA PROCESSING")
        logger.info("=" * 60)
        print("\nPhase 2: Processing data...")

        processor = DataProcessor(config.processing)
        processed_jobs = processor.process(raw_jobs)

        if not processed_jobs:
            logger.warning("No jobs passed validation. Exiting.")
            print("⚠ No valid jobs after processing. Please check the logs.")
            return 1

        # Save processed data
        processed_data_path = processor.save_processed_data(
            processed_jobs, config.data.get("processed_dir", "./data/processed")
        )
        print(f"✓ Processed {len(processed_jobs)} jobs")
        print(f"✓ Processed data saved to: {processed_data_path}")

        # Generate processing report
        report = processor.generate_processing_report(processed_jobs)
        logger.info(f"Processing report: {report}")

        # 6. Export phase
        logger.info("")
        logger.info("=" * 60)
        logger.info("PHASE 3: EXPORT")
        logger.info("=" * 60)
        print("\nPhase 3: Exporting results...")

        exporter = CSVExporter(config.output)
        output_dir = config.data.get("output_dir", "./data/output")

        # Export main CSV
        csv_path = exporter.export(processed_jobs, output_dir)
        print(f"✓ CSV exported to: {csv_path}")

        # Generate summary
        summary_path = exporter.generate_summary(processed_jobs, output_dir)
        print(f"✓ Summary generated: {summary_path}")

        # Generate enrichment template if configured
        if config.enrichment.get("generate_template", True):
            crunchbase_url = config.enrichment.get("crunchbase_search_url")
            template_path = exporter.generate_enrichment_template(
                processed_jobs, output_dir, crunchbase_url
            )
            print(f"✓ Enrichment template: {template_path}")

        # 7. Final summary
        logger.info("")
        logger.info("=" * 60)
        logger.info("EXECUTION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Total jobs scraped: {len(raw_jobs)}")
        logger.info(f"Jobs after processing: {len(processed_jobs)}")
        logger.info(f"Unique companies: {report['unique_companies']}")
        logger.info(f"Average quality score: {report['quality_stats']['avg_quality_score']}")
        logger.info(f"Output directory: {output_dir}")

        print("\n" + "=" * 60)
        print("✓ Scraping Complete!")
        print("=" * 60)
        print(f"Total Jobs: {len(processed_jobs)}")
        print(f"Unique Companies: {report['unique_companies']}")
        print(f"Average Quality: {report['quality_stats']['avg_quality_score']:.2f}")
        print(f"\nOutput files saved to: {output_dir}")
        print("\nNext steps:")
        print("1. Review the CSV file in Excel/Google Sheets")
        print("2. Use the enrichment template to validate companies via Crunchbase")
        print("3. See docs/Enrichment_SOP.md for detailed instructions")
        print("=" * 60)

        return 0

    except FileNotFoundError as e:
        print(f"\n✗ Error: {e}")
        print("\nPlease ensure:")
        print("1. config.yaml exists (copy from config.sample.yaml)")
        print("2. All required directories are accessible")
        return 1

    except ValueError as e:
        print(f"\n✗ Configuration Error: {e}")
        print("\nPlease check your config.yaml file")
        return 1

    except KeyboardInterrupt:
        print("\n\n⚠ Execution interrupted by user")
        if "logger" in locals():
            logger.warning("Execution interrupted by user")
        return 1

    except Exception as e:
        print(f"\n✗ Fatal Error: {e}")
        if "logger" in locals():
            logger.critical(f"Fatal error: {e}", exc_info=True)
        print("\nPlease check the logs for details")
        return 1


if __name__ == "__main__":
    sys.exit(main())
