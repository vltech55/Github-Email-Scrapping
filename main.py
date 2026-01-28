#!/usr/bin/env python3
"""
Main Control File - Automation Pipeline
Starts and manages all workers: scraper -> queue1 -> database -> queue2 -> actions
"""

import sys
import time
import threading
import signal
import argparse
from typing import List, Dict, Any
from dotenv import load_dotenv

from scraper_worker import ScraperWorker
from database_worker import DatabaseWorker
from actions_worker import ActionsWorker

# Load environment variables from .env file
load_dotenv()

import logging
# Set root logger to WARNING to reduce noise
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s [%(name)s] %(message)s',
    datefmt='%H:%M:%S'
)
# Only show MAIN logs
logger = logging.getLogger('MAIN')
logger.setLevel(logging.INFO)


class PipelineController:
    """Main controller for the automation pipeline."""
    
    def __init__(self, search_configs: List[Dict[str, Any]] = None):
        """
        Initialize pipeline controller.
        
        Args:
            search_configs: List of GitHub search configurations
        """
        self.search_configs = search_configs or self.get_default_search_configs()
        
        # Initialize workers
        self.scraper = None
        self.database = None
        self.actions = None
        
        # Thread management
        self.workers = []
        self.running = False
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    @staticmethod
    def get_default_search_configs() -> List[Dict[str, Any]]:
        """Get default GitHub search configurations."""
        # Try to load from search_config.json first
        try:
            import json
            import os
            if os.path.exists('search_config.json'):
                with open('search_config.json', 'r') as f:
                    data = json.load(f)
                    if 'search_configurations' in data:
                        return data['search_configurations']
        except:
            pass
        
        # Fall back to hardcoded defaults
        return [
            {
                'location': 'San Francisco',
                'language': 'python',
                'min_followers': 15,
                'max_results': 50
            },
            {
                'location': 'New York',
                'language': 'javascript',
                'min_followers': 15,
                'max_results': 50
            },
            {
                'location': 'Seattle',
                'language': 'typescript',
                'min_followers': 10,
                'max_results': 50
            }
        ]
    
    def start_all(self, continuous: bool = True, single_config_mode: bool = False):
        """
        Start all workers in the pipeline.
        
        Args:
            continuous: If True, scraper runs continuously; otherwise, runs once
            single_config_mode: If True, use only first config and paginate through all pages
        """
        logger.info("="*70)
        logger.info("STARTING AUTOMATION PIPELINE")
        logger.info("="*70)
        logger.info("Architecture: scraper -> queue1 -> database -> queue2 -> actions")
        logger.info(f"Search configs: {len(self.search_configs)}")
        logger.info(f"Continuous mode: {continuous}")
        logger.info(f"Single config mode: {single_config_mode}")
        if single_config_mode:
            logger.info(">>> Will use ONLY first config and paginate through ALL pages <<<")
        logger.info("="*70)
        
        self.running = True
        self._single_config_mode = single_config_mode  # Save for potential restarts
        
        # Initialize workers
        logger.info("\n[INIT] Initializing workers...")
        self.scraper = ScraperWorker()
        self.database = DatabaseWorker()
        self.actions = ActionsWorker()
        logger.info("[INIT] All workers initialized")
        
        # Start workers in order
        logger.info("\n[START] Starting workers...")
        
        # 1. Database worker (processes queue1)
        logger.info("[START] Starting database worker...")
        db_thread = threading.Thread(
            target=self.database.run,
            name="DatabaseWorker",
            daemon=True
        )
        db_thread.start()
        self.workers.append(('database', db_thread))
        time.sleep(2)
        
        # 2. Actions worker (processes queue2)
        logger.info("[START] Starting actions worker...")
        actions_thread = threading.Thread(
            target=self.actions.run,
            name="ActionsWorker",
            daemon=True
        )
        actions_thread.start()
        self.workers.append(('actions', actions_thread))
        time.sleep(2)
        
        # 3. Scraper worker (feeds queue1)
        logger.info("[START] Starting scraper worker...")
        scraper_thread = threading.Thread(
            target=lambda: self.scraper.run(self.search_configs, continuous=continuous, single_config_mode=single_config_mode),
            name="ScraperWorker",
            daemon=True
        )
        scraper_thread.start()
        self.workers.append(('scraper', scraper_thread))
        time.sleep(1)
        
        logger.info("\n[SUCCESS] All workers started!")
        logger.info("Press Ctrl+C to stop the pipeline\n")
        
        # Monitor pipeline
        self._monitor_pipeline()
    
    def start_worker(self, worker_name: str):
        """
        Start a single worker.
        
        Args:
            worker_name: Name of worker ('scraper', 'database', or 'actions')
        """
        logger.info(f"Starting {worker_name} worker only...")
        
        self.running = True
        
        if worker_name == 'scraper':
            self.scraper = ScraperWorker()
            self.scraper.run(self.search_configs, continuous=True)
            
        elif worker_name == 'database':
            self.database = DatabaseWorker()
            self.database.run()
            
        elif worker_name == 'actions':
            self.actions = ActionsWorker()
            self.actions.run()
            
        else:
            logger.error(f"Unknown worker: {worker_name}")
            logger.info("Available workers: scraper, database, actions")
    
    def _monitor_pipeline(self):
        """Monitor pipeline status and display statistics."""
        
        try:
            status_interval = 30  # seconds
            last_status_time = time.time()
            dead_worker_count = {}  # Track how many times each worker died
            
            while self.running:
                time.sleep(5)
                
                # Check if any worker died and attempt restart
                for i, (name, thread) in enumerate(self.workers):
                    if not thread.is_alive():
                        logger.error(f"[ALERT] {name} worker died!")
                        
                        # Track death count
                        if name not in dead_worker_count:
                            dead_worker_count[name] = 0
                        dead_worker_count[name] += 1
                        
                        # Only restart if not died too many times (prevent infinite restart loop)
                        if dead_worker_count[name] <= 3:
                            logger.info(f"[RESTART] Attempting to restart {name} worker (attempt {dead_worker_count[name]}/3)")
                            
                            try:
                                # Restart the specific worker
                                if name == 'scraper':
                                    logger.info("[RESTART] Restarting scraper worker...")
                                    # Get search configs
                                    search_configs = self.search_configs or self.get_default_search_configs()
                                    # Check if single_config_mode from original start
                                    single_config_mode = getattr(self, '_single_config_mode', False)
                                    continuous = True
                                    
                                    new_thread = threading.Thread(
                                        target=lambda: self.scraper.run(search_configs, continuous=continuous, single_config_mode=single_config_mode),
                                        name="ScraperWorker",
                                        daemon=True
                                    )
                                    new_thread.start()
                                    self.workers[i] = (name, new_thread)
                                    logger.info(f"[RESTART] {name} worker restarted successfully")
                                    
                                elif name == 'database':
                                    logger.info("[RESTART] Restarting database worker...")
                                    new_thread = threading.Thread(
                                        target=self.database.run,
                                        name="DatabaseWorker",
                                        daemon=True
                                    )
                                    new_thread.start()
                                    self.workers[i] = (name, new_thread)
                                    logger.info(f"[RESTART] {name} worker restarted successfully")
                                    
                                elif name == 'actions':
                                    logger.info("[RESTART] Restarting actions worker...")
                                    new_thread = threading.Thread(
                                        target=self.actions.run,
                                        name="ActionsWorker",
                                        daemon=True
                                    )
                                    new_thread.start()
                                    self.workers[i] = (name, new_thread)
                                    logger.info(f"[RESTART] {name} worker restarted successfully")
                                    
                            except Exception as e:
                                logger.error(f"[RESTART] Failed to restart {name}: {e}")
                                import traceback
                                traceback.print_exc()
                        else:
                            logger.error(f"[CRITICAL] {name} worker died {dead_worker_count[name]} times - NOT restarting (possible systemic issue)")
                
                # Print status periodically
                current_time = time.time()
                if current_time - last_status_time >= status_interval:
                    self._print_status()
                    last_status_time = current_time
                    
        except KeyboardInterrupt:
            logger.info("\n[SHUTDOWN] Received interrupt signal")
            self.stop()
    
    def _print_status(self):
        """Print current pipeline status."""
        
        logger.info("\n" + "="*70)
        logger.info("PIPELINE STATUS")
        logger.info("="*70)
        
        try:
            # Queue lengths
            if self.scraper:
                q1 = self.scraper.queue.get_queue_length('queue1')
                q2 = self.scraper.queue.get_queue_length('queue2')
                logger.info(f"Queues: queue1={q1}, queue2={q2}")
            
            # Database stats
            if self.database:
                db_stats = self.database.get_stats()
                logger.info(f"Database: Users={db_stats['users']}, "
                          f"Emails={db_stats['emails']}, "
                          f"Pending={db_stats['pending_actions']}, "
                          f"Completed={db_stats['completed_actions']}")
            
            # Action stats
            if self.actions:
                action_stats = self.actions.get_stats()
                logger.info(f"Actions: {action_stats['by_status']}")
            
            # Worker status
            logger.info(f"Workers alive: {sum(1 for _, t in self.workers if t.is_alive())}/{len(self.workers)}")
            
        except Exception as e:
            logger.error(f"Error getting status: {e}")
        
        logger.info("="*70 + "\n")
    
    def stop(self):
        """Stop all workers gracefully."""
        
        logger.info("\n[SHUTDOWN] Stopping pipeline...")
        self.running = False
        
        # Stop all workers
        if self.scraper:
            self.scraper.stop()
        if self.database:
            self.database.stop()
        if self.actions:
            self.actions.stop()
        
        # Wait for threads to finish
        logger.info("[SHUTDOWN] Waiting for workers to finish...")
        for name, thread in self.workers:
            thread.join(timeout=5)
            if thread.is_alive():
                logger.warning(f"[SHUTDOWN] {name} worker did not stop cleanly")
            else:
                logger.info(f"[SHUTDOWN] {name} worker stopped")
        
        # Print final status
        logger.info("\n[SHUTDOWN] Final status:")
        self._print_status()
        
        logger.info("[SHUTDOWN] Pipeline stopped successfully")
    
    def _signal_handler(self, signum, frame):
        """Handle interrupt signals."""
        logger.info(f"\n[SIGNAL] Received signal {signum}")
        self.stop()
        sys.exit(0)


