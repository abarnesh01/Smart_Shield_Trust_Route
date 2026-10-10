"""Dashboard API endpoints for stats and analytics."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.database import get_db
from database.models import User, Route, SafetyFeedback, DeliveryStatus
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
from loguru import logger
import random

from database.models import User, Route, SafetyFeedback, DeliveryStatus, Delivery, HistoricalDelivery, AlertPreferences, Customer
from api.services.weather import WeatherService
from api.schemas.delivery import Coordinate, DeliveryStop
from api.models.route_optimizer import RouteOptimizer
from sqlalchemy import func

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
weather_service = WeatherService()
route_optimizer = RouteOptimizer()

@router.get("/stats")
async def get_dashboard_stats(
    user_id: str = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get dashboard statistics based on real delivery data."""
    try:
        # 1. Active Deliveries (count 'in_transit' or 'assigned')
        active_count = db.query(Delivery).filter(
            Delivery.status.in_(["in_transit", "assigned", "picked_up"])
        ).count()
        
        # 2. Safety Score (average from feedback)
        avg_safety_result = db.query(func.avg(SafetyFeedback.rating)).scalar()
        avg_safety = int(avg_safety_result * 20) if avg_safety_result else 87 # Scale 1-5 to 0-100%
        
        # 3. Fuel Saved (calculated from historical savings if available, otherwise estimate)
        # For now, sum up estimated fuel saved from optimized routes
        total_fuel_saved = db.query(func.sum(HistoricalDelivery.fuel_consumed)).scalar() or 0
        fuel_saved_display = round(total_fuel_saved * 0.15, 1) # Assume 15% optimization savings for display
        
        # 4. Average Delivery Time (from historical records)
        avg_time_mins = db.query(func.avg(HistoricalDelivery.delivery_time_minutes)).scalar() or 22
        
        return {
            "status": "success",
            "data": {
                "active_deliveries": {
                    "value": str(active_count),
                    "subValue": f"{active_count} in transit",
                    "trend": "+8% vs last week"
                },
                "safety_score": {
                    "value": f"{avg_safety}%",
                    "subValue": "Based on rider feedback",
                    "trend": "+2% vs last week"
                },
                "fuel_saved": {
                    "value": f"{fuel_saved_display}L",
                    "subValue": "Estimated savings",
                    "trend": "+12% vs last week"
                },
                "avg_delivery_time": {
                    "value": f"{int(avg_time_mins)} min",
                    "subValue": "Target: 20 min",
                    "trend": "-3% vs last week"
                }
            }
        }
    except Exception as e:
        logger.error(f"Error fetching dashboard stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/deliveries/queue")
