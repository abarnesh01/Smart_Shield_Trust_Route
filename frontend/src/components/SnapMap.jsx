import React, { useState, useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, CircleMarker, useMap } from 'react-leaflet';
import { FiMapPin, FiNavigation, FiShield } from 'react-icons/fi';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import useLocation from '../hooks/useLocation';

// Fix Leaflet default icon issue
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

// Component to fit map bounds
function FitBounds({ bounds }) {
  const map = useMap();
  useEffect(() => {
    if (bounds && bounds.length > 0) {
      map.fitBounds(bounds, { padding: [50, 50] });
    }
  }, [bounds, map]);
  return null;
}

// Component to update map view
const MapUpdater = ({ center }) => {
  const map = useMap();
  useEffect(() => {
    if (center) {
      map.setView(center, map.getZoom());
    }
  }, [center, map]);
  return null;
};

const SnapMap = () => {
  const { location, loading, error: locationError } = useLocation();
  const [selectedRoute, setSelectedRoute] = useState(null);
  const [showTraffic, setShowTraffic] = useState(true);
  const [showSafety, setShowSafety] = useState(true);
  const [mapStyle, setMapStyle] = useState('standard'); // standard, satellite, dark

  // New York as fallback
  const fallbackLocation = { latitude: 40.7128, longitude: -74.0060 };
  const baseLat = location?.latitude || fallbackLocation.latitude;
  const baseLon = location?.longitude || fallbackLocation.longitude;

  // Mock route data with traffic and safety info relative to base location
  const routes = useMemo(() => [
    {
      id: 1,
      name: 'Route #1247',
      status: 'active',
      safety: 92,
      stops: 5,
      distance: '12.5 km',
      time: '28 min',
      coordinates: [
        { lat: baseLat, lng: baseLon, name: 'Start (My Location)', traffic: 'low', safety: 95 },
        { lat: baseLat + 0.005, lng: baseLon + 0.006, name: 'Stop 1', traffic: 'medium', safety: 90 },
        { lat: baseLat + 0.012, lng: baseLon + 0.003, name: 'Stop 2', traffic: 'high', safety: 85 },
        { lat: baseLat + 0.015, lng: baseLon - 0.005, name: 'Stop 3', traffic: 'low', safety: 95 },
        { lat: baseLat + 0.008, lng: baseLon - 0.012, name: 'Stop 4', traffic: 'medium', safety: 88 },
        { lat: baseLat - 0.002, lng: baseLon - 0.008, name: 'End', traffic: 'low', safety: 92 },
      ],
    },
    {
      id: 2,
      name: 'Route #1246',
      status: 'completed',
      safety: 85,
      stops: 4,
      distance: '8.3 km',
      time: '22 min',
      coordinates: [
        { lat: baseLat + 0.01, lng: baseLon + 0.015, name: 'Start', traffic: 'low', safety: 88 },
        { lat: baseLat + 0.015, lng: baseLon + 0.01, name: 'Stop 1', traffic: 'medium', safety: 85 },
        { lat: baseLat + 0.02, lng: baseLon + 0.005, name: 'Stop 2', traffic: 'high', safety: 80 },
        { lat: baseLat + 0.025, lng: baseLon, name: 'End', traffic: 'low', safety: 87 },
      ],
    },
  ], [baseLat, baseLon]);

  // Get traffic color
  const getTrafficColor = (traffic) => {
    switch (traffic) {
      case 'low': return '#22c55e'; // green
      case 'medium': return '#eab308'; // yellow
      case 'high': return '#ef4444'; // red
      default: return '#6b7280'; // gray
    }
  };

  // Get traffic width
  const getTrafficWidth = (traffic) => {
    switch (traffic) {
      case 'low': return 4;
      case 'medium': return 6;
      case 'high': return 8;
      default: return 4;
    }
  };

  // Get safety color
  const getSafetyColor = (safety) => {
    if (safety >= 90) return '#22c55e'; // green
    if (safety >= 75) return '#eab308'; // yellow
    if (safety >= 60) return '#f97316'; // orange
    return '#ef4444'; // red
  };

  // Create route segments with traffic
  const createRouteSegments = (route) => {
    const segments = [];
    for (let i = 0; i < route.coordinates.length - 1; i++) {
      const start = route.coordinates[i];
      const end = route.coordinates[i + 1];
      segments.push({
        from: [start.lat, start.lng],
        to: [end.lat, end.lng],
        traffic: end.traffic,
        safety: (start.safety + end.safety) / 2,
      });
    }
    return segments;
  };

  // Calculate bounds
  const calculateBounds = (route) => {
    if (!route || !route.coordinates.length) return null;
    return route.coordinates.map(coord => [coord.lat, coord.lng]);
  };

  const currentRoute = selectedRoute || routes[0];
  const segments = createRouteSegments(currentRoute);

  if (loading) {
    return (
      <div className="w-full h-screen bg-gray-900 flex items-center justify-center">
        <div className="flex flex-col items-center">
          <div className="w-16 h-16 border-4 border-primary-500 border-t-transparent rounded-full animate-spin mb-4"></div>
          <p className="text-white text-lg">Locating and loading Map...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative w-full h-screen bg-gray-900">
      {/* Snapchat-like Top Bar */}
      <div className="absolute top-0 left-0 right-0 z-[1000] bg-gradient-to-b from-black/80 to-transparent p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="bg-primary-500 p-2 rounded-full">
              <FiMapPin className="text-white text-xl" />
            </div>
            <div>
              <h1 className="text-white text-xl font-bold">Smart Shield Map</h1>
              <div className="flex items-center space-x-2">
                <p className="text-gray-300 text-sm">{currentRoute.name}</p>
                {location && (
                  <span className="text-[10px] bg-green-500/20 text-green-400 px-1.5 py-0.5 rounded border border-green-500/30 flex items-center">
                    <span className="w-1.5 h-1.5 bg-green-500 rounded-full mr-1 animate-pulse"></span>
                    Live Location
                  </span>
                )}
              </div>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setShowTraffic(!showTraffic)}
              className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${showTraffic ? 'bg-primary-500 text-white' : 'bg-white/20 text-gray-300'
                }`}
            >
              Traffic
            </button>
            <button
              onClick={() => setShowSafety(!showSafety)}
              className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${showSafety ? 'bg-success-500 text-white' : 'bg-white/20 text-gray-300'
                }`}
            >
              Safety
            </button>
          </div>
        </div>
      </div>

      {/* Map Container */}
      <MapContainer
        center={[baseLat, baseLon]}
        zoom={14}
        style={{ height: '100vh', width: '100%', zIndex: 0 }}
        zoomControl={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <MapUpdater center={[baseLat, baseLon]} />

        {/* Fit bounds to route */}
        <FitBounds bounds={calculateBounds(currentRoute)} />

        {/* Route segments with traffic colors */}
        {showTraffic && segments.map((segment, index) => (
          <Polyline
            key={index}
            positions={[segment.from, segment.to]}
            pathOptions={{
              color: getTrafficColor(segment.traffic),
              weight: getTrafficWidth(segment.traffic),
              opacity: 0.8,
              dashArray: segment.traffic === 'high' ? '10, 10' : null,
            }}
          />
        ))}

        {/* Safety overlay circles */}
        {showSafety && currentRoute.coordinates.map((coord, index) => (
          <CircleMarker
            key={index}
            center={[coord.lat, coord.lng]}
            radius={8}
            pathOptions={{
              color: getSafetyColor(coord.safety),
              fillColor: getSafetyColor(coord.safety),
              fillOpacity: 0.4,
              weight: 2,
            }}
          >
            <Popup>
              <div className="p-2">
                <h3 className="font-bold text-sm">{coord.name}</h3>
                <p className="text-xs text-gray-600">Safety: {coord.safety}%</p>
                <p className="text-xs text-gray-600">
                  Traffic: <span className="font-medium">{coord.traffic}</span>
                </p>
              </div>
            </Popup>
          </CircleMarker>
        ))}

        {/* Route markers */}
        {currentRoute.coordinates.map((coord, index) => (
          <Marker
            key={index}
            position={[coord.lat, coord.lng]}
            icon={
              index === 0 || index === currentRoute.coordinates.length - 1
                ? new L.Icon({
                  iconUrl: index === 0
                    ? 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-green.png'
                    : 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png',
                  iconSize: [25, 41],
                  iconAnchor: [12, 41],
                  popupAnchor: [1, -34],
                })
                : new L.Icon({
                  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-blue.png',
                  iconSize: [25, 41],
                  iconAnchor: [12, 41],
                  popupAnchor: [1, -34],
                })
            }
          >
            <Popup>
              <div className="p-2 min-w-[200px]">
                <h3 className="font-bold text-sm mb-2">{coord.name}</h3>
                <div className="space-y-1 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-600">Safety:</span>
                    <span className="font-medium" style={{ color: getSafetyColor(coord.safety) }}>
                      {coord.safety}%
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-600">Traffic:</span>
                    <span
                      className="font-medium px-2 py-0.5 rounded"
                      style={{
                        backgroundColor: getTrafficColor(coord.traffic) + '20',
                        color: getTrafficColor(coord.traffic),
                      }}
                    >
                      {coord.traffic}
                    </span>
                  </div>
                </div>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>

      {/* Bottom Panel - Route Info */}
      <div className="absolute bottom-0 left-0 right-0 z-[1000] bg-gradient-to-t from-black/90 via-black/80 to-transparent p-4">
        <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-4 border border-white/20">
          {/* Route Selector */}
          <div className="flex items-center space-x-2 mb-4 overflow-x-auto pb-2">
            {routes.map((route) => (
              <button
                key={route.id}
                onClick={() => setSelectedRoute(route)}
                className={`px-4 py-2 rounded-xl text-sm font-medium whitespace-nowrap transition-all ${(selectedRoute?.id || routes[0].id) === route.id
                    ? 'bg-primary-500 text-white'
                    : 'bg-white/20 text-gray-300 hover:bg-white/30'
                  }`}
              >
                {route.name}
              </button>
            ))}
          </div>

          {/* Route Stats */}
          <div className="grid grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-white">{currentRoute.safety}</div>
              <div className="text-xs text-gray-300">Safety</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-white">{currentRoute.stops}</div>
              <div className="text-xs text-gray-300">Stops</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-white">{currentRoute.distance}</div>
              <div className="text-xs text-gray-300">Distance</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-white">{currentRoute.time}</div>
              <div className="text-xs text-gray-300">Time</div>
            </div>
          </div>

          {/* Legend */}
          <div className="mt-4 pt-4 border-t border-white/20">
            <div className="flex items-center justify-around text-xs">
              <div className="flex items-center space-x-2">
                <div className="w-4 h-1 bg-green-500 rounded"></div>
                <span className="text-gray-300">Low Traffic</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-4 h-1 bg-yellow-500 rounded"></div>
                <span className="text-gray-300">Medium</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-4 h-1 bg-red-500 rounded"></div>
                <span className="text-gray-300">High Traffic</span>
              </div>
              <div className="flex items-center space-x-2">
                <FiShield className="text-green-500" />
                <span className="text-gray-300">Safe Zone</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Floating Action Button - Map Style */}
      <div className="absolute bottom-24 right-4 z-[1000]">
        <div className="flex flex-col space-y-2">
          <button
            onClick={() => setMapStyle(mapStyle === 'standard' ? 'dark' : 'standard')}
            className="bg-white/90 backdrop-blur-lg p-3 rounded-full shadow-lg hover:bg-white transition-colors"
          >
            <FiNavigation className="text-gray-800" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default SnapMap;

