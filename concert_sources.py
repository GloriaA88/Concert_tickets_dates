"""
Multiple concert data sources for better coverage of Italian concerts
"""
import aiohttp
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import re
from comprehensive_concert_db import ComprehensiveConcertDatabase
from official_concert_scraper import OfficialConcertScraper
from verified_concert_database import VerifiedConcertDatabase

logger = logging.getLogger(__name__)

class MultiSourceConcertFinder:
    """
    Searches multiple sources for concerts to improve coverage beyond TicketMaster
    """
    
    def __init__(self, ticketmaster_api):
        self.ticketmaster = ticketmaster_api
        self.session = None
        self.comprehensive_db = ComprehensiveConcertDatabase()
        self.official_scraper = OfficialConcertScraper()
        self.verified_db = VerifiedConcertDatabase()
    
    async def get_session(self):
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close_session(self):
        """Close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
        await self.official_scraper.close_session()
    
    async def search_all_sources(self, artist_name: str, country_code: str = "IT") -> List[Dict]:
        """
        Search all available sources for concerts - Only Italian events from activation date onwards
        """
        # Strict Italy-only filtering
        if country_code.upper() != "IT":
            logger.info(f"Rejecting search request for {artist_name} - Only Italian events are monitored")
            return []
        
        logger.info(f"Starting Italian concert search for {artist_name}")
        all_concerts = []
        
        # 1. Check verified concert database (manually verified authentic Italian data)
        try:
            verified_concerts = self.verified_db.search_concerts(artist_name, country_code)
            if verified_concerts:
                # Additional filtering to ensure all concerts are in Italy and future dates
                italian_future_concerts = [
                    concert for concert in verified_concerts 
                    if concert.get('country', '').upper() == 'ITALY' and 
                    self._is_future_event(concert.get('date', ''))
                ]
                
                if italian_future_concerts:
                    all_concerts.extend(italian_future_concerts)
                    logger.info(f"Verified database found {len(italian_future_concerts)} future Italian concerts for {artist_name}")
        except Exception as e:
            logger.error(f"Verified database search error for {artist_name}: {e}")
        
        # 2. Check TicketMaster API for real-time concert data
        try:
            ticketmaster_concerts = await self.ticketmaster.search_concerts(artist_name, country_code)
            if ticketmaster_concerts:
                # Filter for Italian future events
                italian_tm_concerts = [
                    concert for concert in ticketmaster_concerts 
                    if concert.get('country', '').upper() == 'ITALY' and 
                    self._is_future_event(concert.get('date', ''))
                ]
                
                if italian_tm_concerts:
                    all_concerts.extend(italian_tm_concerts)
                    logger.info(f"TicketMaster API found {len(italian_tm_concerts)} future Italian concerts for {artist_name}")
                else:
                    logger.info(f"TicketMaster API search completed but no future Italian concerts found for {artist_name}")
            else:
                logger.info(f"TicketMaster API returned no results for {artist_name}")
        except Exception as e:
            logger.error(f"TicketMaster API search error for {artist_name}: {e}")
        
        # 3. Check official band websites (web scraping for Italian venues only)
        try:
            official_concerts = await self.official_scraper.search_official_concerts(artist_name, country_code)
            if official_concerts:
                # Additional filtering to ensure only Italian events
                italian_concerts = [
                    concert for concert in official_concerts 
                    if concert.get('country', '').upper() == 'ITALY' and 
                    self._is_future_event(concert.get('date', ''))
                ]
                
                if italian_concerts:
                    all_concerts.extend(italian_concerts)
                    logger.info(f"Official website found {len(italian_concerts)} future Italian concerts for {artist_name}")
        except Exception as e:
            logger.error(f"Official website search error for {artist_name}: {e}")
        
        # Remove duplicates based on concert ID or similar attributes
        unique_concerts = []
        seen_concerts = set()
        for concert in all_concerts:
            concert_key = f"{concert.get('name', '')}-{concert.get('date', '')}-{concert.get('venue', '')}"
            if concert_key not in seen_concerts:
                seen_concerts.add(concert_key)
                unique_concerts.append(concert)
        
        if unique_concerts:
            logger.info(f"Total unique Italian concerts found for {artist_name}: {len(unique_concerts)}")
        else:
            logger.info(f"No authentic Italian concerts found for {artist_name} - monitoring continues")
        
        return unique_concerts
    
    def _is_future_event(self, date_str: str) -> bool:
        """Check if event date is in the future"""
        try:
            from datetime import datetime
            event_date = datetime.strptime(date_str, '%Y-%m-%d')
            is_future = event_date > datetime.now()
            logger.info(f"Date check: {date_str} is {'future' if is_future else 'past'}")
            return is_future
        except:
            logger.warning(f"Unable to parse date: {date_str}")
            return False
    
    async def _search_by_attraction_id(self, attraction_id: str, country_code: str) -> List[Dict]:
        """
        Search for events using the attraction (artist) ID
        """
        start_date = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        end_date = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        params = {
            'attractionId': attraction_id,
            'countryCode': country_code,
            'startDateTime': start_date,
            'endDateTime': end_date,
            'size': 50,
            'sort': 'date,asc'
        }
        
        response = await self.ticketmaster._make_request('events.json', params)
        
        concerts = []
        if response and response.get('_embedded', {}).get('events'):
            events = response.get('_embedded', {}).get('events', [])
            for event in events:
                concert = self.ticketmaster._parse_event(event)
                if concert:
                    concerts.append(concert)
        
        return concerts
    
    async def _search_songkick(self, artist_name: str, country_code: str) -> List[Dict]:
        """Search Songkick for concerts"""
        concerts = []
        try:
            session = await self.get_session()
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # Search for the artist on Songkick
            url = f"https://www.songkick.com/search"
            params = {
                'query': artist_name,
                'type': 'artists'
            }
            
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    text = await response.text()
                    # Look for Italy concerts in the response
                    if 'italy' in text.lower() or 'italia' in text.lower():
                        logger.info(f"Songkick found potential Italy concerts for {artist_name}")
                        
        except Exception as e:
            logger.error(f"Songkick search error: {e}")
        
        return concerts
    
    async def _search_bandsintown(self, artist_name: str, country_code: str) -> List[Dict]:
        """Search Bandsintown for concerts"""
        concerts = []
        try:
            session = await self.get_session()
            # Would need Bandsintown API key for real implementation
            logger.info(f"Bandsintown search attempted for {artist_name}")
        except Exception as e:
            logger.error(f"Bandsintown search error: {e}")
        
        return concerts
    
    # REMOVED: Duplicate concert database that could cause date conflicts
    # All authentic concert data now exclusively from verified_concert_database.py
    
    def create_sample_concert(self, artist_name: str) -> Optional[Dict]:
        """
        DEPRECATED: This function created fake concert data which violates data integrity.
        Always return None to prevent fake concert creation.
        """
        # Never create fake concerts - always return None to maintain data integrity
        return None