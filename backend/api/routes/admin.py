from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from database.database import get_db
from database.models import User, Delivery, PanicAlert, DeliveryFeedback, DeliveryStatus, DeliveryRoute, HistoricalDelivery, SafetyScore
from api.deps import get_current_admin, get_current_dispatcher, get_current_active_user
from datetime import datetime, timedelta
import csv
import io
from fastapi.responses import StreamingResponse
from loguru import logger

from api.services.geospatial import geo_service
from api.services.location_cache import location_cache
from api.routes.notifications import manager as notification_manager
from config.config import settings

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/summary")
async def get_system_summary(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_dispatcher)
):
    """Retrieve high-level system statistics for the Admin Dashboard."""
    # Active nodes: users with role 'rider' or 'driver'
    fleet_count = db.query(User).filter(User.role.in_(['rider', 'driver'])).count()
    
    # Active tasks: deliveries not in 'delivered' or 'cancelled' status
    active_deliveries = db.query(Delivery).filter(
        ~Delivery.status.in_(['delivered', 'cancelled'])
    ).count()
    
    # Active alerts: panic alerts with status 'active'
    active_alerts = db.query(PanicAlert).filter(PanicAlert.status == 'active').count()
    
    # Average safety score of all deliveries
    avg_safety = db.query(func.avg(Delivery.safety_score)).scalar() or 94.0
    
    # Mock utilization based on active deliveries vs fleet
    utilization = "0%"
    if fleet_count > 0:
        utilization = f"{min(100, int((active_deliveries / fleet_count) * 100))}%"
    else:
        utilization = "0%"

    # Real-time online count from cache
    online_count = len(await location_cache.get_all_fleet())
    
    # Fallback to DB if cache is empty (likely due to simulation or separate process)
    if online_count == 0:
        cutoff = datetime.utcnow() - timedelta(minutes=15)
        online_count = db.query(DeliveryStatus.rider_id).filter(
            DeliveryStatus.timestamp >= cutoff
        ).distinct().count()

    return {
        "activeDrivers": fleet_count,
        "onlineDrivers": online_count,
        "fleetUtilization": utilization,
        "safetyScore": round(float(avg_safety), 1),
        "activeAlerts": active_alerts,
        "totalTasks": db.query(Delivery).count()
    }

@router.post("/broadcast")
async def broadcast_message(
    payload: dict,
    admin: User = Depends(get_current_admin)
):
    """Broadcast real-time message via WebSocket notification manager."""
    try:
        message = str(payload.get("message", "")).strip() or "System Alert"
        target = str(payload.get("target", "all")).strip()
        
        broadcast_data = {
            "type": "admin_broadcast",
            "message": message,
            "target": target,
            "sender": admin.username,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await notification_manager.broadcast(broadcast_data)
        logger.info(f"Admin '{admin.username}' broadcast message to target '{target}': {message}")
        
        return {
            "status": "success",
            "message": f"Broadcast sent to {target} nodes",
            "broadcast_details": broadcast_data
        }
    except Exception as e:
        logger.error(f"Error executing broadcast: {e}")
        raise HTTPException(status_code=500, detail=f"Broadcast failed: {str(e)}")

@router.get("/analytics-trends")
def get_analytics_trends(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_dispatcher)
):
    """Get database-derived analytics trend aggregates for charts."""
    try:
        labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        
        routes = db.query(DeliveryRoute).all()
        hist = db.query(HistoricalDelivery).all()
        deliveries = db.query(Delivery).all()

        day_times = {i: [] for i in range(7)}
        day_counts = {i: 0 for i in range(7)}

        for r in routes:
            t = r.actual_time or r.predicted_time
            dt_obj = r.created_at or r.delivery_time
            if t and dt_obj:
                w = dt_obj.weekday()
                day_times[w].append(float(t))
                day_counts[w] += 1

        for h in hist:
            t = h.delivery_time_minutes
            dt_obj = h.completed_at or h.created_at
            if t and dt_obj:
                w = dt_obj.weekday()
                day_times[w].append(float(t))
                day_counts[w] += 1

        for d in deliveries:
            t = d.estimated_duration
            dt_obj = d.created_at
            if t and dt_obj:
                w = dt_obj.weekday()
                day_times[w].append(float(t))
                day_counts[w] += 1

        delivery_time_trend = [
            round(sum(day_times[i]) / len(day_times[i]), 1) if day_times[i] else 0.0
            for i in range(7)
        ]

        active_nodes_trend = [day_counts[i] for i in range(7)]

        safety_scores = []
        for r in routes:
            if r.safety_score is not None:
                safety_scores.append(float(r.safety_score))
        for d in deliveries:
            if d.safety_score is not None:
                safety_scores.append(float(d.safety_score))
        scores_table = db.query(SafetyScore.overall_score).all()
        for (s,) in scores_table:
            if s is not None:
                safety_scores.append(float(s))

        high_cnt = sum(1 for s in safety_scores if s >= 70)
        med_cnt = sum(1 for s in safety_scores if 40 <= s < 70)
        low_cnt = sum(1 for s in safety_scores if s < 40)
        safety_dist = [high_cnt, med_cnt, low_cnt]

        fuel_records = []
        for r in routes:
            if r.fuel_score is not None:
                fuel_records.append(float(r.fuel_score))
        for h in hist:
            if h.fuel_consumed is not None:
                fuel_records.append(float(h.fuel_consumed))

        if fuel_records:
            total_f = sum(fuel_records)
            fuel_savings_trend = [
                round(total_f * 0.4, 1),
                round(total_f * 0.3, 1),
                round(total_f * 0.2, 1),
                round(total_f * 0.1, 1)
            ]
        else:
            fuel_savings_trend = [0.0, 0.0, 0.0, 0.0]

        return {
            "labels": labels,
            "deliveryTime": delivery_time_trend,
            "safetyDistribution": safety_dist,
            "fuelSavings": fuel_savings_trend,
            "activeNodes": active_nodes_trend
        }
    except Exception as e:
        logger.error(f"Error calculating analytics trends: {e}")
        return {
            "labels": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "deliveryTime": [0.0] * 7,
            "safetyDistribution": [0, 0, 0],
            "fuelSavings": [0.0] * 4,
            "activeNodes": [0] * 7
        }

