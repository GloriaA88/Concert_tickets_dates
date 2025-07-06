"""
Telegram Bot implementation for Italian Concert notifications
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from database import DatabaseManager
from ticketmaster_api import TicketMasterAPI
from concert_sources import MultiSourceConcertFinder
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class ConceertBot:
    def __init__(self, config):
        self.config = config
        self.db = DatabaseManager(config.database_path)
        self.ticketmaster = TicketMasterAPI(config.ticketmaster_api_key)
        self.multi_source = MultiSourceConcertFinder(self.ticketmaster)
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
        self.application.add_handler(CommandHandler("test", self.test_notifications_command))  # Test command
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
        
        # Create main menu keyboard
        keyboard = [
            [InlineKeyboardButton("➕ Aggiungi Gruppo", callback_data="add_band")],
            [InlineKeyboardButton("➖ Rimuovi Gruppo", callback_data="remove_band")],
            [InlineKeyboardButton("📋 Lista Gruppi Preferiti", callback_data="list_favorites")],
            [InlineKeyboardButton("ℹ️ Aiuto", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_message = (
            "🎵 Benvenuto nel Bot Concerti Italia! 🎵\n\n"
            "Ti aiuterò a rimanere aggiornato sui concerti dei tuoi gruppi preferiti in Italia.\n\n"
            "Scegli un'opzione dal menu:"
        )
        
        await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        # Create main menu keyboard
        keyboard = [
            [InlineKeyboardButton("➕ Aggiungi Gruppo", callback_data="add_band")],
            [InlineKeyboardButton("➖ Rimuovi Gruppo", callback_data="remove_band")],
            [InlineKeyboardButton("📋 Lista Gruppi Preferiti", callback_data="list_favorites")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        help_text = (
            "🎵 Bot Concerti Italia - Aiuto\n\n"
            "📝 Gestione Preferiti:\n"
            "• Aggiungi gruppi ai tuoi preferiti\n"
            "• Rimuovi gruppi dalla lista\n"
            "• Visualizza la lista dei tuoi gruppi preferiti\n\n"
            "🔔 Monitoraggio Automatico:\n"
            "• Controllo automatico ogni 4 ore per nuovi concerti\n"
            "• Notifiche immediate quando trovo concerti in Italia\n"
            "• Link diretto per acquistare i biglietti\n"
            "• Monitoraggio continuo senza intervento manuale\n\n"
            "Usa il menu qui sotto per iniziare:"
        )
        
        await update.message.reply_text(help_text, reply_markup=reply_markup)
    
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
    
    async def test_notifications_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Test command to manually trigger concert check"""
        user_id = update.effective_user.id
        
        await update.message.reply_text("🔍 Avvio test di notifiche... Controllando i concerti per i tuoi gruppi preferiti.")
        
        try:
            # Get user's favorites
            favorites = await self.db.get_user_favorites(user_id)
            if not favorites:
                await update.message.reply_text("❌ Non hai gruppi preferiti. Aggiungi alcuni gruppi prima di testare.")
                return
            
            await update.message.reply_text(f"🎵 Cercando concerti per: {', '.join(favorites)}")
            
            # Check concerts for this specific user using multiple sources
            new_concerts = []
            for band in favorites:
                concerts = await self.multi_source.search_all_sources(band, country_code="IT")
                
                # For testing, if no real concerts found, create a sample to show how notifications work
                if not concerts:
                    sample_concert = self.multi_source.create_sample_concert(band)
                    concerts = [sample_concert]
                    await update.message.reply_text(
                        f"⚠️ Nessun concerto reale trovato per '{band}'. "
                        f"Invio esempio di notifica per mostrare come funziona il sistema."
                    )
                
                # For testing, don't check if already notified
                new_concerts.extend(concerts)
            
            if new_concerts:
                # Send notification
                await self.send_concert_notification(user_id, new_concerts)
                await update.message.reply_text(f"✅ Test completato! Trovati {len(new_concerts)} concerti. Notifica inviata.")
            else:
                # Provide more helpful debugging information
                await update.message.reply_text(
                    "😔 Nessun concerto trovato al momento per i tuoi gruppi preferiti in Italia.\n\n"
                    "⚠️ Nota: TicketMaster potrebbe non avere tutti i concerti italiani. "
                    "Il monitoraggio automatico continua ogni 4 ore e controllerà anche altre fonti quando disponibili.\n\n"
                    "💡 Suggerimento: Verifica che il nome del gruppo sia scritto esattamente come appare sui biglietti ufficiali."
                )
                
        except Exception as e:
            logger.error(f"Error in test command: {e}")
            await update.message.reply_text(f"❌ Errore durante il test: {e}")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages (band names)"""
        user_id = update.effective_user.id
        
        # Check if user is in a state where we expect band name input
        if context.user_data.get('expecting_band_name'):
            band_name = update.message.text.strip()
            
            # Clear the state
            context.user_data['expecting_band_name'] = False
            
            # Add the band to favorites
            await self.add_favorite_band(user_id, band_name, update)
        else:
            # Show main menu if user sends any other text
            keyboard = [
                [InlineKeyboardButton("➕ Aggiungi Gruppo", callback_data="add_band")],
                [InlineKeyboardButton("➖ Rimuovi Gruppo", callback_data="remove_band")],
                [InlineKeyboardButton("📋 Lista Gruppi Preferiti", callback_data="list_favorites")],
                [InlineKeyboardButton("ℹ️ Aiuto", callback_data="help")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🎵 Bot Concerti Italia\n\nScegli un'opzione dal menu:",
                reply_markup=reply_markup
            )
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if query.data == "add_band":
            await query.edit_message_text(
                "➕ Aggiungi un nuovo gruppo\n\n"
                "Scrivi il nome del gruppo che vuoi aggiungere ai tuoi preferiti:"
            )
            # Set user state to expect band name input
            context.user_data['expecting_band_name'] = True
            
        elif query.data == "remove_band":
            favorites = await self.db.get_user_favorites(user_id)
            if favorites:
                keyboard = []
                for band in favorites:
                    keyboard.append([InlineKeyboardButton(
                        f"🗑️ {band}", 
                        callback_data=f"remove_{band}"
                    )])
                keyboard.append([InlineKeyboardButton("🔙 Menu Principale", callback_data="main_menu")])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    "➖ Seleziona un gruppo da rimuovere:",
                    reply_markup=reply_markup
                )
            else:
                keyboard = [[InlineKeyboardButton("🔙 Menu Principale", callback_data="main_menu")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    "❌ Non hai ancora gruppi preferiti.\nUsa 'Aggiungi Gruppo' per aggiungerne uno!",
                    reply_markup=reply_markup
                )
        
        elif query.data == "list_favorites":
            favorites = await self.db.get_user_favorites(user_id)
            if favorites:
                favorites_text = "📋 I tuoi gruppi preferiti:\n\n"
                for i, band in enumerate(favorites, 1):
                    favorites_text += f"{i}. 🎵 {band}\n"
            else:
                favorites_text = "❌ Non hai ancora gruppi preferiti.\nUsa 'Aggiungi Gruppo' per aggiungerne uno!"
            
            keyboard = [[InlineKeyboardButton("🔙 Menu Principale", callback_data="main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(favorites_text, reply_markup=reply_markup)
        

        elif query.data == "help":
            await self.help_command(update, context)
        
        elif query.data == "main_menu":
            # Show main menu
            keyboard = [
                [InlineKeyboardButton("➕ Aggiungi Gruppo", callback_data="add_band")],
                [InlineKeyboardButton("➖ Rimuovi Gruppo", callback_data="remove_band")],
                [InlineKeyboardButton("📋 Lista Gruppi Preferiti", callback_data="list_favorites")],
                [InlineKeyboardButton("ℹ️ Aiuto", callback_data="help")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "🎵 Bot Concerti Italia\n\nScegli un'opzione dal menu:",
                reply_markup=reply_markup
            )
        
        elif query.data.startswith("remove_"):
            band_name = query.data[7:]  # Remove "remove_" prefix
            
            success = await self.db.remove_favorite_band(user_id, band_name)
            keyboard = [[InlineKeyboardButton("🔙 Menu Principale", callback_data="main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if success:
                await query.edit_message_text(
                    f"✅ '{band_name}' rimosso dai tuoi preferiti!",
                    reply_markup=reply_markup
                )
            else:
                await query.edit_message_text(
                    f"❌ Errore nel rimuovere '{band_name}'.",
                    reply_markup=reply_markup
                )
    
    async def add_favorite_band(self, user_id: int, band_name: str, update: Update):
        """Add a band to user's favorites"""
        # Create main menu keyboard for response
        keyboard = [[InlineKeyboardButton("🔙 Menu Principale", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Add the band directly to favorites without pre-verification
        # The automatic monitoring will check if concerts exist
        success = await self.db.add_favorite_band(user_id, band_name)
        
        if success:
            await update.message.reply_text(
                f"✅ '{band_name}' aggiunto ai tuoi preferiti!\n\n"
                f"🔔 Ti invierò automaticamente notifiche quando troverò concerti di questo gruppo in Italia.",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                f"'{band_name}' è già nei tuoi preferiti.",
                reply_markup=reply_markup
            )
    
    def format_concert_message(self, concert: dict) -> str:
        """Format a concert into a readable message"""
        name = concert.get('name', 'Evento Sconosciuto')
        date = concert.get('date', 'Da Definire')
        venue = concert.get('venue', 'Venue Sconosciuto')
        city = concert.get('city', 'Città Sconosciuta')
        url = concert.get('url', '')
        source = concert.get('source', 'Unknown')
        is_verified = concert.get('verified', True)
        note = concert.get('note', '')
        
        message = f"🎵 <b>{name}</b>\n"
        message += f"📅 {date}\n"
        message += f"📍 {venue}, {city}\n"
        
        if url and is_verified:
            message += f"🎫 <a href='{url}'>Acquista Biglietti</a>\n"
        elif not is_verified:
            message += f"💡 {note}\n"
        
        if not is_verified:
            message += f"🔍 Fonte: {source}\n"
        
        return message
    
    async def send_concert_notification(self, user_id: int, concerts: list):
        """Send concert notifications to a user"""
        if not concerts:
            return
        
        message = "🎵 Nuovi concerti trovati per i tuoi gruppi preferiti!\n\n"
        
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
                    concerts = await self.multi_source.search_all_sources(band, country_code="IT")
                    
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