def main():
    """Main entry point with CLI argument parsing."""
    
    parser = argparse.ArgumentParser(
        description='Automation Pipeline Controller',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                             # Start all workers in continuous mode
  python main.py --once                      # Run scraper once then stop
  python main.py --single-config             # Use only first config, paginate through ALL pages
  python main.py --worker scraper            # Start only scraper worker
  python main.py --worker database           # Start only database worker
  python main.py --worker actions            # Start only actions worker
        """
    )
    
    parser.add_argument(
        '--worker',
        choices=['scraper', 'database', 'actions'],
        help='Start only a specific worker'
    )
    
    parser.add_argument(
        '--single-config',
        action='store_true',
        help='Use only the first search config and paginate through all pages (no cycling)'
    )
    
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run scraper once and exit (instead of continuous mode)'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='Path to search configuration JSON file'
    )
    
    args = parser.parse_args()
    
    # Load search configs
    search_configs = None
    if args.config:
        try:
            import json
            with open(args.config, 'r') as f:
                search_configs = json.load(f)
            logger.info(f"Loaded search configs from {args.config}")
        except Exception as e:
            logger.error(f"Failed to load config file: {e}")
            sys.exit(1)
    
    # Create controller
    controller = PipelineController(search_configs=search_configs)
    
    try:
        if args.worker:
            # Start single worker
            controller.start_worker(args.worker)
        else:
            # Start all workers
            continuous = not args.once
            single_config_mode = args.single_config
            controller.start_all(continuous=continuous, single_config_mode=single_config_mode)
            
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        controller.stop()
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        import traceback
        traceback.print_exc()
        controller.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()
