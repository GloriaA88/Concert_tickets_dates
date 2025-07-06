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
        Search all available sources for concerts - Official websites + TicketMaster data
        """
        all_concerts = []
        
        # 1. PRIORITY: Verified concert database (manually verified authentic data)
        try:
            verified_concerts = self.verified_db.search_concerts(artist_name, country_code)
            if verified_concerts:
                all_concerts.extend(verified_concerts)
                logger.info(f"Verified database found {len(verified_concerts)} authentic concerts for {artist_name}")
                # Return immediately if we found verified concerts - these are the most reliable
                return verified_concerts
        except Exception as e:
            logger.error(f"Verified database search error for {artist_name}: {e}")
        
        # 2. FALLBACK: Official band websites (web scraping)
        try:
            official_concerts = await self.official_scraper.search_official_concerts(artist_name, country_code)
            if official_concerts:
                all_concerts.extend(official_concerts)
                logger.info(f"Official website found {len(official_concerts)} authentic concerts for {artist_name}")
                # Return immediately if we found official concerts - these are the most reliable
                return official_concerts
        except Exception as e:
            logger.error(f"Official website search error for {artist_name}: {e}")
        
        # 3. FALLBACK: TicketMaster API (if no official data found)
        try:
            tm_concerts = await self.ticketmaster.search_concerts(artist_name, country_code)
            for concert in tm_concerts:
                concert['source'] = 'TicketMaster'
                concert['verified'] = True
            all_concerts.extend(tm_concerts)
            logger.info(f"TicketMaster found {len(tm_concerts)} authentic concerts for {artist_name}")
        except Exception as e:
            logger.error(f"TicketMaster search error for {artist_name}: {e}")
        
        # 3. Try attraction-based search with the found artist ID
        if not all_concerts:
            try:
                artist_info = await self.ticketmaster.get_artist_info(artist_name)
                if artist_info and artist_info.get('id'):
                    logger.info(f"Found artist ID {artist_info['id']} for {artist_name}, searching by attraction...")
                    attraction_concerts = await self._search_by_attraction_id(
                        artist_info['id'], country_code
                    )
                    for concert in attraction_concerts:
                        concert['source'] = 'TicketMaster-Attraction'
                        concert['verified'] = True
                    all_concerts.extend(attraction_concerts)
                    logger.info(f"Attraction search found {len(attraction_concerts)} concerts")
            except Exception as e:
                logger.error(f"Attraction search error for {artist_name}: {e}")
        
        # REMOVED: Legacy known concert data (could conflict with verified database)
        
        # 5. Search Songkick (alternative concert database) - only if still no results
        if not all_concerts:
            try:
                songkick_concerts = await self._search_songkick(artist_name, country_code)
                all_concerts.extend(songkick_concerts)
                logger.info(f"Songkick found {len(songkick_concerts)} concerts for {artist_name}")
            except Exception as e:
                logger.error(f"Songkick search error for {artist_name}: {e}")
        
        # 6. Search Bandsintown (another alternative) - only if still no results
        if not all_concerts:
            try:
                bandsintown_concerts = await self._search_bandsintown(artist_name, country_code)
                all_concerts.extend(bandsintown_concerts)
                logger.info(f"Bandsintown found {len(bandsintown_concerts)} concerts for {artist_name}")
            except Exception as e:
                logger.error(f"Bandsintown search error for {artist_name}: {e}")
        
        return all_concerts
    
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
    
    def create_sample_concert(self, artist_name: str) -> Dict:
        """
        DEPRECATED: This function created fake concert data which violates data integrity.
        Always return None to prevent fake concert creation.
        """
        # Never create fake concerts - always return None to maintain data integrity
        return None