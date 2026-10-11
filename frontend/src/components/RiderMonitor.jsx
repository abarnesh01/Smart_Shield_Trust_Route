import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
    FiRefreshCw, FiMapPin, FiUser, FiPhone, FiPackage,
    FiActivity, FiWifi, FiWifiOff, FiBattery, FiNavigation,
    FiAlertTriangle, FiCheckCircle, FiSearch, FiFilter,
    FiTruck, FiClock, FiStar, FiArrowUp, FiChevronDown, FiShield
} from 'react-icons/fi';
import SafetyHeatmap from './SafetyHeatmap';
import { api } from '../services/api';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';

// ── Fix Leaflet marker icons ──────────────────────────────────
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
    iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

// Custom rider marker icons
const createRiderIcon = (isOnline, role) => {
    const color = isOnline ? '#10b981' : '#94a3b8';
    const bg = isOnline ? '#d1fae5' : '#f1f5f9';
    const emoji = role === 'driver' ? '🚗' : '🛵';
    return L.divIcon({
        className: '',
        html: `<div style="
            width:36px;height:36px;border-radius:50%;
            background:${bg};border:2.5px solid ${color};
            display:flex;align-items:center;justify-content:center;
            font-size:18px;box-shadow:0 2px 8px ${color}55;
            animation:${isOnline ? 'pulse-ring 2s infinite' : 'none'};
        ">${emoji}</div>
        <style>@keyframes pulse-ring{0%,100%{box-shadow:0 2px 8px ${color}55}50%{box-shadow:0 0 0 6px ${color}33}}</style>`,
        iconSize: [36, 36],
        iconAnchor: [18, 18],
    });
};

// ── Fleet overview map component ──────────────────────────────
const FleetOverviewMap = ({ riders, onSelectRider, selectedRiderId }) => {
    const onlineRiders = riders.filter(r => r.last_location);

    return (
        <div className="h-full w-full rounded-3xl overflow-hidden">
            <MapContainer
                center={[12.9716, 80.2452]}
                zoom={11}
                className="h-full w-full"
                zoomControl={false}
            >
                <TileLayer
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                />
                <SafetyHeatmap show={true} />
                {onlineRiders.map(rider => {
                    const lat = rider.last_location?.latitude || rider.last_location?.lat;
                    const lng = rider.last_location?.longitude || rider.last_location?.lng;
                    if (!lat || !lng) return null;
                    return (
                        <Marker
                            key={rider.rider_id}
                            position={[lat, lng]}
                            icon={createRiderIcon(rider.is_online, rider.role)}
                            eventHandlers={{ click: () => onSelectRider(rider) }}
                        >
                            <Popup className="custom-popup">
                                <div className="p-2 min-w-[180px]">
                                    <div className="flex items-center gap-2 mb-2">
                                        <div className={`w-2 h-2 rounded-full ${rider.is_online ? 'bg-emerald-500' : 'bg-slate-400'}`} />
                                        <p className="font-bold text-slate-900 text-sm">{rider.name}</p>
                                    </div>
                                    <p className="text-xs text-slate-500 capitalize">{rider.role}</p>
                                    {rider.active_delivery && (
                                        <div className="mt-2 pt-2 border-t border-slate-100">
                                            <p className="text-[10px] font-bold text-indigo-600 uppercase">Active Delivery</p>
                                            <p className="text-xs text-slate-700 font-semibold mt-0.5">{rider.active_delivery.order_id}</p>
                                            <p className="text-[10px] text-slate-500 mt-0.5 capitalize">{rider.active_delivery.status?.replace('_', ' ')}</p>
                                        </div>
                                    )}
                                    {rider.speed_kmh != null && (
                                        <p className="text-[10px] text-slate-400 mt-1">⚡ {Math.round(rider.speed_kmh)} km/h</p>
                                    )}
                                </div>
                            </Popup>
                        </Marker>
                    );
                })}
            </MapContainer>
        </div>
    );
};

