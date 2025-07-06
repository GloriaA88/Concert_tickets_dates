"""
TicketMaster API integration for concert data
"""
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import asyncio

logger = logging.getLogger(__name__)

class TicketMasterAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://app.ticketmaster.com/discovery/v2"
        self.session = None
        self.rate_limit_delay = 0.2  # 200ms delay between requests
        self.last_request_time = 0
    
    async def get_session(self):
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close_session(self):
        """Close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def _rate_limit(self):
        """Simple rate limiting"""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - time_since_last)
        
        self.last_request_time = asyncio.get_event_loop().time()
    
    async def _make_request(self, endpoint: str, params: dict) -> Optional[dict]:
        """Make an API request with error handling"""
        await self._rate_limit()
        
        params['apikey'] = self.api_key
        url = f"{self.base_url}/{endpoint}"
        
        session = await self.get_session()
        
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 429:
                    # Rate limited, wait and retry once
                    logger.warning("Rate limited by TicketMaster API, waiting...")
                    await asyncio.sleep(1)
                    async with session.get(url, params=params) as retry_response:
                        if retry_response.status == 200:
                            return await retry_response.json()
                        else:
                            logger.error(f"TicketMaster API error after retry: {retry_response.status}")
                            return None
                else:
                    logger.error(f"TicketMaster API error: {response.status}")
                    return None
        
        except asyncio.TimeoutError:
            logger.error("TicketMaster API request timeout")
            return None
        except Exception as e:
            logger.error(f"TicketMaster API request error: {e}")
            return None
    
    async def search_concerts(self, 
                            artist_name: str, 
                            country_code: str = "IT",
                            limit: int = 20) -> List[Dict]:
        """Search for concerts by artist name in specified country"""
        
        # Get date range for next 2 years (infinite-like range)
        start_date = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        end_date = (datetime.now() + timedelta(days=730)).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Try multiple search strategies for better results
        search_strategies = [
            # Strategy 1: Exact artist name
            {
                'keyword': artist_name,
                'countryCode': country_code,
                'classificationName': 'music',
                'startDateTime': start_date,
                'endDateTime': end_date,
                'size': limit,
                'sort': 'date,asc'
            },
            # Strategy 2: Try without classification restriction
            {
                'keyword': artist_name,
                'countryCode': country_code,
                'startDateTime': start_date,
                'endDateTime': end_date,
                'size': limit,
                'sort': 'date,asc'
            },
            # Strategy 3: Search by attraction (artist) first, then events
            {
                'attractionId': None,  # Will be filled if we find the artist
                'countryCode': country_code,
                'classificationName': 'music',
                'startDateTime': start_date,
                'endDateTime': end_date,
                'size': limit,
                'sort': 'date,asc'
            }
        ]
        
        concerts = []
        
        # Try different search strategies until we find results
        for i, strategy in enumerate(search_strategies[:2]):  # Skip strategy 3 for now
            logger.info(f"Trying search strategy {i+1} for '{artist_name}'")
            response = await self._make_request('events.json', strategy)
            
            if response and response.get('_embedded', {}).get('events'):
                events = response.get('_embedded', {}).get('events', [])
                
                for event in events:
                    concert = self._parse_event(event)
                    if concert:
                        concerts.append(concert)
                
                logger.info(f"Found {len(concerts)} concerts for '{artist_name}' in {country_code} using strategy {i+1}")
                break
            else:
                logger.info(f"No results found with strategy {i+1} for '{artist_name}'")
        
        # If no concerts found with regular search, try broader search strategies
        if not concerts:
            logger.info(f"Trying broader search for '{artist_name}'")
            
            # Strategy 1: Remove all filters except country
            broad_params = {
                'keyword': artist_name,
                'countryCode': country_code,
                'size': limit
            }
            response = await self._make_request('events.json', broad_params)
            
            if response and response.get('_embedded', {}).get('events'):
                events = response.get('_embedded', {}).get('events', [])
                for event in events:
                    concert = self._parse_event(event)
                    if concert:
                        concerts.append(concert)
                logger.info(f"Broad search found {len(concerts)} events for '{artist_name}'")
            
            # Strategy 2: Try with extended date range (2 years)
            if not concerts:
                logger.info(f"Trying extended date range search for '{artist_name}'")
                extended_end_date = (datetime.now() + timedelta(days=730)).strftime("%Y-%m-%dT%H:%M:%SZ")
                extended_params = {
                    'keyword': artist_name,
                    'countryCode': country_code,
                    'startDateTime': start_date,
                    'endDateTime': extended_end_date,
                    'size': limit
                }
                response = await self._make_request('events.json', extended_params)
                
                if response and response.get('_embedded', {}).get('events'):
                    events = response.get('_embedded', {}).get('events', [])
                    for event in events:
                        concert = self._parse_event(event)
                        if concert:
                            concerts.append(concert)
                    logger.info(f"Extended search found {len(concerts)} events for '{artist_name}'")
            
            # Strategy 3: Try searching by attraction first
            if not concerts:
                logger.info(f"Trying attraction-based search for '{artist_name}'")
                artist_info = await self.get_artist_info(artist_name)
                extended_end_date = (datetime.now() + timedelta(days=730)).strftime("%Y-%m-%dT%H:%M:%SZ")
                
                if artist_info and artist_info.get('id'):
                    attraction_params = {
                        'attractionId': artist_info['id'],
                        'countryCode': country_code,
                        'startDateTime': start_date,
                        'endDateTime': extended_end_date,
                        'size': limit
                    }
                    response = await self._make_request('events.json', attraction_params)
                    
                    if response and response.get('_embedded', {}).get('events'):
                        events = response.get('_embedded', {}).get('events', [])
                        for event in events:
                            concert = self._parse_event(event)
                            if concert:
                                concerts.append(concert)
                        logger.info(f"Attraction-based search found {len(concerts)} events for '{artist_name}'")
        
        return concerts
    
    def _parse_event(self, event: dict) -> Optional[Dict]:
        """Parse a TicketMaster event into our concert format"""
        try:
            concert = {
                'id': event.get('id'),
                'name': event.get('name', 'Unknown Event'),
                'url': event.get('url', ''),
                'date': 'TBD',
                'time': '',
                'venue': 'Unknown Venue',
                'city': 'Unknown City',
                'country': 'Italy',
                'price_range': '',
                'genre': '',
                'image_url': ''
            }
            
            # Parse date and time
            dates = event.get('dates', {})
            if dates.get('start'):
                start_date = dates['start']
                if start_date.get('localDate'):
                    concert['date'] = start_date['localDate']
                if start_date.get('localTime'):
                    concert['time'] = start_date['localTime']
            
            # Parse venue information
            embedded = event.get('_embedded', {})
            venues = embedded.get('venues', [])
            if venues:
                venue = venues[0]
                concert['venue'] = venue.get('name', 'Unknown Venue')
                
                city = venue.get('city', {})
                if city and city.get('name'):
                    concert['city'] = city['name']
                
                country = venue.get('country', {})
                if country and country.get('name'):
                    concert['country'] = country['name']
            
            # Parse price range
            price_ranges = event.get('priceRanges', [])
            if price_ranges:
                price_range = price_ranges[0]
                min_price = price_range.get('min', 0)
                max_price = price_range.get('max', 0)
                currency = price_range.get('currency', 'EUR')
                
                if min_price and max_price:
                    concert['price_range'] = f"{min_price}-{max_price} {currency}"
                elif min_price:
                    concert['price_range'] = f"From {min_price} {currency}"
            
            # Parse genre
            classifications = event.get('classifications', [])
            if classifications:
                genre = classifications[0].get('genre', {})
                if genre and genre.get('name'):
                    concert['genre'] = genre['name']
            
            # Parse image
            images = event.get('images', [])
            if images:
                # Try to get a medium-sized image
                for image in images:
                    if image.get('width', 0) >= 300:
                        concert['image_url'] = image.get('url', '')
                        break
                if not concert['image_url'] and images:
                    concert['image_url'] = images[0].get('url', '')
            
            return concert
            
        except Exception as e:
            logger.error(f"Error parsing event: {e}")
            return None
    
    async def get_artist_info(self, artist_name: str) -> Optional[Dict]:
        """Get information about an artist"""
        params = {
            'keyword': artist_name,
            'size': 1
        }
        
        response = await self._make_request('attractions.json', params)
        
        if not response:
            return None
        
        attractions = response.get('_embedded', {}).get('attractions', [])
        
        if attractions:
            artist = attractions[0]
            return {
                'id': artist.get('id'),
                'name': artist.get('name'),
                'url': artist.get('url', ''),
                'image_url': artist.get('images', [{}])[0].get('url', '') if artist.get('images') else '',
                'genre': artist.get('classifications', [{}])[0].get('genre', {}).get('name', '') if artist.get('classifications') else ''
            }
        
        return None
    
    async def get_venues_in_italy(self) -> List[Dict]:
        """Get popular venues in Italy"""
        params = {
            'countryCode': 'IT',
            'size': 100
        }
        
        response = await self._make_request('venues.json', params)
        
        if not response:
            return []
        
        venues = []
        venue_data = response.get('_embedded', {}).get('venues', [])
        
        for venue in venue_data:
            venue_info = {
                'id': venue.get('id'),
                'name': venue.get('name'),
                'city': venue.get('city', {}).get('name', ''),
                'address': venue.get('address', {}).get('line1', ''),
                'capacity': venue.get('capacity', 0),
                'url': venue.get('url', '')
            }
            venues.append(venue_info)
        
        return venues
