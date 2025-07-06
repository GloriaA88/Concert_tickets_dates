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
        
        # 3. Simulate future concert detection (placeholder for additional sources)
        # This is where you could add other Italian concert platforms
        if not all_concerts:
            logger.info(f"No concerts found in primary sources for {artist_name}")
            # In a real implementation, you could add:
            # - TicketOne.it API
            # - Songkick API  
            # - Bandsintown API
            # - Local venue websites scraping
        
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