"""
Official Concert Scraper for Italian Events
This module scrapes official band websites to find authentic concert announcements
"""
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import re
import trafilatura

logger = logging.getLogger(__name__)

class OfficialConcertScraper:
    """
    Scrapes official band websites for authentic concert announcements in Italy
    """
    
    def __init__(self):
        self.session = None
        self.official_sources = {
            'metallica': {
                'url': 'https://www.metallica.com/events',
                'ticketmaster_base': 'https://www.ticketmaster.it/artist/metallica-tickets/1240'
            },
            'green day': {
                'url': 'https://www.greenday.com/tour',
                'ticketmaster_base': 'https://www.ticketmaster.it/artist/green-day-tickets/895'
            },
            'linkin park': {
                'url': 'https://www.linkinpark.com/tour',
                'ticketmaster_base': 'https://www.ticketmaster.it/artist/linkin-park-tickets/1223'
            },
            'pearl jam': {
                'url': 'https://pearljam.com/tour',
                'ticketmaster_base': 'https://www.ticketmaster.it/artist/pearl-jam-tickets/1156'
            },
            'coldplay': {
                'url': 'https://www.coldplay.com/tour',
                'ticketmaster_base': 'https://www.ticketmaster.it/artist/coldplay-tickets/806'
            },
            'imagine dragons': {
                'url': 'https://www.imaginedragonsmusic.com/tour',
                'ticketmaster_base': 'https://www.ticketmaster.it/artist/imagine-dragons-tickets/1503'
            },
            'u2': {
                'url': 'https://www.u2.com/tour',
                'ticketmaster_base': 'https://www.ticketmaster.it/artist/u2-tickets/734'
            },
            'radiohead': {
                'url': 'https://www.radiohead.com/tour',
                'ticketmaster_base': 'https://www.ticketmaster.it/artist/radiohead-tickets/928'
            },
            'arctic monkeys': {
                'url': 'https://www.arcticmonkeys.com/tour',
                'ticketmaster_base': 'https://www.ticketmaster.it/artist/arctic-monkeys-tickets/1287'
            },
            'muse': {
                'url': 'https://www.muse.mu/tour',
                'ticketmaster_base': 'https://www.ticketmaster.it/artist/muse-tickets/1043'
            }
        }
    
    async def get_session(self):
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close_session(self):
        """Close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def search_official_concerts(self, artist_name: str, country_code: str = "IT") -> List[Dict]:
        """
        Search for concerts by checking official band websites
        """
        if country_code.upper() != "IT":
            return []
        
        normalized_name = artist_name.lower().strip()
        
        # Check if we have official sources for this artist
        if normalized_name not in self.official_sources:
            logger.info(f"No official source configured for {artist_name}")
            return []
        
        try:
            source_info = self.official_sources[normalized_name]
            concerts = await self._scrape_official_site(normalized_name, source_info)
            
            if concerts:
                logger.info(f"Found {len(concerts)} official concerts for {artist_name}")
                return concerts
            else:
                logger.info(f"No Italian concerts found on official site for {artist_name}")
                return []
                
        except Exception as e:
            logger.error(f"Error scraping official site for {artist_name}: {e}")
            return []
    
    async def _scrape_official_site(self, artist_name: str, source_info: Dict) -> List[Dict]:
        """
        Scrape official website for concert information
        """
        try:
            session = await self.get_session()
            
            # Fetch the webpage
            async with session.get(source_info['url']) as response:
                if response.status != 200:
                    logger.warning(f"Failed to fetch {source_info['url']}: {response.status}")
                    return []
                
                html_content = await response.text()
            
            # Extract text content using trafilatura
            text_content = trafilatura.extract(html_content)
            
            if not text_content:
                logger.warning(f"No content extracted from {source_info['url']}")
                return []
            
            # Parse the content for Italian concerts
            concerts = self._parse_tour_content(text_content, artist_name, source_info)
            
            return concerts
            
        except Exception as e:
            logger.error(f"Error scraping {source_info['url']}: {e}")
            return []
    
    def _parse_tour_content(self, content: str, artist_name: str, source_info: Dict) -> List[Dict]:
        """
        Parse scraped content to extract Italian concert information
        """
        concerts = []
        
        # Look for Italian cities and venues
        italian_indicators = [
            'italy', 'italia', 'milan', 'milano', 'rome', 'roma', 'bologna', 'florence', 
            'firenze', 'turin', 'torino', 'naples', 'napoli', 'venice', 'venezia',
            'san siro', 'stadio olimpico', 'palazzo dello sport', 'mediolanum forum',
            'unipol forum', 'palasport', 'arena'
        ]
        
        # Look for dates in the content
        date_patterns = [
            r'(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})',  # DD/MM/YYYY, DD-MM-YYYY, etc.
            r'(\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2})',    # YYYY/MM/DD, YYYY-MM-DD, etc.
            r'(\w+\s+\d{1,2},?\s+\d{4})',              # Month DD, YYYY
            r'(\d{1,2}\s+\w+\s+\d{4})',                # DD Month YYYY
        ]
        
        lines = content.lower().split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Check if line contains Italian indicators
            has_italian = any(indicator in line for indicator in italian_indicators)
            
            if has_italian:
                # Try to extract date from this line or nearby lines
                for pattern in date_patterns:
                    dates = re.findall(pattern, line)
                    for date_str in dates:
                        try:
                            # Try to parse the date
                            concert_date = self._parse_date(date_str)
                            
                            if concert_date and concert_date > datetime.now():
                                # Extract venue and city information
                                venue_info = self._extract_venue_info(line)
                                
                                concert = {
                                    'id': f"{artist_name}_{venue_info['city']}_{concert_date.strftime('%Y_%m_%d')}",
                                    'name': f"{artist_name.title()} - Live in {venue_info['city']}",
                                    'date': concert_date.strftime('%Y-%m-%d'),
                                    'time': '20:00',  # Default time
                                    'venue': venue_info['venue'],
                                    'city': venue_info['city'],
                                    'country': 'Italy',
                                    'url': source_info['ticketmaster_base'],
                                    'source': f"Official {artist_name.title()} website",
                                    'verified': True,
                                    'artist': artist_name.title(),
                                    'ticket_info': 'Tickets available via TicketMaster Italy'
                                }
                                
                                concerts.append(concert)
                                logger.info(f"Found concert: {artist_name} in {venue_info['city']} on {concert_date.strftime('%Y-%m-%d')}")
                                
                        except Exception as e:
                            logger.debug(f"Could not parse date '{date_str}': {e}")
                            continue
        
        return concerts
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse various date formats into datetime object
        """
        date_formats = [
            '%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y',
            '%Y/%m/%d', '%Y-%m-%d', '%Y.%m.%d',
            '%B %d, %Y', '%d %B %Y',
            '%b %d, %Y', '%d %b %Y'
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        return None
    
    def _extract_venue_info(self, line: str) -> Dict[str, str]:
        """
        Extract venue and city information from a line
        """
        # Italian cities mapping
        city_mappings = {
            'milan': 'Milano', 'milano': 'Milano',
            'rome': 'Roma', 'roma': 'Roma',
            'bologna': 'Bologna',
            'florence': 'Firenze', 'firenze': 'Firenze',
            'turin': 'Torino', 'torino': 'Torino',
            'naples': 'Napoli', 'napoli': 'Napoli',
            'venice': 'Venezia', 'venezia': 'Venezia'
        }
        
        # Venue mappings
        venue_mappings = {
            'san siro': 'Stadio San Siro',
            'stadio olimpico': 'Stadio Olimpico',
            'mediolanum forum': 'Mediolanum Forum',
            'unipol forum': 'Unipol Forum',
            'palazzo dello sport': 'Palazzo dello Sport'
        }
        
        # Default values
        city = 'Milano'
        venue = 'TBA'
        
        # Extract city
        for key, value in city_mappings.items():
            if key in line:
                city = value
                break
        
        # Extract venue
        for key, value in venue_mappings.items():
            if key in line:
                venue = value
                break
        
        return {'city': city, 'venue': venue}
    
    def get_supported_artists(self) -> List[str]:
        """
        Get list of artists we can scrape official data for
        """
        return list(self.official_sources.keys())