#!/usr/bin/env python3
"""
Main entry point for the Italian Concert Telegram Bot
"""
import asyncio
import logging
from bot import ConceertBot
from scheduler import ConcertScheduler
from config import Config
import signal
import sys

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class BotApplication:
    def __init__(self):
        self.config = Config()
        self.bot = ConceertBot(self.config)
        self.scheduler = ConcertScheduler(self.config)
        self.running = False
    
    async def start(self):
        """Start the bot and scheduler"""
        logger.info("Starting Italian Concert Bot...")
        
        try:
            # Initialize database
            await self.bot.initialize_database()
            
            # Start the scheduler in background
            self.scheduler.start()
            logger.info("Concert monitoring scheduler started")
            
            # Start the bot
            await self.bot.start()
            self.running = True
            logger.info("Bot started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            await self.shutdown()
            sys.exit(1)
    
    async def shutdown(self):
        """Graceful shutdown"""
        if self.running:
            logger.info("Shutting down bot...")
            self.scheduler.stop()
            await self.bot.stop()
            self.running = False
            logger.info("Bot shutdown complete")
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        asyncio.create_task(self.shutdown())

async def main():
    """Main application entry point"""
    app = BotApplication()
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, app.signal_handler)
    signal.signal(signal.SIGTERM, app.signal_handler)
    
    try:
        await app.start()
        
        # Keep the application running
        while app.running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        await app.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
