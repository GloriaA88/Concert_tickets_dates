# Italian Concert Telegram Bot

## Overview

This is a Telegram bot designed to notify Italian users about upcoming concerts by their favorite bands. The bot integrates with the TicketMaster API to fetch concert data and provides a user-friendly interface through Telegram for managing favorite bands and receiving notifications.

## System Architecture

The application follows a modular architecture with clear separation of concerns:

- **Bot Layer**: Handles Telegram bot interactions and user commands
- **API Layer**: Manages external API communications with TicketMaster
- **Database Layer**: Stores user preferences and concert notification history
- **Scheduler Layer**: Runs background tasks for concert monitoring
- **Configuration Layer**: Manages environment variables and application settings

## Key Components

### Bot (bot.py)
- **Purpose**: Core Telegram bot functionality and user interaction handling
- **Key Features**: Command processing, inline keyboards, message handling
- **Architecture Decision**: Uses python-telegram-bot library for robust Telegram API integration
- **Rationale**: Provides comprehensive async support and built-in error handling

### Database (database.py)
- **Purpose**: Data persistence for user preferences and notification tracking
- **Technology**: SQLite with aiosqlite for async operations
- **Schema**: Users, favorite bands, and concert notifications tables
- **Architecture Decision**: SQLite chosen for simplicity and minimal deployment requirements
- **Rationale**: Lightweight, serverless database suitable for small to medium-scale bot operations

### TicketMaster API (ticketmaster_api.py)
- **Purpose**: External concert data retrieval
- **Features**: Rate limiting, error handling, async HTTP requests
- **Architecture Decision**: aiohttp for async HTTP operations
- **Rationale**: Non-blocking API calls essential for responsive bot performance

### Scheduler (scheduler.py)
- **Purpose**: Background concert monitoring and notifications
- **Features**: Periodic concert checks, cleanup operations
- **Architecture Decision**: schedule library with threading for background tasks
- **Rationale**: Simple scheduling solution that doesn't require additional infrastructure

### Configuration (config.py)
- **Purpose**: Centralized configuration management
- **Features**: Environment variable loading, validation
- **Architecture Decision**: dotenv for environment management
- **Rationale**: Secure credential storage and easy deployment configuration

## Data Flow

1. **User Registration**: Users interact with bot → User data stored in SQLite
2. **Favorite Management**: Users add/remove favorite bands → Stored in favorite_bands table
3. **Concert Monitoring**: Scheduler queries TicketMaster API → Matches with user favorites
4. **Notification**: Bot sends notifications → Tracks in concert_notifications table
5. **Cleanup**: Periodic cleanup of old notification records

## External Dependencies

- **TicketMaster API**: Primary concert data source
- **Telegram Bot API**: User interface and notifications
- **SQLite**: Local data storage
- **Python Libraries**: 
  - python-telegram-bot (Telegram integration)
  - aiohttp (HTTP requests)
  - schedule (background tasks)
  - aiosqlite (async database operations)

## Deployment Strategy

- **Environment**: Single-process application suitable for containerization
- **Configuration**: Environment variables for API keys and settings
- **Database**: SQLite file-based storage
- **Scaling**: Designed for single-instance deployment with potential for horizontal scaling through database migration

## Changelog

- July 06, 2025: Initial setup
- July 06, 2025: Updated bot interface to complete Italian language
- July 06, 2025: Implemented interactive menu system with inline keyboards
- July 06, 2025: Added button-based navigation matching user's design requirements

## User Preferences

Preferred communication style: Simple, everyday language.
Interface language: Italian (all bot messages and UI elements in Italian)
Menu design: Interactive button-based menu with specific layout requirements