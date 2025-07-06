#!/usr/bin/env python3
"""Test telegram import"""

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    print("✓ Main telegram imports successful")
except ImportError as e:
    print(f"✗ Main import error: {e}")

try:
    from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
    print("✓ All telegram.ext imports successful")
except ImportError as e:
    print(f"✗ Ext import error: {e}")
    
    # Try alternative import structure
    try:
        import telegram
        print(f"✓ Base telegram module found: {telegram}")
        print(f"Available attributes: {dir(telegram)}")
    except ImportError as e2:
        print(f"✗ Base telegram module not found: {e2}")