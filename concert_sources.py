"""
Multiple concert data sources for better coverage of Italian concerts
"""
import aiohttp
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import re
from comprehensive_concert_db import ComprehensiveConcertDatabase

logger = logging.getLogger(__name__)

class MultiSourceConcertFinder:
    """
    Searches multiple sources for concerts to improve coverage beyond TicketMaster
    """
    
    def __init__(self, ticketmaster_api):
        self.ticketmaster = ticketmaster_api
        self.session = None
        self.comprehensive_db = ComprehensiveConcertDatabase()
    
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
        Search all available sources for concerts - prioritizing comprehensive database
        """
        all_concerts = []
        
        # 1. PRIORITY: Search comprehensive database first (official announcements)
        try:
            comprehensive_concerts = self.comprehensive_db.search_concerts(artist_name, country_code)
            if comprehensive_concerts:
                all_concerts.extend(comprehensive_concerts)
                logger.info(f"Comprehensive DB found {len(comprehensive_concerts)} official concerts for {artist_name}")
                # Return immediately if we found official concerts - these are the most reliable
                return comprehensive_concerts
        except Exception as e:
            logger.error(f"Comprehensive DB search failed for {artist_name}: {e}")
        
        # 2. TicketMaster (primary API source)
        try:
            tm_concerts = await self.ticketmaster.search_concerts(artist_name, country_code)
            for concert in tm_concerts:
                concert['source'] = 'TicketMaster'
                concert['verified'] = True
            all_concerts.extend(tm_concerts)
            logger.info(f"TicketMaster found {len(tm_concerts)} concerts for {artist_name}")
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
        
        # 4. Search legacy known concert data (fallback)
        try:
            known_concerts = await self._search_known_concerts(artist_name, country_code)
            all_concerts.extend(known_concerts)
            logger.info(f"Known concerts found {len(known_concerts)} for {artist_name}")
        except Exception as e:
            logger.error(f"Known concerts search error for {artist_name}: {e}")
        
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
    
    async def _search_known_concerts(self, artist_name: str, country_code: str) -> List[Dict]:
        """Search database of known announced concerts"""
        concerts = []
        
        # CRITICAL: Only add concerts that are OFFICIALLY ANNOUNCED and VERIFIED
        # This database should remain empty unless concerts are confirmed through official sources
        # If no official events exist, this returns empty so the bot reports no events
        known_concerts_db = {
            # Only officially announced and verified concerts from official sources
            # Data verified through official announcements and ticketing platforms
            'metallica': [
                {
                    'id': 'metallica_bologna_2026_06_03',
                    'name': 'Metallica - M72 World Tour',
                    'date': '2026-06-03',
                    'time': '20:30',
                    'venue': 'Stadio Renato Dall\'Ara',
                    'city': 'Bologna',
                    'country': 'Italy',
                    'url': 'https://www.ticketmaster.it/artist/metallica-tickets/1240',
                    'source': 'Official Metallica.com Announcement',
                    'verified': True,
                    'support_acts': ['Gojira', 'Knocked Loose'],
                    'ticket_info': 'Presale: 27 May 2025 | General Sale: 30 May 2025',
                    'official_announcement': 'https://www.metallica.com/tour/2026-06-03-bologna-italy.html'
                }
            ]
        }
        
        # Normalize artist name for matching with multiple search patterns
        artist_key = artist_name.lower().strip()
        
        # Direct match
        if artist_key in known_concerts_db:
            for concert_data in known_concerts_db[artist_key]:
                concerts.append(concert_data)
                logger.info(f"Found known concert: {concert_data['name']} on {concert_data['date']}")
        
        # Fuzzy matching for similar artist names
        if len(concerts) == 0:
            # Check for partial matches or common variations
            for known_artist in known_concerts_db.keys():
                # Check if the searched artist name is contained within known artist names
                if artist_key in known_artist or known_artist in artist_key:
                    # Check similarity score (simple approach)
                    if len(artist_key) > 3 and len(known_artist) > 3:
                        # Count matching characters
                        matching_chars = sum(1 for c in artist_key if c in known_artist)
                        similarity = matching_chars / max(len(artist_key), len(known_artist))
                        
                        if similarity > 0.7:  # 70% similarity threshold
                            for concert_data in known_concerts_db[known_artist]:
                                concerts.append(concert_data)
                                logger.info(f"Found known concert via fuzzy match ({known_artist} ~ {artist_key}): {concert_data['name']} on {concert_data['date']}")
                            break  # Found a match, no need to continue
        
        logger.info(f"Known concerts found {len(concerts)} for {artist_name}")
        return concerts
    
    def create_sample_concert(self, artist_name: str) -> Dict:
        """
        DEPRECATED: This function created fake concert data which violates data integrity.
        Always return None to prevent fake concert creation.
        """
        # Never create fake concerts - always return None to maintain data integrity
        return None