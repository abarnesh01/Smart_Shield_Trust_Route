"""
OSRM (Open Source Routing Machine) Service - FREE Alternative to Google Maps
No API key required, no billing, completely free!
"""
import httpx
from typing import List, Dict, Optional, Tuple
import polyline
from datetime import datetime
import sys
from pathlib import Path
import asyncio

sys.path.append(str(Path(__file__).parent.parent.parent))

from api.schemas.delivery import Coordinate
from loguru import logger


class OSRMService:
    """Free routing service using OSRM - no API key needed!"""
    
    def __init__(self):
        # Public OSRM server (free, no API key)
        self.base_url = "https://router.project-osrm.org"
        # Backup server
        self.backup_url = "http://router.project-osrm.org"
        logger.info("OSRMService initialized (FREE - no API key needed)")
    
    def _get_lat_lng(self, point: any) -> Tuple[float, float]:
        """Utility to convert various point formats to (lat, lng) tuple"""
        if hasattr(point, 'latitude'):
            return (point.latitude, point.longitude)
        if isinstance(point, dict):
            if 'lat' in point:
                return (point['lat'], point['lng'])
            if 'latitude' in point:
                return (point['latitude'], point['longitude'])
        return point
    
    async def get_directions(
        self,
        origin: any,
        destination: any,
        waypoints: Optional[List[any]] = None,
        alternatives: bool = True,
        **kwargs
    ) -> Optional[List[Dict]]:
        """
        Get driving directions using OSRM (FREE!)
        
        Returns list of route alternatives in Google Maps-compatible format
        """
        try:
            orig = self._get_lat_lng(origin)
            dest = self._get_lat_lng(destination)
            
            # Build coordinates string: lng,lat;lng,lat
            coords = f"{orig[1]},{orig[0]}"
            
            # Add waypoints if provided
            if waypoints:
                for wp in waypoints:
                    wp_coords = self._get_lat_lng(wp)
                    coords += f";{wp_coords[1]},{wp_coords[0]}"
            
            coords += f";{dest[1]},{dest[0]}"
            
            # OSRM route request
            url = f"{self.base_url}/route/v1/driving/{coords}"
            params = {
                'overview': 'full',
                'geometries': 'polyline',
                'steps': 'true',
                'alternatives': 'true' if alternatives else 'false'
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('code') == 'Ok':
                    routes = self._parse_osrm_response(data, orig, dest)
                    logger.info(f"OSRM returned {len(routes)} route(s)")
                    return routes
                else:
                    logger.warning(f"OSRM error: {data.get('message')}")
                    return self._get_mock_directions(origin, destination)
            else:
                logger.warning(f"OSRM HTTP error: {response.status_code}")
                return self._get_mock_directions(origin, destination)
                
        except Exception as e:
            logger.warning(f"OSRM request failed: {e}, using mock data")
            return self._get_mock_directions(origin, destination)
    
    def _parse_osrm_response(self, data: Dict, orig: Tuple, dest: Tuple) -> List[Dict]:
        """Parse OSRM response into Google Maps-compatible format"""
        routes = []
        
        for idx, route in enumerate(data.get('routes', [])):
            # Extract route geometry
            geometry = route.get('geometry', '')
            route_coords = polyline.decode(geometry)
            
            # Get legs
            legs_data = route.get('legs', [])
            
            # Build Google Maps-compatible structure
            legs = []
            for leg in legs_data:
                steps = []
                for step in leg.get('steps', []):
                    # Decode step geometry
                    step_geom = step.get('geometry', '')
                    step_coords = polyline.decode(step_geom) if step_geom else []
                    
                    start_loc = step_coords[0] if step_coords else orig
                    end_loc = step_coords[-1] if step_coords else dest
                    
                    steps.append({
                        'distance': {
                            'text': f"{step.get('distance', 0) / 1000:.1f} km",
                            'value': int(step.get('distance', 0))
                        },
                        'duration': {
                            'text': f"{int(step.get('duration', 0) / 60)} mins",
                            'value': int(step.get('duration', 0))
                        },
                        'html_instructions': step.get('name', 'Continue'),
                        'start_location': {'lat': start_loc[0], 'lng': start_loc[1]},
                        'end_location': {'lat': end_loc[0], 'lng': end_loc[1]},
                        'maneuver': step.get('maneuver', {}).get('type', 'straight')
                    })
                
                legs.append({
                    'distance': {
                        'text': f"{leg.get('distance', 0) / 1000:.1f} km",
                        'value': int(leg.get('distance', 0))
                    },
                    'duration': {
                        'text': f"{int(leg.get('duration', 0) / 60)} mins",
                        'value': int(leg.get('duration', 0))
                    },
                    'start_address': f"{orig[0]}, {orig[1]}",
                    'end_address': f"{dest[0]}, {dest[1]}",
                    'steps': steps
                })
            
            # Convert route coordinates to dict format
            route_coordinates = [
                {'lat': coord[0], 'lng': coord[1]} 
                for coord in route_coords
            ]
            
            routes.append({
                'summary': f'Route {idx + 1} via OSRM',
                'legs': legs,
                'overview_polyline': {'points': geometry},
                'route_coordinates': route_coordinates,
                'warnings': [],
                'waypoint_order': []
            })
        
        return routes
    
    def _get_mock_directions(self, origin, destination) -> List[Dict]:
        """Generate mock directions when OSRM is unavailable"""
        orig = self._get_lat_lng(origin)
        dest = self._get_lat_lng(destination)
        
        # Calculate midpoint
        mid_lat = (orig[0] + dest[0]) / 2
        mid_lng = (orig[1] + dest[1]) / 2
        
        # Simple straight-line route
        route_coords = [orig, (mid_lat, mid_lng), dest]
        encoded = polyline.encode(route_coords)
        
        # Estimate distance (Haversine approximation)
        import math
        R = 6371000  # Earth radius in meters
        phi1 = orig[0] * math.pi / 180
        phi2 = dest[0] * math.pi / 180
        dphi = (dest[0] - orig[0]) * math.pi / 180
        dlambda = (dest[1] - orig[1]) * math.pi / 180
        
        a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance = R * c
        
        # Estimate duration (assume 30 km/h average)
        duration = distance / 8.33  # m/s
        
        route = {
            'summary': 'Direct Route (Mock)',
            'legs': [{
                'distance': {'text': f'{distance/1000:.1f} km', 'value': int(distance)},
                'duration': {'text': f'{int(duration/60)} mins', 'value': int(duration)},
                'start_address': f'{orig[0]}, {orig[1]}',
                'end_address': f'{dest[0]}, {dest[1]}',
                'steps': [{
                    'distance': {'text': f'{distance/1000:.1f} km', 'value': int(distance)},
                    'duration': {'text': f'{int(duration/60)} mins', 'value': int(duration)},
                    'html_instructions': 'Head to destination',
                    'start_location': {'lat': orig[0], 'lng': orig[1]},
                    'end_location': {'lat': dest[0], 'lng': dest[1]},
                    'maneuver': 'straight'
                }]
            }],
            'overview_polyline': {'points': encoded},
            'route_coordinates': [
                {'lat': coord[0], 'lng': coord[1]} for coord in route_coords
            ],
            'warnings': ['Using mock data - OSRM unavailable']
        }
        
        return [route]
    
    async def geocode_address(self, address: str) -> Optional[Dict[str, float]]:
        """
        Geocode address using Nominatim (OpenStreetMap) - FREE!
        No API key needed!
        """
        try:
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': address,
                'format': 'json',
                'limit': 1
            }
            headers = {
                'User-Agent': 'SmartShield/1.0'  # Required by Nominatim
            }
            
            async with httpx.AsyncClient(timeout=5.0, headers=headers) as client:
                response = await client.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                if data:
                    return {
                        'lat': float(data[0]['lat']),
                        'lng': float(data[0]['lon'])
                    }
            
            logger.warning(f"Geocoding failed for: {address}")
            return None
            
        except Exception as e:
            logger.error(f"Geocoding error: {e}")
            return None
    
    async def reverse_geocode(self, lat: float, lng: float) -> Optional[str]:
        """
        Reverse geocode coordinates using Nominatim - FREE!
        """
        try:
            url = "https://nominatim.openstreetmap.org/reverse"
            params = {
                'lat': lat,
                'lon': lng,
                'format': 'json'
            }
            headers = {
                'User-Agent': 'SmartShield/1.0'
            }
            
            async with httpx.AsyncClient(timeout=5.0, headers=headers) as client:
                response = await client.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('display_name', f'{lat}, {lng}')
            
            return f'{lat}, {lng}'
            
        except Exception as e:
            logger.error(f"Reverse geocoding error: {e}")
            return f'{lat}, {lng}'
    
    def calculate_straight_distance(self, coord1: Coordinate, coord2: Coordinate) -> float:
        """Calculate straight-line distance in meters (Haversine formula)"""
        import math
        
        R = 6371000  # Earth radius in meters
        phi1 = coord1.latitude * math.pi / 180
        phi2 = coord2.latitude * math.pi / 180
        dphi = (coord2.latitude - coord1.latitude) * math.pi / 180
        dlambda = (coord2.longitude - coord1.longitude) * math.pi / 180
        
        a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    async def get_all_directions(self, origin: any, destination: any, **kwargs) -> List[Dict]:
        """Get all route variations (for RouteOptimizer compatibility)"""
        return await self.get_directions(origin, destination, alternatives=True, **kwargs)
    
    def geocode(self, address: str) -> Optional[Coordinate]:
        """Geocode an address (for compatibility)"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We are in an active loop, we can't block here.
                # In a real app we'd use nest_asyncio, but for now we fallback.
                return None
            result = loop.run_until_complete(self.geocode_address(address))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.geocode_address(address))
            loop.close()
            
        if result:
            return Coordinate(latitude=result['lat'], longitude=result['lng'])
        return None