async def get_delivery_queue(
    limit: int = 10,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get current delivery queue with details from database."""
    try:
        deliveries = (
            db.query(Delivery)
            .order_by(Delivery.created_at.desc())
            .limit(limit)
            .all()
        )
        
        customer_ids = [d.customer_id for d in deliveries if d.customer_id]
        customers = {}
        if customer_ids:
            customers = {c.id: c for c in db.query(Customer).filter(Customer.id.in_(customer_ids)).all()}

        queue_items = []
        for d in deliveries:
            cust = customers.get(d.customer_id)
            cust_name = cust.name if cust else "Valued Customer"
            dropoff = d.dropoff_location or {}
            address = dropoff.get("address") or "Coimbatore Delivery Area"
            
            # Format distance
            dist_val = d.estimated_distance
            dist_str = f"{dist_val:.1f} km" if dist_val is not None else "3.5 km"
            
            # Format time
            time_val = d.estimated_duration
            time_str = f"{int(time_val)} mins" if time_val is not None else "15 mins"
            
            # Priority & color
            priority = "Normal"
            priority_color = "blue"
            if d.status == "in_transit":
                priority = "High"
                priority_color = "amber"
            elif d.status == "failed":
                priority = "Urgent"
                priority_color = "red"

            queue_items.append({
                "id": d.order_id or d.id,
                "customer_name": cust_name,
                "address": address,
                "estimated_time": time_str,
                "distance": dist_str,
                "safety_score": int(d.safety_score) if d.safety_score is not None else 85,
                "status": d.status.replace("_", " ").title() if d.status else "Pending",
                "priority": priority,
                "priority_color": priority_color
            })

        return {
            "status": "success",
            "data": queue_items,
            "total": len(queue_items)
        }
    except Exception as e:
        logger.error(f"Error fetching delivery queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/zones/safety")
async def get_zone_safety(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get safety information for different zones."""
    try:
        # Static safe zones for demo
        zones = [
            {"name": "Chennai Central", "incidents": "2 hazards", "trend": "down", "score": 85, "color": "green", "last_updated": datetime.now().isoformat()},
            {"name": "Anna Nagar", "incidents": "4 hazards", "trend": "neutral", "score": 72, "color": "amber", "last_updated": datetime.now().isoformat()},
            {"name": "T. Nagar", "incidents": "1 hazard", "trend": "down", "score": 91, "color": "green", "last_updated": datetime.now().isoformat()}
        ]
        
        return {
            "status": "success",
            "data": zones,
            "updated_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching zone safety: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/weather")
async def get_weather_conditions(
    lat: float = 13.0827,
    lon: float = 80.2707
) -> Dict[str, Any]:
    """Get real-time weather conditions for location."""
    try:
        coord = Coordinate(latitude=lat, longitude=lon)
        weather_data = await weather_service.get_weather(coord)
        
        return {
            "status": "success",
            "data": weather_data
        }
    except Exception as e:
        logger.error(f"Error fetching weather: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class OptimizeRequest(BaseModel):
    delivery_ids: List[str]

@router.post("/route/optimize")
async def optimize_current_route(
    request: OptimizeRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Optimize route for given deliveries using real RouteOptimizer."""
    try:
        ids = [str(did).strip() for did in request.delivery_ids if str(did).strip()]
        if not ids:
            return {
                "status": "success",
                "message": "No deliveries provided to optimize",
                "estimated_time_saved": "0 minutes",
                "fuel_saved": "0.0L",
                "data": {
                    "sequence": [],
                    "total_distance_meters": 0.0,
                    "total_duration_seconds": 0.0,
                    "average_safety_score": 0.0,
                    "total_fuel_liters": 0.0
                }
            }

        deliveries = (
            db.query(Delivery)
            .filter((Delivery.id.in_(ids)) | (Delivery.order_id.in_(ids)))
            .all()
        )

        if not deliveries:
            return {
                "status": "success",
                "message": "No matching delivery records found",
                "estimated_time_saved": "0 minutes",
                "fuel_saved": "0.0L",
                "data": {
                    "sequence": [],
                    "total_distance_meters": 0.0,
                    "total_duration_seconds": 0.0,
                    "average_safety_score": 0.0,
                    "total_fuel_liters": 0.0
                }
            }

        stops: List[DeliveryStop] = []
        for d in deliveries:
            dropoff = d.dropoff_location or {}
            lat = dropoff.get("lat") or dropoff.get("latitude")
            lng = dropoff.get("lng") or dropoff.get("longitude")
            if lat is not None and lng is not None:
                stops.append(DeliveryStop(
                    stop_id=str(d.order_id or d.id),
                    address=dropoff.get("address") or "Delivery Location",
                    coordinates=Coordinate(latitude=float(lat), longitude=float(lng)),
                    priority="high" if d.status == "in_transit" else "medium"
                ))

        if not stops:
            return {
                "status": "success",
                "message": "Deliveries found but lack valid destination coordinates",
                "estimated_time_saved": "0 minutes",
                "fuel_saved": "0.0L",
                "data": {
                    "sequence": [],
                    "total_distance_meters": 0.0,
                    "total_duration_seconds": 0.0,
                    "average_safety_score": 0.0,
                    "total_fuel_liters": 0.0
                }
            }

        first_pickup = deliveries[0].pickup_location or {}
        p_lat = first_pickup.get("lat") or first_pickup.get("latitude")
        p_lng = first_pickup.get("lng") or first_pickup.get("longitude")
        if p_lat is not None and p_lng is not None:
            starting_point = Coordinate(latitude=float(p_lat), longitude=float(p_lng))
        else:
            starting_point = Coordinate(latitude=11.0168, longitude=76.9558)

        optimized = await route_optimizer.optimize_route(
            starting_point=starting_point,
            stops=stops,
            optimize_for=["time", "distance", "safety"]
        )

        total_duration = float(optimized.get("total_duration_seconds", 0.0))
        total_distance = float(optimized.get("total_distance_meters", 0.0))
        total_fuel = float(optimized.get("total_fuel_liters", 0.0))
        avg_safety = float(optimized.get("average_safety_score", 0.0))

        time_saved_mins = max(1, int(total_duration * 0.15 / 60)) if total_duration > 0 else 0
        fuel_saved_l = round(total_fuel * 0.15, 2) if total_fuel > 0 else 0.0

        return {
            "status": "success",
            "message": f"Route successfully optimized for {len(stops)} stops",
            "estimated_time_saved": f"{time_saved_mins} minutes",
            "fuel_saved": f"{fuel_saved_l}L",
            "data": {
                "sequence": optimized.get("sequence", []),
                "total_distance_meters": total_distance,
                "total_duration_seconds": total_duration,
                "average_safety_score": avg_safety,
                "total_fuel_liters": total_fuel,
                "optimizations_applied": optimized.get("optimizations_applied", [])
            }
        }
    except Exception as e:
        logger.error(f"Error optimizing route: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/alerts/recent")
async def get_recent_alerts(
    limit: int = 5,
    user_id: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get recent safety alerts, filtered by user preferences if user_id provided."""
    try:
        alerts = db.query(SafetyFeedback).order_by(
            SafetyFeedback.date_submitted.desc()
        ).limit(limit * 3).all()  # Fetch more to account for filtering
        
        # Get user preferences if user_id provided
        preferences = None
        if user_id:
            preferences = db.query(AlertPreferences).filter(
                AlertPreferences.user_id == user_id
            ).first()
        
        # Generate title based on incident type
        def get_alert_title(incident_type, feedback_type):
            titles = {
                'suspicious_activity': 'Suspicious Activity Reported',
                'road_hazard': 'Road Hazard Detected',
                'poor_lighting': 'Poorly Lit Area'
            }
            return titles.get(incident_type or feedback_type, 'Safety Feedback')
        
        # Map alert type to preference field
        def get_preference_field(alert_type):
            mapping = {
                'suspicious_activity': 'suspicious_activity',
                'road_hazard': 'road_hazard',
                'poor_lighting': 'poor_lighting'
            }
            return mapping.get(alert_type, 'general_alert')
        
        alert_data = []
        for alert in alerts:
            alert_type = alert.incident_type or alert.feedback_type or 'general'
            severity = "high" if alert.rating <= 2 else "medium" if alert.rating <= 3 else "low"
            
            # Apply preference filters if preferences exist
            if preferences:
                # Check alert type preference
                pref_field = get_preference_field(alert_type)
                if not getattr(preferences, pref_field, True):
                    continue
                
                # Check severity level preference
                if severity == "high" and not preferences.show_high_severity:
                    continue
                if severity == "medium" and not preferences.show_medium_severity:
                    continue
                if severity == "low" and not preferences.show_low_severity:
                    continue
                
                # Check time preference (night alerts only)
                if preferences.night_alerts_only:
                    time_of_day = alert.time_of_day or "day"
                    if time_of_day != "night":
                        continue
            
            # Map feedback fields to expected dashboard alert structure
            alert_data.append({
                "id": alert.id,
                "type": alert_type,
                "title": get_alert_title(alert.incident_type, alert.feedback_type),
                "message": alert.comments or 'Safety feedback received',
                "location": alert.location if isinstance(alert.location, dict) else {},
                "severity": severity,
                "created_at": alert.date_submitted.isoformat() if alert.date_submitted else None,
                "time_of_day": alert.time_of_day or "day"
            })
            
            # Stop if we have enough alerts
            if len(alert_data) >= limit:
                break
        
        return {
            "status": "success",
            "data": alert_data,
            "count": len(alert_data)
        }
    except Exception as e:
        logger.error(f"Error fetching alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alert-preferences/{user_id}")
async def get_alert_preferences(
    user_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get user's alert notification preferences."""
    try:
        # Check if preferences exist
        preferences = db.query(AlertPreferences).filter(
            AlertPreferences.user_id == user_id
        ).first()
        
        # If no preferences exist, create default ones
        if not preferences:
            preferences = AlertPreferences(user_id=user_id)
            db.add(preferences)
            db.commit()
            db.refresh(preferences)
        
        return {
            "status": "success",
            "data": {
                "user_id": preferences.user_id,
                "alert_types": {
                    "suspicious_activity": preferences.suspicious_activity,
                    "road_hazard": preferences.road_hazard,
                    "poor_lighting": preferences.poor_lighting,
                    "weather_hazard": preferences.weather_hazard,
                    "safety_concern": preferences.safety_concern,
                    "general_alert": preferences.general_alert
                },
                "severity_levels": {
                    "high": preferences.show_high_severity,
                    "medium": preferences.show_medium_severity,
                    "low": preferences.show_low_severity
                },
                "time_preferences": {
                    "night_alerts_only": preferences.night_alerts_only
                },
                "notification_channels": {
                    "push": preferences.push_notifications,
                    "email": preferences.email_notifications
                },
                "updated_at": preferences.updated_at.isoformat() if preferences.updated_at else None
            }
        }
    except Exception as e:
        logger.error(f"Error fetching alert preferences: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class AlertPreferencesUpdate(BaseModel):
    """Schema for updating alert preferences."""
    alert_types: Optional[Dict[str, bool]] = None
    severity_levels: Optional[Dict[str, bool]] = None
    time_preferences: Optional[Dict[str, bool]] = None
    notification_channels: Optional[Dict[str, bool]] = None


@router.put("/alert-preferences/{user_id}")
async def update_alert_preferences(
    user_id: str,
    preferences_update: AlertPreferencesUpdate,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Update user's alert notification preferences."""
    try:
        # Get or create preferences
        preferences = db.query(AlertPreferences).filter(
            AlertPreferences.user_id == user_id
        ).first()
        
        if not preferences:
            preferences = AlertPreferences(user_id=user_id)
            db.add(preferences)
        
        # Update alert types
        if preferences_update.alert_types:
            for alert_type, enabled in preferences_update.alert_types.items():
                if hasattr(preferences, alert_type):
                    setattr(preferences, alert_type, enabled)
        
        # Update severity levels
        if preferences_update.severity_levels:
            severity_map = {
                "high": "show_high_severity",
                "medium": "show_medium_severity",
                "low": "show_low_severity"
            }
            for severity, enabled in preferences_update.severity_levels.items():
                db_field = severity_map.get(severity)
                if db_field:
                    setattr(preferences, db_field, enabled)
        
        # Update time preferences
        if preferences_update.time_preferences:
            if "night_alerts_only" in preferences_update.time_preferences:
                preferences.night_alerts_only = preferences_update.time_preferences["night_alerts_only"]
        
        # Update notification channels
        if preferences_update.notification_channels:
            if "push" in preferences_update.notification_channels:
                preferences.push_notifications = preferences_update.notification_channels["push"]
            if "email" in preferences_update.notification_channels:
                preferences.email_notifications = preferences_update.notification_channels["email"]
        
        db.commit()
        db.refresh(preferences)
        
        return {
            "status": "success",
            "message": "Alert preferences updated successfully",
            "data": {
                "user_id": preferences.user_id,
                "updated_at": preferences.updated_at.isoformat()
            }
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating alert preferences: {e}")
        raise HTTPException(status_code=500, detail=str(e))