// ── Status badge ──────────────────────────────────────────────
const DeliveryStatusBadge = ({ status }) => {
    const config = {
        in_transit: { bg: 'bg-indigo-50', text: 'text-indigo-700', border: 'border-indigo-200', label: 'In Transit' },
        picked_up: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200', label: 'Picked Up' },
        assigned: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200', label: 'Assigned' },
        pending: { bg: 'bg-slate-50', text: 'text-slate-500', border: 'border-slate-200', label: 'Pending' },
        delivered: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200', label: 'Delivered' },
    };
    const c = config[status] || config.pending;
    return (
        <span className={`px-2.5 py-1 rounded-full text-[10px] font-black uppercase tracking-wider border ${c.bg} ${c.text} ${c.border}`}>
            {c.label}
        </span>
    );
};

// ── Battery indicator ─────────────────────────────────────────
const BatteryBar = ({ level }) => {
    if (level == null) return <span className="text-slate-300 text-xs">—</span>;
    const color = level > 60 ? '#10b981' : level > 30 ? '#f59e0b' : '#ef4444';
    return (
        <div className="flex items-center gap-1.5">
            <div className="flex items-center gap-0.5">
                {[...Array(4)].map((_, i) => (
                    <div
                        key={i}
                        className="w-2 h-3 rounded-sm transition-all"
                        style={{ background: i < Math.ceil(level / 25) ? color : '#e2e8f0' }}
                    />
                ))}
            </div>
            <span className="text-xs font-bold" style={{ color }}>{level}%</span>
        </div>
    );
};

// ── Time since last update ────────────────────────────────────
const TimeSince = ({ iso }) => {
    if (!iso) return <span className="text-slate-300 text-xs">Never</span>;
    const diff = Math.floor((Date.now() - new Date(iso)) / 1000);
    let label;
    if (diff < 60) label = `${diff}s ago`;
    else if (diff < 3600) label = `${Math.floor(diff / 60)}m ago`;
    else label = `${Math.floor(diff / 3600)}h ago`;
    const fresh = diff < 60;
    return (
        <span className={`text-xs font-bold ${fresh ? 'text-emerald-600' : diff < 300 ? 'text-amber-600' : 'text-slate-400'}`}>
            {label}
        </span>
    );
};

