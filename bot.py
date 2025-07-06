"""
Telegram Bot implementation for Italian Concert notifications
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from database import DatabaseManager
from ticketmaster_api import TicketMasterAPI
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class ConceertBot:
    def __init__(self, config):
        self.config = config
        self.db = DatabaseManager(config.database_path)
        self.ticketmaster = TicketMasterAPI(config.ticketmaster_api_key)
        self.application = None
        
    async def initialize_database(self):
        """Initialize the database"""
        await self.db.initialize()
        
    async def start(self):
        """Start the Telegram bot"""
        self.application = Application.builder().token(self.config.telegram_token).build()
        
        # Add command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("addfavorite", self.add_favorite_command))
        self.application.add_handler(CommandHandler("removefavorite", self.remove_favorite_command))
        self.application.add_handler(CommandHandler("listfavorites", self.list_favorites_command))
        self.application.add_handler(CommandHandler("findconcerts", self.find_concerts_command))
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Add message handler for band names
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Start the bot
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        
    async def stop(self):
        """Stop the bot"""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name
        
        # Register user in database
        await self.db.add_user(user_id, username)
        
        welcome_message = (
            "🎵 Welcome to the Italian Concert Bot! 🎵\n\n"
            "I'll help you stay updated on concerts by your favorite bands in Italy.\n\n"
            "Use /help to see all available commands."
        )
        
        await update.message.reply_text(welcome_message)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = (
            "🎵 Italian Concert Bot Commands:\n\n"
            "📝 Managing Favorites:\n"
            "/addfavorite - Add a band to your favorites\n"
            "/removefavorite - Remove a band from favorites\n"
            "/listfavorites - Show your favorite bands\n\n"
            "🔍 Finding Concerts:\n"
            "/findconcerts - Search for concerts by your favorite bands\n\n"
            "ℹ️ Other:\n"
            "/help - Show this help message\n\n"
            "💡 Tip: I automatically check for new concerts and notify you when I find them!"
        )
        
        await update.message.reply_text(help_text)
    
    async def add_favorite_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /addfavorite command"""
        user_id = update.effective_user.id
        
        if context.args:
            band_name = ' '.join(context.args)
            await self.add_favorite_band(user_id, band_name, update)
        else:
            await update.message.reply_text(
                "Please provide a band name. Example: /addfavorite Coldplay"
            )
    
    async def remove_favorite_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /removefavorite command"""
        user_id = update.effective_user.id
        
        if context.args:
            band_name = ' '.join(context.args)
            success = await self.db.remove_favorite_band(user_id, band_name)
            
            if success:
                await update.message.reply_text(f"✅ Removed '{band_name}' from your favorites!")
            else:
                await update.message.reply_text(f"❌ '{band_name}' was not in your favorites.")
        else:
            # Show list of favorites to remove
            favorites = await self.db.get_user_favorites(user_id)
            if favorites:
                keyboard = []
                for band in favorites:
                    keyboard.append([InlineKeyboardButton(
                        f"Remove {band}", 
                        callback_data=f"remove_{band}"
                    )])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    "Select a band to remove from your favorites:",
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text("You don't have any favorite bands yet.")
    
    async def list_favorites_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /listfavorites command"""
        user_id = update.effective_user.id
        favorites = await self.db.get_user_favorites(user_id)
        
        if favorites:
            favorites_text = "🎵 Your favorite bands:\n\n"
            for i, band in enumerate(favorites, 1):
                favorites_text += f"{i}. {band}\n"
        else:
            favorites_text = "You don't have any favorite bands yet.\nUse /addfavorite to add some!"
        
        await update.message.reply_text(favorites_text)
    
    async def find_concerts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /findconcerts command"""
        user_id = update.effective_user.id
        favorites = await self.db.get_user_favorites(user_id)
        
        if not favorites:
            await update.message.reply_text(
                "You don't have any favorite bands yet.\nUse /addfavorite to add some!"
            )
            return
        
        await update.message.reply_text("🔍 Searching for concerts... Please wait.")
        
        all_concerts = []
        for band in favorites:
            concerts = await self.ticketmaster.search_concerts(band, country_code="IT")
            all_concerts.extend(concerts)
        
        if all_concerts:
            message = "🎵 Found concerts for your favorite bands:\n\n"
            for concert in all_concerts[:10]:  # Limit to 10 concerts
                message += self.format_concert_message(concert) + "\n"
        else:
            message = "😔 No upcoming concerts found for your favorite bands in Italy."
        
        await update.message.reply_text(message, parse_mode='HTML', disable_web_page_preview=True)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages (band names)"""
        # This could be used for adding favorites via text input
        pass
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("remove_"):
            band_name = query.data[7:]  # Remove "remove_" prefix
            user_id = query.from_user.id
            
            success = await self.db.remove_favorite_band(user_id, band_name)
            if success:
                await query.edit_message_text(f"✅ Removed '{band_name}' from your favorites!")
            else:
                await query.edit_message_text(f"❌ Failed to remove '{band_name}'.")
    
    async def add_favorite_band(self, user_id: int, band_name: str, update: Update):
        """Add a band to user's favorites"""
        # First, verify the band exists in TicketMaster
        concerts = await self.ticketmaster.search_concerts(band_name, limit=1)
        
        if not concerts:
            await update.message.reply_text(
                f"⚠️ Could not find '{band_name}' in TicketMaster. "
                f"Please check the spelling and try again."
            )
            return
        
        success = await self.db.add_favorite_band(user_id, band_name)
        
        if success:
            await update.message.reply_text(f"✅ Added '{band_name}' to your favorites!")
        else:
            await update.message.reply_text(f"'{band_name}' is already in your favorites.")
    
    def format_concert_message(self, concert: dict) -> str:
        """Format a concert into a readable message"""
        name = concert.get('name', 'Unknown Event')
        date = concert.get('date', 'TBD')
        venue = concert.get('venue', 'Unknown Venue')
        city = concert.get('city', 'Unknown City')
        url = concert.get('url', '')
        
        message = f"🎵 <b>{name}</b>\n"
        message += f"📅 {date}\n"
        message += f"📍 {venue}, {city}\n"
        
        if url:
            message += f"🎫 <a href='{url}'>Buy Tickets</a>\n"
        
        return message
    
    async def send_concert_notification(self, user_id: int, concerts: list):
        """Send concert notifications to a user"""
        if not concerts:
            return
        
        message = "🎵 New concerts found for your favorite bands!\n\n"
        
        for concert in concerts:
            message += self.format_concert_message(concert) + "\n"
        
        try:
            await self.application.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Failed to send notification to user {user_id}: {e}")
    
    async def check_concerts_for_all_users(self):
        """Check for new concerts for all users"""
        users = await self.db.get_all_users()
        
        for user_id in users:
            try:
                favorites = await self.db.get_user_favorites(user_id)
                if not favorites:
                    continue
                
                new_concerts = []
                for band in favorites:
                    concerts = await self.ticketmaster.search_concerts(band, country_code="IT")
                    
                    # Filter out concerts we've already notified about
                    for concert in concerts:
                        concert_id = concert.get('id')
                        if concert_id and not await self.db.has_notified_concert(user_id, concert_id):
                            new_concerts.append(concert)
                            await self.db.mark_concert_notified(user_id, concert_id)
                
                if new_concerts:
                    await self.send_concert_notification(user_id, new_concerts)
                    
            except Exception as e:
                logger.error(f"Error checking concerts for user {user_id}: {e}")
            
            # Rate limiting - small delay between users
            await asyncio.sleep(1)
