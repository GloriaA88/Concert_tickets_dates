"""
Background scheduler for monitoring concerts
"""
import asyncio
import logging
from datetime import datetime, time
import schedule
from threading import Thread
from bot import ConceertBot
from database import DatabaseManager

logger = logging.getLogger(__name__)

class ConcertScheduler:
    def __init__(self, config):
        self.config = config
        self.db = DatabaseManager(config.database_path)
        self.bot = None
        self.running = False
        self.schedule_thread = None
    
    def start(self):
        """Start the scheduler"""
        self.running = True
        
        # Schedule concert checking every 4 hours
        schedule.every(4).hours.do(self._schedule_concert_check)
        
        # Schedule daily cleanup at 3 AM
        schedule.every().day.at("03:00").do(self._schedule_cleanup)
        
        # Schedule immediate check (after 1 minute startup delay)
        schedule.every(1).minutes.do(self._schedule_initial_check)
        
        # Start the scheduler thread
        self.schedule_thread = Thread(target=self._run_scheduler, daemon=True)
        self.schedule_thread.start()
        
        logger.info("Concert scheduler started")
    
    def stop(self):
        """Stop the scheduler"""
        self.running = False
        schedule.clear()
        
        if self.schedule_thread:
            self.schedule_thread.join(timeout=5)
        
        logger.info("Concert scheduler stopped")
    
    def _run_scheduler(self):
        """Run the scheduler in a separate thread"""
        import time
        while self.running:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    def _schedule_concert_check(self):
        """Schedule a concert check"""
        if self.running:
            asyncio.create_task(self._check_concerts())
    
    def _schedule_cleanup(self):
        """Schedule database cleanup"""
        if self.running:
            asyncio.create_task(self._cleanup_database())
    
    def _schedule_initial_check(self):
        """Schedule initial concert check (run once)"""
        if self.running:
            asyncio.create_task(self._check_concerts())
            # Remove this job after first run
            schedule.clear('initial_check')
    
    async def _check_concerts(self):
        """Check for new concerts for all users"""
        logger.info("Starting scheduled concert check...")
        
        try:
            if not self.bot:
                # We need to create a bot instance for API calls
                from bot import ConceertBot
                self.bot = ConceertBot(self.config)
            
            await self.bot.check_concerts_for_all_users()
            logger.info("Scheduled concert check completed")
            
        except Exception as e:
            logger.error(f"Error during scheduled concert check: {e}")
    
    async def _cleanup_database(self):
        """Clean up old database records"""
        logger.info("Starting database cleanup...")
        
        try:
            await self.db.cleanup_old_notifications(days=30)
            logger.info("Database cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during database cleanup: {e}")
    
    def get_next_check_time(self) -> str:
        """Get the next scheduled check time"""
        jobs = schedule.get_jobs()
        if jobs:
            next_run = min(job.next_run for job in jobs if job.next_run)
            return next_run.strftime("%Y-%m-%d %H:%M:%S")
        return "No scheduled jobs"
    
    def get_schedule_status(self) -> dict:
        """Get current schedule status"""
        jobs = schedule.get_jobs()
        return {
            'running': self.running,
            'active_jobs': len(jobs),
            'next_check': self.get_next_check_time(),
            'jobs': [
                {
                    'job': str(job.job_func),
                    'next_run': job.next_run.strftime("%Y-%m-%d %H:%M:%S") if job.next_run else None,
                    'interval': str(job.interval)
                }
                for job in jobs
            ]
        }