@router.get("/fleet-events")
def get_recent_fleet_events(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_dispatcher)
):
    """Retrieve recent activities for the event feed."""
    from database.models import Delivery, PanicAlert
    
    # Get last 5 deliveries and alerts
    deliveries = db.query(Delivery).order_by(Delivery.created_at.desc()).limit(5).all()
    alerts = db.query(PanicAlert).order_by(PanicAlert.created_at.desc()).limit(5).all()
    
    events = []
    for d in deliveries:
        events.append({
            "id": f"del_{d.id}",
            "type": "delivery",
            "title": f"Order #{d.order_id}",
            "description": f"Status updated to {d.status}",
            "time": d.created_at.isoformat() if d.created_at else None,
            "icon": "truck"
        })
    for a in alerts:
        events.append({
            "id": f"alert_{a.id}",
            "type": "alert",
            "title": "SOS Signal",
            "description": f"Panic triggered by Rider ID: {a.rider_id}",
            "time": a.created_at.isoformat() if a.created_at else None,
            "icon": "alert"
        })
    
    # Sort by time
    events.sort(key=lambda x: x['time'] or '', reverse=True)
    return events[:10]

@router.get("/riders-status")
async def get_riders_live_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get all riders/drivers with their live location, active delivery info, 
    and the latest tracking update. Used by Admin Dashboard to monitor workability.
    """
    # Get all rider/driver users
    riders = db.query(User).filter(
        User.role.in_(["rider", "driver"]),
        User.is_active == True
    ).all()

    result = []
    for rider in riders:
        # 1. OPTIMIZATION: Check in-memory cache first (Redis-like O(1) jump)
        # This allows us to see simulated riders who haven't hit the DB yet
        cached = await location_cache.get_by_rider(rider.id)

        # 2. Fall back to DB for history
        latest_track = None
        if not cached:
            latest_track = (
                db.query(DeliveryStatus)
                .filter(DeliveryStatus.rider_id == rider.id)
                .order_by(DeliveryStatus.timestamp.desc())
                .first()
            )

        # 3. Get rider's current active delivery
        active_delivery = (
            db.query(Delivery)
            .filter(
                Delivery.assigned_rider_id == rider.id,
                ~Delivery.status.in_(["delivered", "cancelled", "failed"])
            )
            .order_by(Delivery.created_at.desc())
            .first()
        )

        # Build response entry
        entry = {
            "rider_id": rider.id,
            "name": rider.full_name or rider.username,
            "phone": rider.phone,
            "email": rider.email,
            "role": rider.role,
            "status": rider.status,
            # Location data (prefer cache)
            "last_location": {
                "latitude": cached["latitude"], 
                "longitude": cached["longitude"]
            } if cached else (latest_track.current_location if latest_track else None),
            
            "last_seen": cached["timestamp"] if cached else (latest_track.timestamp.isoformat() if latest_track else None),
            "speed_kmh": cached["speed_kmh"] if cached else (latest_track.speed_kmh if latest_track else None),
            "heading": cached["heading"] if cached else (latest_track.heading if latest_track else None),
            "battery_level": cached["battery_level"] if cached else (latest_track.battery_level if latest_track else None),
            # Delivery data
            "active_delivery": {
                "id": active_delivery.id,
                "order_id": active_delivery.order_id,
                "status": active_delivery.status,
                "dropoff_location": active_delivery.dropoff_location,
                "pickup_location": active_delivery.pickup_location,
                "safety_score": active_delivery.safety_score,
                "estimated_distance": active_delivery.estimated_distance,
                "estimated_duration": active_delivery.estimated_duration,
                "created_at": active_delivery.created_at.isoformat() if active_delivery.created_at else None,
            } if active_delivery else None,
            # Computed fields
            "is_online": cached is not None or (latest_track is not None and (
                datetime.utcnow() - latest_track.timestamp
            ).total_seconds() < 300),  # online if cached OR updated within 5 min
            "deliveries_today": db.query(Delivery).filter(
                Delivery.assigned_rider_id == rider.id,
                Delivery.status == "delivered",
                Delivery.delivered_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            ).count(),
            "h3_index": cached.get("h3_index") if cached else (
                geo_service.get_hex_id(
                    latest_track.current_location.get("latitude"),
                    latest_track.current_location.get("longitude")
                ) if latest_track and latest_track.current_location else None
            )
        }
        result.append(entry)

    # Sort: online first, then by name
    result.sort(key=lambda x: (not x["is_online"], x["name"] or ""))
    return result


@router.get("/rider-performance")
def get_rider_performance_stats(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Get aggregated performance metrics for all riders.
    Includes total deliveries, avg safety score, avg delivery time.
    """
    riders = db.query(User).filter(User.role.in_(["rider", "driver"])).all()
    
    stats = []
    for rider in riders:
        deliveries = db.query(Delivery).filter(
            Delivery.assigned_rider_id == rider.id,
            Delivery.status == "delivered"
        ).all()
        
        total = len(deliveries)
        if total > 0:
            avg_safety = sum((d.safety_score or 0) for d in deliveries) / total
            # Calculate avg duration in minutes
            durations = []
            for d in deliveries:
                if d.delivered_at and d.created_at:
                    durations.append((d.delivered_at - d.created_at).total_seconds() / 60)
            avg_duration = sum(durations) / len(durations) if durations else 0
        else:
            avg_safety = 0
            avg_duration = 0
            
        stats.append({
            "rider_id": rider.id,
            "name": rider.full_name or rider.username,
            "total_deliveries": total,
            "avg_safety_score": round(avg_safety, 1),
            "avg_delivery_time": round(avg_duration, 1),
            "rating": 4.5 + (avg_safety / 200) # Mock rating based on safety
        })
        
    return stats


@router.get("/nearby-riders")
def find_nearby_riders_h3(
    lat: float,
    lng: float,
    radius_cells: int = 1,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Ultra-fast honeycomb lookup for riders near a point.
    Matches Uber's K-Ring search logic.
    """
    rider_ids = geo_service.find_nearby_riders(lat, lng, k_rings=radius_cells)
    
    if not rider_ids:
        return []
    
    # Fetch user details for the matched IDs
    nearby_riders = db.query(User).filter(User.id.in_(rider_ids)).all()
    
    # Enrich with their current H3 cell
    results = []
    for r in nearby_riders:
        results.append({
            "id": r.id,
            "name": r.full_name or r.username,
            "role": r.role,
            "h3_cell": geo_service.get_hex_id(lat, lng), # Current center cell for context
            "distance_tier": "immediate" if radius_cells == 0 else "k-ring-1"
        })
        
    return results


@router.get("/export/reports")
def export_incident_reports(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Export incident reports as CSV."""
    alerts = db.query(PanicAlert).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Rider ID", "Status", "Created At", "Resolution Notes"])
    
    for alert in alerts:
        writer.writerow([alert.id, alert.rider_id, alert.status, alert.created_at, alert.resolved_at])
    
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=incident_reports.csv"}
    )
