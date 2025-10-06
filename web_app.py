"""
Job Scraper Web Application
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Simple Flask web UI for job scraping and enrichment.
"""

from flask import Flask, render_template, request, jsonify, send_file
from pathlib import Path
import threading
import json
from datetime import datetime
import pandas as pd

# Import scraper modules
from src.scraper.indeed_selenium_scraper import IndeedSeleniumScraper
from src.scraper.jobspy_scraper import JobSpyScraper
from src.processor.data_processor import DataProcessor
from src.export.csv_exporter import CSVExporter
from src.enrichment import IndeedCompanyEnricher
from src.utils.config import Config

app = Flask(__name__)

# Store job status
job_status = {}

# Configuration
config = Config()


@app.route('/')
def index():
    """Home page."""
    return render_template('index.html')


@app.route('/api/scrape', methods=['POST'])
def start_scrape():
    """Start scraping job."""
    data = request.json
    
    job_role = data.get('job_role')
    location = data.get('location', 'United States')
    job_board = data.get('job_board', 'indeed')
    max_companies = data.get('max_companies', 50)
    enrich = data.get('enrich', True)
    
    # Validate inputs
    if not job_role:
        return jsonify({'error': 'Job role is required'}), 400
    
    # Generate job ID
    job_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Initialize status
    job_status[job_id] = {
        'status': 'started',
        'progress': 0,
        'message': 'Initializing scraper...',
        'job_role': job_role,
        'location': location,
        'job_board': job_board,
        'max_companies': max_companies
    }
    
    # Start scraping in background thread
    thread = threading.Thread(
        target=run_scrape_job,
        args=(job_id, job_role, location, job_board, max_companies, enrich)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({'job_id': job_id})


@app.route('/api/status/<job_id>')
def get_status(job_id):
    """Get job status."""
    if job_id not in job_status:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify(job_status[job_id])


@app.route('/api/download/<job_id>')
def download_results(job_id):
    """Download results as Excel file."""
    if job_id not in job_status:
        return jsonify({'error': 'Job not found'}), 404
    
    status = job_status[job_id]
    
    if status['status'] != 'completed':
        return jsonify({'error': 'Job not completed yet'}), 400
    
    output_file = status.get('output_file')
    
    if not output_file or not Path(output_file).exists():
        return jsonify({'error': 'Output file not found'}), 404
    
    # Convert CSV to Excel
    excel_file = output_file.replace('.csv', '.xlsx')
    
    try:
        df = pd.read_csv(output_file)
        df.to_excel(excel_file, index=False, engine='openpyxl')
        
        return send_file(
            excel_file,
            as_attachment=True,
            download_name=f'job_leads_{job_id}.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def run_scrape_job(job_id, job_role, location, job_board, max_companies, enrich):
    """Run scraping job in background."""
    try:
        # Update status
        job_status[job_id]['message'] = f'Scraping {job_board} for {job_role} jobs...'
        job_status[job_id]['progress'] = 10
        
        # Initialize scraper - Use JobSpy for better reliability
        scraper_config = {
            'target_roles': [job_role],
            'location': location,
            'max_companies': max_companies,
            'results_wanted': 100,  # JobSpy parameter (number of results)
            'hours_old': None,  # Get all jobs (can filter by hours if needed)
        }
        
        print(f"DEBUG: Using JobSpy scraper with config: {scraper_config}")
        
        # JobSpy supported sites
        jobspy_sites = ['indeed', 'linkedin', 'glassdoor', 'zip_recruiter', 'google', 'bayt', 'naukri', 'bdjobs']
        
        if job_board.lower() in jobspy_sites:
            try:
                scraper_config['site_name'] = [job_board.lower()]
                scraper = JobSpyScraper(config=scraper_config)
            except ImportError:
                # Fallback to old scraper if JobSpy not installed
                print("WARNING: JobSpy not available, using legacy scraper")
                scraper_config['max_pages_per_role'] = 10
                scraper_config['headless'] = True
                scraper = IndeedSeleniumScraper(config=scraper_config)
        else:
            job_status[job_id]['status'] = 'error'
            job_status[job_id]['message'] = f'Unsupported job board: {job_board}. Supported: {", ".join(jobspy_sites)}'
            return
        
        # Scrape jobs
        job_status[job_id]['progress'] = 20
        raw_jobs = scraper.scrape_all_roles()
        
        job_status[job_id]['message'] = f'Found {len(raw_jobs)} jobs from {len(set(j["company_name"] for j in raw_jobs))} companies'
        job_status[job_id]['progress'] = 50
        
        # Process data
        job_status[job_id]['message'] = 'Processing and cleaning data...'
        processor = DataProcessor(config.processing)
        processed_jobs = processor.process(raw_jobs)
        
        job_status[job_id]['progress'] = 60
        
        # Enrich if requested - handle different enrichment strategies per job board
        if enrich:
            try:
                job_status[job_id]['message'] = 'Enriching company data...'
                job_status[job_id]['progress'] = 70
                
                # Use different enrichment strategies based on job board
                if job_board.lower() == 'linkedin':
                    # Use LinkedIn company page enrichment (with fallback)
                    print("DEBUG: Using LinkedIn company page enrichment...")
                    
                    try:
                        # Import here to avoid circular imports
                        from src.enrichment.linkedin_company_enricher import LinkedInCompanyEnricher
                        
                        # Try enrichment with timeout handling
                        with LinkedInCompanyEnricher(headless=True) as enricher:
                            enrichment_map = enricher.enrich_companies_from_jobs(processed_jobs[:min(len(processed_jobs), 30)])  # Reduced limit
                        
                        print(f"DEBUG: Enriched {len(enrichment_map)} companies from LinkedIn pages")
                        
                        # Merge enrichment data into jobs
                        enriched_count = 0
                        timeout_count = 0
                        blocked_count = 0
                        
                        for job in processed_jobs:
                            company_name = job.get('company_name')
                            if company_name and company_name in enrichment_map:
                                enrichment = enrichment_map[company_name]
                                status = enrichment.get('status', 'UNKNOWN')
                                
                                # Only override if we found better data
                                if enrichment.get('company_size') not in ['Unknown', 'Not available (timeout)', 'Not available (login required)']:
                                    job['company_size'] = enrichment.get('company_size', 'Unknown')
                                if enrichment.get('revenue_range') != 'Unknown':
                                    job['company_revenue_range'] = enrichment.get('revenue_range', 'Unknown')
                                if enrichment.get('headquarters') != 'Unknown':
                                    job['headquarters'] = enrichment.get('headquarters', 'Unknown')
                                if enrichment.get('industry') != 'Unknown':
                                    job['industry'] = enrichment.get('industry', 'Unknown')
                                if enrichment.get('founded_year') != 'Unknown':
                                    job['founded_year'] = enrichment.get('founded_year', 'Unknown')
                                
                                # Count different statuses
                                if status == 'SUCCESS':
                                    enriched_count += 1
                                elif status == 'TIMEOUT':
                                    timeout_count += 1
                                elif status == 'BLOCKED':
                                    blocked_count += 1
                        
                        print(f"DEBUG: LinkedIn enrichment results - Success: {enriched_count}, Timeouts: {timeout_count}, Blocked: {blocked_count}")
                        
                        # If most companies failed, log warning but continue
                        total_attempted = len(enrichment_map)
                        if total_attempted > 0:
                            success_rate = enriched_count / total_attempted
                            if success_rate < 0.3:  # Less than 30% success
                                print(f"WARNING: Low LinkedIn enrichment success rate ({success_rate:.1%}) - LinkedIn may be blocking requests")
                    
                    except Exception as e:
                        print(f"WARNING: LinkedIn enrichment failed completely: {e}")
                        print("DEBUG: Continuing with basic LinkedIn data (industry, headquarters from job listings)")
                        # Don't fail the entire process - continue with basic data
                    
                elif job_board.lower() == 'indeed':
                    # Use Indeed company page enrichment (existing)
                    print("DEBUG: Using Indeed company page enrichment...")
                    
                    from src.enrichment.indeed_company_enricher import IndeedCompanyEnricher
                    
                    with IndeedCompanyEnricher(headless=True) as enricher:
                        enrichment_map = enricher.enrich_companies_from_jobs(processed_jobs[:min(len(processed_jobs), 50)])
                    
                    print(f"DEBUG: Enriched {len(enrichment_map)} companies from Indeed pages")
                    
                    # Merge enrichment data into jobs
                    enriched_count = 0
                    for job in processed_jobs:
                        company_name = job.get('company_name')
                        if company_name and company_name in enrichment_map:
                            enrichment = enrichment_map[company_name]
                            job['company_size'] = enrichment.get('company_size', 'Unknown')
                            job['revenue_range'] = enrichment.get('revenue_range', 'Unknown')
                            job['headquarters'] = enrichment.get('headquarters', 'Unknown')
                            job['industry'] = enrichment.get('industry', 'Unknown')
                            job['founded_year'] = enrichment.get('founded_year', 'Unknown')
                            enriched_count += 1
                    
                    print(f"DEBUG: Applied Indeed enrichment to {enriched_count}/{len(processed_jobs)} companies")
                    
                else:
                    # For other boards, use the data already included from JobSpy
                    print("DEBUG: Using built-in JobSpy company data...")
                
                job_status[job_id]['progress'] = 80
                
            except Exception as e:
                self.logger.error(f"Error during enrichment: {e}")
                print(f"ERROR: Enrichment failed - {e}")
                # Continue without enrichment rather than failing completely
                pass
        else:
            # Add Unknown fields if enrichment not requested
            for job in processed_jobs:
                job['company_size'] = 'Not enriched'
                job['revenue_range'] = 'Not enriched'
                job['headquarters'] = 'Not enriched'
                job['industry'] = 'Not enriched'
                job['founded_year'] = 'Not enriched'
        
        # Export to CSV
        job_status[job_id]['message'] = 'Exporting results...'
        exporter = CSVExporter(config.output)
        output_file = exporter.export(processed_jobs, 'data/output')
        
        # Update status
        job_status[job_id]['status'] = 'completed'
        job_status[job_id]['progress'] = 100
        job_status[job_id]['message'] = f'Completed! Found {len(processed_jobs)} jobs from {len(set(j["company_name"] for j in processed_jobs))} companies'
        job_status[job_id]['output_file'] = output_file
        job_status[job_id]['total_jobs'] = len(processed_jobs)
        job_status[job_id]['unique_companies'] = len(set(j['company_name'] for j in processed_jobs))
        
    except Exception as e:
        job_status[job_id]['status'] = 'error'
        job_status[job_id]['message'] = f'Error: {str(e)}'
        job_status[job_id]['progress'] = 0


if __name__ == '__main__':
    # Create templates directory if not exists
    Path('templates').mkdir(exist_ok=True)
    Path('static').mkdir(exist_ok=True)
    
    print("=" * 60)
    print("Job Scraper Web App")
    print("=" * 60)
    print()
    print("Starting server at http://localhost:5000")
    print("Press Ctrl+C to stop")
    print()
    
    import os
    
    # Load production configuration for Railway deployment
    try:
        from config_production import ProductionConfig
        config = ProductionConfig()
        port = config.PORT
        host = config.HOST
        debug = config.DEBUG
        
        print(f"Production configuration loaded")
        print(f"Host: {host}")
        print(f"Port: {port}")
        print(f"Debug: {debug}")
        
    except ImportError:
        # Fallback to basic configuration
        port = int(os.environ.get("PORT", 5000))
        host = '0.0.0.0'
        debug = False
        print(f"Using fallback configuration")
        print(f"Host: {host}")
        print(f"Port: {port}")
    
    print("=" * 60)
    print("Job Scraper Web App - Railway Deployment")
    print("=" * 60)
    print()
    print(f"Starting server at http://{host}:{port}")
    print("Press Ctrl+C to stop")
    print()
    
    app.run(debug=debug, host=host, port=port)
