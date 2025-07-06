"""
Database management for storing user preferences and concert data
"""
import aiosqlite
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def initialize(self):
        """Initialize the database with required tables"""
        async with aiosqlite.connect(self.db_path) as db:
            # Users table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Favorite bands table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS favorite_bands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    band_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    UNIQUE(user_id, band_name)
                )
            ''')
            
            # Concert notifications table (to avoid duplicate notifications)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS concert_notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    concert_id TEXT,
                    notified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    UNIQUE(user_id, concert_id)
                )
            ''')
            
            await db.commit()
            logger.info("Database initialized successfully")
    
    async def add_user(self, user_id: int, username: str):
        """Add a new user to the database"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    'INSERT OR REPLACE INTO users (id, username) VALUES (?, ?)',
                    (user_id, username)
                )
                await db.commit()
                logger.info(f"User {user_id} ({username}) added to database")
        except Exception as e:
            logger.error(f"Error adding user {user_id}: {e}")
    
    async def add_favorite_band(self, user_id: int, band_name: str) -> bool:
        """Add a favorite band for a user"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    'INSERT INTO favorite_bands (user_id, band_name) VALUES (?, ?)',
                    (user_id, band_name)
                )
                await db.commit()
                logger.info(f"Added favorite band '{band_name}' for user {user_id}")
                return True
        except aiosqlite.IntegrityError:
            logger.info(f"Band '{band_name}' already in favorites for user {user_id}")
            return False
        except Exception as e:
            logger.error(f"Error adding favorite band for user {user_id}: {e}")
            return False
    
    async def remove_favorite_band(self, user_id: int, band_name: str) -> bool:
        """Remove a favorite band for a user"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    'DELETE FROM favorite_bands WHERE user_id = ? AND band_name = ?',
                    (user_id, band_name)
                )
                await db.commit()
                
                if cursor.rowcount > 0:
                    logger.info(f"Removed favorite band '{band_name}' for user {user_id}")
                    return True
                else:
                    return False
        except Exception as e:
            logger.error(f"Error removing favorite band for user {user_id}: {e}")
            return False
    
    async def get_user_favorites(self, user_id: int) -> List[str]:
        """Get all favorite bands for a user"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    'SELECT band_name FROM favorite_bands WHERE user_id = ? ORDER BY band_name',
                    (user_id,)
                )
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"Error getting favorites for user {user_id}: {e}")
            return []
    
    async def get_all_users(self) -> List[int]:
        """Get all user IDs"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute('SELECT id FROM users')
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return []
    
    async def has_notified_concert(self, user_id: int, concert_id: str) -> bool:
        """Check if user has been notified about a specific concert"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    'SELECT 1 FROM concert_notifications WHERE user_id = ? AND concert_id = ?',
                    (user_id, concert_id)
                )
                result = await cursor.fetchone()
                return result is not None
        except Exception as e:
            logger.error(f"Error checking notification status: {e}")
            return False
    
    async def mark_concert_notified(self, user_id: int, concert_id: str):
        """Mark a concert as notified for a user"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    'INSERT OR IGNORE INTO concert_notifications (user_id, concert_id) VALUES (?, ?)',
                    (user_id, concert_id)
                )
                await db.commit()
        except Exception as e:
            logger.error(f"Error marking concert as notified: {e}")
    
    async def cleanup_old_notifications(self, days: int = 30):
        """Clean up old notification records"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    'DELETE FROM concert_notifications WHERE notified_at < datetime("now", "-{} days")'.format(days)
                )
                await db.commit()
                logger.info(f"Cleaned up notifications older than {days} days")
        except Exception as e:
            logger.error(f"Error cleaning up old notifications: {e}")
