"""
Verified Concert Database with real, officially announced concerts
This module contains only verified, officially announced concerts with proper TicketMaster links
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class VerifiedConcertDatabase:
    """
    Database of verified, officially announced concerts in Italy
    All data is sourced from official announcements and verified ticket sources
    """
    
    def __init__(self):
        self.verified_concerts = self._load_verified_concerts()
    
    def _load_verified_concerts(self) -> List[Dict]:
        """
        Load verified concerts from official sources
        Each concert is manually verified from official announcements
        """
        return [
            # Metallica - OFFICIAL M72 World Tour (REAL DATA FROM METALLICA.COM)
            {
                'id': 'metallica_bologna_2026_06_03',
                'name': 'Metallica - M72 World Tour',
                'date': '2026-06-03',
                'time': '20:30',
                'venue': 'Stadio Renato Dall\'Ara',
                'city': 'Bologna',
                'country': 'Italy',
                'url': 'https://www.ticketmaster.it/artist/metallica-tickets/1240',
                'source': 'Official Metallica.com & TicketMaster Italy',
                'verified': True,
                'artist': 'Metallica',
                'support_acts': ['Gojira', 'Knocked Loose'],
                'ticket_info': 'Fan Club Presale: May 27, 2025 | General Sale: May 30, 2025',
                'price_range': 'TBA',
                'on_sale': False
            },

            # Linkin Park - OFFICIAL From Zero World Tour Milano 2026 (REAL DATA)
            {
                'id': 'linkin_park_milano_2026_06_24',
                'name': 'Linkin Park - From Zero World Tour (I-Days Milano)',
                'date': '2026-06-24',
                'time': '20:00',
                'venue': 'Ippodromo SNAI La Maura',
                'city': 'Milano',
                'country': 'Italy',
                'url': 'https://www.ticketmaster.it/artist/linkin-park-tickets/10021',
                'source': 'Official Linkin Park & TicketMaster Italy',
                'verified': True,
                'artist': 'Linkin Park',
                'support_acts': ['TBA'],
                'ticket_info': 'SOLD OUT - Was available via TicketMaster Italy',
                'price_range': 'TBA',
                'on_sale': False
            },
            # Linkin Park - OFFICIAL From Zero World Tour Firenze 2026 (REAL DATA)
            {
                'id': 'linkin_park_florence_2026_06_26',
                'name': 'Linkin Park - From Zero World Tour',
                'date': '2026-06-26',
                'time': '20:30',
                'venue': 'Ippodromo del Visarno',
                'city': 'Firenze',
                'country': 'Italy',
                'url': 'https://www.ticketmaster.it/artist/linkin-park-tickets/10021',
                'source': 'Official Linkin Park & TicketMaster Italy',
                'verified': True,
                'artist': 'Linkin Park',
                'support_acts': ['TBA'],
                'ticket_info': 'General Sale: June 6, 2025 at 9:00 AM',
                'price_range': 'TBA',
                'on_sale': False
            }
        ]
    
    def search_concerts(self, artist_name: str, country_code: str = "IT") -> List[Dict]:
        """
        Search for verified concerts by artist name
        """
        # Strict Italy-only filtering
        if country_code.upper() != "IT":
            logger.info(f"Rejecting search for {artist_name} - Country code '{country_code}' is not Italy")
            return []
        
        logger.info(f"Searching for Italian concerts for artist: {artist_name}")
        
        # Normalize artist name for search
        normalized_search = artist_name.lower().strip()
        
        # Search through verified concerts
        matching_concerts = []
        
        for concert in self.verified_concerts:
            concert_artist = concert['artist'].lower().strip()
            
            # Only consider concerts in Italy
            if concert.get('country', '').upper() != 'ITALY':
                continue
            
            # Exact match or contains match
            if normalized_search == concert_artist or normalized_search in concert_artist:
                if self._is_future_concert(concert['date']):
                    matching_concerts.append(concert)
                    logger.info(f"Found future Italian concert: {concert['name']} on {concert['date']}")
                    continue
            
            # Reverse match (artist name contains search term)
            if concert_artist in normalized_search:
                if self._is_future_concert(concert['date']):
                    matching_concerts.append(concert)
                    logger.info(f"Found future Italian concert: {concert['name']} on {concert['date']}")
                    continue
            
            # Fuzzy matching for similar names
            if self._fuzzy_match(normalized_search, concert_artist):
                if self._is_future_concert(concert['date']):
                    matching_concerts.append(concert)
                    logger.info(f"Found future Italian concert: {concert['name']} on {concert['date']}")
        
        if matching_concerts:
            logger.info(f"Total verified Italian concerts found for {artist_name}: {len(matching_concerts)}")
        else:
            logger.info(f"No verified Italian concerts found for {artist_name}")
        
        return matching_concerts
    
    def _fuzzy_match(self, search_name: str, artist_name: str) -> bool:
        """
        Fuzzy matching for artist names
        """
        search_words = set(search_name.split())
        artist_words = set(artist_name.split())
        
        # Check if main words match
        if search_words & artist_words:
            return True
        
        # Check for partial matches
        for search_word in search_words:
            for artist_word in artist_words:
                if len(search_word) > 3 and len(artist_word) > 3:
                    if search_word in artist_word or artist_word in search_word:
                        return True
        
        return False
    
    def _is_future_concert(self, date_str: str) -> bool:
        """
        Check if concert date is in the future
        """
        try:
            concert_date = datetime.strptime(date_str, '%Y-%m-%d')
            return concert_date > datetime.now()
        except:
            return False
    
    def get_all_verified_concerts(self) -> List[Dict]:
        """
        Get all verified concerts that are in the future
        """
        return [c for c in self.verified_concerts if self._is_future_concert(c['date'])]
    
    def get_verified_artists(self) -> List[str]:
        """
        Get list of artists with verified concerts
        """
        artists = set()
        for concert in self.verified_concerts:
            if self._is_future_concert(concert['date']):
                artists.add(concert['artist'])
        return sorted(list(artists))
    
    def get_concert_count(self) -> int:
        """
        Get total number of verified future concerts
        """
        return len([c for c in self.verified_concerts if self._is_future_concert(c['date'])])