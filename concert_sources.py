"""
Multiple concert data sources for better coverage of Italian concerts
"""
import aiohttp
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import re

logger = logging.getLogger(__name__)

class MultiSourceConcertFinder:
    """
    Searches multiple sources for concerts to improve coverage beyond TicketMaster
    """
    
    def __init__(self, ticketmaster_api):
        self.ticketmaster = ticketmaster_api
        self.session = None
    
    async def get_session(self):
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close_session(self):
        """Close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def search_all_sources(self, artist_name: str, country_code: str = "IT") -> List[Dict]:
        """
        Search all available sources for concerts
        """
        all_concerts = []
        
        # 1. TicketMaster (primary source)
        try:
            tm_concerts = await self.ticketmaster.search_concerts(artist_name, country_code)
            for concert in tm_concerts:
                concert['source'] = 'TicketMaster'
                concert['verified'] = True
            all_concerts.extend(tm_concerts)
            logger.info(f"TicketMaster found {len(tm_concerts)} concerts for {artist_name}")
        except Exception as e:
            logger.error(f"TicketMaster search error for {artist_name}: {e}")
        
        # 2. Try attraction-based search with the found artist ID
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
        
        # 3. Search Songkick (alternative concert database)
        if not all_concerts:
            try:
                songkick_concerts = await self._search_songkick(artist_name, country_code)
                all_concerts.extend(songkick_concerts)
                logger.info(f"Songkick found {len(songkick_concerts)} concerts for {artist_name}")
            except Exception as e:
                logger.error(f"Songkick search error for {artist_name}: {e}")
        
        # 4. Search Bandsintown (another alternative)
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
            # Songkick doesn't require API key for basic searches
            url = "https://www.songkick.com/search"
            params = {
                'query': artist_name,
                'type': 'artists'
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    # For now, return empty - would need HTML parsing for real implementation
                    logger.info(f"Songkick search accessed for {artist_name}")
                    pass
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
    
    def create_sample_concert(self, artist_name: str) -> Dict:
        """
        Create a sample concert notification to demonstrate the system
        (for testing purposes when no real concerts are found)
        """
        return {
            'id': f'sample_{artist_name.lower().replace(" ", "_")}',
            'name': f'{artist_name} - Tour 2025',
            'date': '2025-12-15',
            'venue': 'Palazzo dello Sport',
            'city': 'Roma',
            'country': 'Italy',
            'url': 'https://www.ticketmaster.it/artist/sample',
            'source': 'Sample',
            'verified': False,
            'note': 'Questo è un esempio di come appariranno le notifiche quando saranno trovati concerti reali.'
        }