// ── Main Component ────────────────────────────────────────────
const RiderMonitor = () => {
    const [riders, setRiders] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [search, setSearch] = useState('');
    const [filter, setFilter] = useState('all'); // all, online, offline, active
    const [selectedRider, setSelectedRider] = useState(null);
    const [view, setView] = useState('split'); // split, map, table, performance
    const [sortBy, setSortBy] = useState('online');
    const [performanceData, setPerformanceData] = useState([]);
    const refreshRef = useRef(null);

    const fetchRiders = useCallback(async () => {
        try {
            const data = await api.getRidersStatus();
            setRiders(Array.isArray(data) ? data : []);
            setError('');
        } catch (e) {
            setError('Failed to load rider data: ' + (e.message || 'Unknown error'));
        } finally {
            setLoading(false);
        }
    }, []);

    const fetchPerformance = useCallback(async () => {
        try {
            const data = await api.getRiderPerformance();
            setPerformanceData(data);
        } catch (e) {
            console.error("Perf fetch error", e);
        }
    }, []);

    useEffect(() => {
        fetchRiders();
        if (view === 'performance') fetchPerformance();
        // Poll every 15 seconds for live updates
        refreshRef.current = setInterval(fetchRiders, 15000);
        return () => clearInterval(refreshRef.current);
    }, [fetchRiders, fetchPerformance, view]);

    const filtered = riders.filter(r => {
        if (filter === 'online' && !r.is_online) return false;
        if (filter === 'offline' && r.is_online) return false;
        if (filter === 'active' && !r.active_delivery) return false;
        if (search) {
            const q = search.toLowerCase();
            return (
                r.name?.toLowerCase().includes(q) ||
                r.email?.toLowerCase().includes(q) ||
                r.phone?.toLowerCase().includes(q) ||
                r.active_delivery?.order_id?.toLowerCase().includes(q)
            );
        }
        return true;
    });

    const onlineCount = riders.filter(r => r.is_online).length;
    const activeCount = riders.filter(r => r.active_delivery).length;

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center h-96">
                <div className="w-12 h-12 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mb-4" />
                <p className="text-slate-400 font-bold">Loading rider fleet data...</p>
            </div>
        );
    }

    return (
        <div className="space-y-6 h-full flex flex-col">
            {/* Header */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shrink-0">
                <div>
                    <h2 className="text-2xl font-black text-slate-900">Rider Workability Monitor</h2>
                    <p className="text-slate-500 text-sm mt-1 flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse inline-block" />
                        Live fleet tracking — auto refreshes every 15s
                    </p>
                </div>
                <div className="flex gap-2">
                    {/* View toggle */}
                    <div className="flex bg-slate-100 rounded-2xl p-1 gap-1">
                        {[
                            { id: 'split', label: 'Split' },
                            { id: 'map', label: 'Map' },
                            { id: 'table', label: 'Table' },
                            { id: 'performance', label: 'Performance' },
                        ].map(v => (
                            <button
                                key={v.id}
                                onClick={() => setView(v.id)}
                                className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${view === v.id ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
                            >
                                {v.label}
                            </button>
                        ))}
                    </div>
                    <button
                        onClick={() => { setLoading(true); fetchRiders(); }}
                        className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-xl text-sm font-bold text-slate-600 hover:bg-slate-50 transition-all shadow-sm"
                    >
                        <FiRefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
                    </button>
                </div>
            </div>

            {/* KPI strip */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 shrink-0">
                {[
                    { label: 'Total Riders', value: riders.length, icon: FiUser, color: 'indigo', onClick: () => setFilter('all') },
                    { label: 'Online Now', value: onlineCount, icon: FiWifi, color: 'emerald', onClick: () => setFilter('online') },
                    { label: 'Offline', value: riders.length - onlineCount, icon: FiWifiOff, color: 'slate', onClick: () => setFilter('offline') },
                    { label: 'Active Delivery', value: activeCount, icon: FiPackage, color: 'amber', onClick: () => setFilter('active') },
                ].map(kpi => (
                    <button
                        key={kpi.label}
                        onClick={kpi.onClick}
                        className={`bg-white p-5 rounded-3xl border-2 transition-all text-left hover:shadow-md ${filter === (kpi.label === 'Total Riders' ? 'all' : kpi.label === 'Online Now' ? 'online' : kpi.label === 'Offline' ? 'offline' : 'active')
                            ? 'border-indigo-300 shadow-lg shadow-indigo-100'
                            : 'border-slate-200'
                            }`}
                    >
                        <div className={`w-10 h-10 rounded-2xl flex items-center justify-center mb-3 bg-${kpi.color}-50 text-${kpi.color}-600`}>
                            <kpi.icon size={20} />
                        </div>
                        <p className="text-3xl font-black text-slate-900">{kpi.value}</p>
                        <p className="text-[11px] text-slate-400 font-bold uppercase tracking-widest mt-1">{kpi.label}</p>
                    </button>
                ))}
            </div>

            {/* Error */}
            {error && (
                <div className="p-4 bg-rose-50 border border-rose-200 rounded-2xl text-rose-700 text-sm font-medium flex items-center gap-2">
                    <FiAlertTriangle /> {error}
                </div>
            )}

            {/* Search + Filter bar */}
            <div className="flex flex-wrap gap-3 shrink-0">
                <div className="relative flex-1 min-w-[200px]">
                    <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14} />
                    <input
                        type="text"
                        placeholder="Search by name, phone, or order ID..."
                        value={search}
                        onChange={e => setSearch(e.target.value)}
                        className="w-full pl-9 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:border-indigo-400 shadow-sm"
                    />
                </div>
                <select
                    value={sortBy}
                    onChange={e => setSortBy(e.target.value)}
                    className="px-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm font-semibold text-slate-700 focus:outline-none shadow-sm"
                >
                    <option value="online">Sort: Online First</option>
                    <option value="name">Sort: Name</option>
                    <option value="delivery">Sort: Has Delivery</option>
                    <option value="battery">Sort: Battery Low</option>
                    <option value="speed">Sort: Fastest</option>
                </select>
            </div>

            {/* Performance view */}
            {view === 'performance' && (
                <div className="flex-1 overflow-y-auto bg-white rounded-3xl border border-slate-200 shadow-sm p-8">
                    <div className="flex items-center justify-between mb-8">
                        <h3 className="text-xl font-black text-slate-900">Worker Efficiency & Safety Ranking</h3>
                        <button
                            onClick={fetchPerformance}
                            className="text-indigo-600 text-xs font-bold hover:underline"
                        >
                            Refresh Rankings
                        </button>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full text-left">
                            <thead>
                                <tr className="border-b border-slate-100 pb-4 text-[10px] font-black text-slate-400 uppercase tracking-widest">
                                    <th className="pb-4">Rider</th>
                                    <th className="pb-4">Total Deliveries</th>
                                    <th className="pb-4">Avg Safety</th>
                                    <th className="pb-4">Avg Time</th>
                                    <th className="pb-4">Rating</th>
                                    <th className="pb-4">Operational Score</th>
                                </tr>
                            </thead>
                            <tbody>
                                {performanceData.sort((a, b) => b.total_deliveries - a.total_deliveries).map((p, idx) => (
                                    <tr key={p.rider_id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50/50 transition-colors">
                                        <td className="py-5">
                                            <div className="flex items-center gap-3">
                                                <span className="text-xs font-black text-slate-300 w-4">#{idx + 1}</span>
                                                <div className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-xs shrink-0">
                                                    {p.name[0].toUpperCase()}
                                                </div>
                                                <p className="font-bold text-slate-900 text-sm">{p.name}</p>
                                            </div>
                                        </td>
                                        <td className="py-5">
                                            <p className="text-sm font-black text-slate-700">{p.total_deliveries}</p>
                                        </td>
                                        <td className="py-5">
                                            <div className="flex items-center gap-2">
                                                <div className="flex-1 bg-slate-100 rounded-full h-1.5 w-20 overflow-hidden">
                                                    <div
                                                        className="h-full bg-emerald-500 rounded-full"
                                                        style={{ width: `${p.avg_safety_score}%` }}
                                                    />
                                                </div>
                                                <span className="text-xs font-bold text-emerald-600 font-mono">{p.avg_safety_score}%</span>
                                            </div>
                                        </td>
                                        <td className="py-5">
                                            <p className="text-sm font-bold text-slate-600">{p.avg_delivery_time} min</p>
                                        </td>
                                        <td className="py-5">
                                            <div className="flex items-center gap-1 text-amber-400">
                                                <FiStar size={14} fill="currentColor" />
                                                <span className="text-sm font-black text-slate-900">{p.rating.toFixed(1)}</span>
                                            </div>
                                        </td>
                                        <td className="py-5">
                                            <span className={`px-2 py-1 rounded-lg text-[10px] font-black uppercase ${p.total_deliveries > 20 ? 'bg-indigo-50 text-indigo-600' : 'bg-slate-50 text-slate-500'
                                                }`}>
                                                {p.total_deliveries > 20 ? 'Elite' : p.total_deliveries > 10 ? 'Pro' : 'Standard'}
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* Main content (split/map/table) */}
            {view !== 'performance' && (
                <div className="flex-1 min-h-0 flex gap-6">
                    {/* Map section */}
                    {(view === 'split' || view === 'map') && (
                        <div className={`${view === 'split' ? 'w-1/2' : 'flex-1'} rounded-3xl overflow-hidden border border-slate-200 shadow-sm bg-white relative`} style={{ minHeight: 400 }}>
                            <div className="absolute top-4 left-4 z-10">
                                <div className="bg-white/90 backdrop-blur-md px-3 py-2 rounded-2xl border border-slate-200 shadow-sm flex items-center gap-2">
                                    <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                                    <span className="text-[10px] font-black text-slate-600 uppercase tracking-widest">Live Fleet Map</span>
                                </div>
                            </div>
                            <FleetOverviewMap
                                riders={filtered}
                                onSelectRider={setSelectedRider}
                                selectedRiderId={selectedRider?.rider_id}
                            />
                        </div>
                    )}

                    {/* Table/List section */}
                    {(view === 'split' || view === 'table') && (
                        <div className={`${view === 'split' ? 'w-1/2' : 'flex-1'} flex flex-col gap-3 overflow-y-auto pr-1`}>
                            {filtered.length === 0 ? (
                                <div className="flex flex-col items-center justify-center py-20 bg-white rounded-3xl border border-slate-200 border-dashed">
                                    <FiUser size={40} className="text-slate-200 mb-4" />
                                    <p className="font-bold text-slate-400">No riders found</p>
                                </div>
                            ) : (
                                filtered
                                    .slice()
                                    .sort((a, b) => {
                                        if (sortBy === 'online') return (b.is_online ? 1 : 0) - (a.is_online ? 1 : 0);
                                        if (sortBy === 'name') return (a.name || '').localeCompare(b.name || '');
                                        if (sortBy === 'delivery') return (b.active_delivery ? 1 : 0) - (a.active_delivery ? 1 : 0);
                                        if (sortBy === 'battery') return (a.battery_level || 100) - (b.battery_level || 100);
                                        if (sortBy === 'speed') return (b.speed_kmh || 0) - (a.speed_kmh || 0);
                                        return 0;
                                    })
                                    .map(rider => (
                                        <RiderCard
                                            key={rider.rider_id}
                                            rider={rider}
                                            isSelected={selectedRider?.rider_id === rider.rider_id}
                                            onClick={() => setSelectedRider(rider === selectedRider ? null : rider)}
                                        />
                                    ))
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

// ── Individual Rider Card ─────────────────────────────────────
const RiderCard = ({ rider, isSelected, onClick }) => {
    const [expanded, setExpanded] = useState(false);
    const hasDelivery = !!rider.active_delivery;
    const lat = rider.last_location?.latitude || rider.last_location?.lat;
    const lng = rider.last_location?.longitude || rider.last_location?.lng;

    return (
        <div
            className={`bg-white rounded-3xl border-2 transition-all cursor-pointer shadow-sm hover:shadow-md ${isSelected ? 'border-indigo-400 shadow-lg shadow-indigo-100' : 'border-slate-200'
                }`}
            onClick={onClick}
        >
            {/* Main row */}
            <div className="p-4 flex items-center gap-3">
                {/* Avatar + online dot */}
                <div className="relative shrink-0">
                    <div className={`w-12 h-12 rounded-2xl flex items-center justify-center font-black text-lg border-2 ${rider.role === 'driver'
                        ? 'bg-blue-50 text-blue-700 border-blue-200'
                        : 'bg-indigo-50 text-indigo-700 border-indigo-200'
                        }`}>
                        {(rider.name || 'R')[0].toUpperCase()}
                    </div>
                    <div className={`absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 rounded-full border-2 border-white ${rider.is_online ? 'bg-emerald-500' : 'bg-slate-300'
                        }`} />
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                        <p className="font-black text-slate-900 text-sm truncate">{rider.name}</p>
                        <span className={`text-[9px] font-black uppercase px-1.5 py-0.5 rounded-full ${rider.role === 'driver' ? 'bg-blue-100 text-blue-700' : 'bg-indigo-100 text-indigo-700'
                            }`}>
                            {rider.role}
                        </span>
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                        {rider.is_online
                            ? <span className="text-[10px] font-bold text-emerald-600 flex items-center gap-1"><FiWifi size={10} /> Online</span>
                            : <span className="text-[10px] font-bold text-slate-400 flex items-center gap-1"><FiWifiOff size={10} /> Offline</span>
                        }
                        {rider.phone && <span className="text-[10px] text-slate-400">{rider.phone}</span>}
                        <TimeSince iso={rider.last_seen} />
                    </div>
                </div>

                {/* Metrics */}
                <div className="shrink-0 flex flex-col items-end gap-1.5">
                    <BatteryBar level={rider.battery_level} />
                    {rider.speed_kmh != null && (
                        <span className="text-[10px] font-bold text-slate-500 flex items-center gap-1">
                            <FiNavigation size={10} /> {Math.round(rider.speed_kmh)} km/h
                        </span>
                    )}
                    {hasDelivery && <DeliveryStatusBadge status={rider.active_delivery.status} />}
                    {!hasDelivery && rider.is_online && (
                        <span className="text-[10px] font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-100">Available</span>
                    )}
                </div>

                {/* Expand toggle */}
                <button
                    onClick={e => { e.stopPropagation(); setExpanded(v => !v); }}
                    className="ml-1 p-1 text-slate-300 hover:text-slate-600 transition-colors"
                >
                    <FiChevronDown size={16} className={`transition-transform ${expanded ? 'rotate-180' : ''}`} />
                </button>
            </div>

            {/* Expanded delivery details */}
            {expanded && (
                <div className="px-5 pb-5 border-t border-slate-100 mt-0 pt-4 space-y-4">
                    {/* Location */}
                    {lat && lng && (
                        <div className="flex items-start gap-3 p-3 bg-slate-50 rounded-2xl">
                            <FiMapPin size={16} className="text-indigo-500 mt-0.5 shrink-0" />
                            <div>
                                <p className="text-[10px] text-slate-400 font-bold uppercase">Last Known Location</p>
                                <p className="text-xs font-bold text-slate-700 mt-0.5">{lat?.toFixed(5)}, {lng?.toFixed(5)}</p>
                                <p className="text-[10px] text-slate-400 mt-0.5">
                                    {rider.heading != null && `Heading: ${Math.round(rider.heading)}°`}
                                    {rider.speed_kmh != null && ` · ${Math.round(rider.speed_kmh)} km/h`}
                                </p>
                                {rider.h3_index && (
                                    <div className="mt-2 flex items-center gap-1.5">
                                        <span className="text-[9px] bg-amber-100 text-amber-700 font-black px-1.5 py-0.5 rounded-md uppercase tracking-tighter">H3-ID</span>
                                        <code className="text-[10px] font-mono text-slate-500 bg-slate-100 px-1 rounded">{rider.h3_index}</code>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    {/* Active delivery */}
                    {hasDelivery ? (
                        <div className="space-y-3">
                            <div className="flex items-center justify-between">
                                <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest flex items-center gap-1">
                                    <FiPackage size={12} /> Active Delivery
                                </p>
                                <DeliveryStatusBadge status={rider.active_delivery.status} />
                            </div>

                            <div className="grid grid-cols-2 gap-3">
                                <div className="p-3 bg-indigo-50 rounded-2xl border border-indigo-100">
                                    <p className="text-[10px] text-indigo-400 font-bold uppercase">Order ID</p>
                                    <p className="text-xs font-black text-indigo-900 font-mono mt-0.5">{rider.active_delivery.order_id || '—'}</p>
                                </div>
                                <div className="p-3 bg-slate-50 rounded-2xl border border-slate-100">
                                    <p className="text-[10px] text-slate-400 font-bold uppercase">Safety Score</p>
                                    <p className="text-xs font-black text-slate-900 mt-0.5">
                                        {rider.active_delivery.safety_score ? `${Math.round(rider.active_delivery.safety_score)}%` : '—'}
                                    </p>
                                </div>
                            </div>

                            {/* Pickup */}
                            {rider.active_delivery.pickup_location?.address && (
                                <div className="flex items-start gap-3 p-3 bg-emerald-50 rounded-2xl border border-emerald-100">
                                    <div className="w-5 h-5 rounded-lg bg-emerald-500 text-white flex items-center justify-center shrink-0 mt-0.5 text-[10px] font-black">P</div>
                                    <div>
                                        <p className="text-[10px] text-emerald-600 font-bold uppercase">Pickup</p>
                                        <p className="text-xs font-semibold text-slate-700 mt-0.5">{rider.active_delivery.pickup_location.address}</p>
                                    </div>
                                </div>
                            )}

                            {/* Dropoff */}
                            {rider.active_delivery.dropoff_location?.address && (
                                <div className="flex items-start gap-3 p-3 bg-rose-50 rounded-2xl border border-rose-100">
                                    <div className="w-5 h-5 rounded-lg bg-rose-500 text-white flex items-center justify-center shrink-0 mt-0.5 text-[10px] font-black">D</div>
                                    <div>
                                        <p className="text-[10px] text-rose-600 font-bold uppercase">Delivery Destination</p>
                                        <p className="text-xs font-semibold text-slate-700 mt-0.5">{rider.active_delivery.dropoff_location.address}</p>
                                        {rider.active_delivery.estimated_distance && (
                                            <p className="text-[10px] text-slate-400 mt-0.5">
                                                ~{parseFloat(rider.active_delivery.estimated_distance).toFixed(1)} km
                                                {rider.active_delivery.estimated_duration &&
                                                    ` · ~${Math.round(parseFloat(rider.active_delivery.estimated_duration))} min`
                                                }
                                            </p>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="flex items-center gap-3 p-3 bg-emerald-50/50 rounded-2xl border border-emerald-100">
                            <FiCheckCircle size={16} className="text-emerald-500" />
                            <div>
                                <p className="text-xs font-bold text-slate-700">No active delivery</p>
                                <p className="text-[10px] text-slate-400">
                                    Deliveries today: {rider.deliveries_today || 0}
                                </p>
                            </div>
                        </div>
                    )}
                </div>
            )
            }
        </div >
    );
};

export default RiderMonitor;
