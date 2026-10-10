from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from datetime import datetime
import sys
from pathlib import Path

from api.deps import get_current_user, get_current_active_user, get_current_dispatcher
from database.models import User

sys.path.append(str(Path(__file__).parent.parent.parent))

from api.schemas.safety import (
    SafetyScoreRequest,
    SafetyScoreResponse,
    LocationSafetyScore,
    SafetyFactor,
    SafetyConditionsRequest,
    SafetyConditionsResponse,
    PanicButtonRequest,
    PanicButtonResponse,
    PanicButtonResolveRequest,
    CheckInRequest,
    CheckInResponse,
    SafeZonesRequest,
    RideAlongRequest,
    RideAlongResponse,
    BuddyRequest
)
from api.schemas.delivery import Coordinate
from api.models.safety_scorer import SafetyScorer
from api.services.safety import SafetyService
from database.database import get_db
from loguru import logger

router = APIRouter()
safety_scorer = SafetyScorer()
safety_service = SafetyService()

@router.post("/safety/score", response_model=SafetyScoreResponse)
async def calculate_safety_score(
    request: SafetyScoreRequest,
    db: Session = Depends(get_db)
):
    try:
        rider_info = {"gender": request.rider_gender}
        safety_data = safety_scorer.score_route(
            coordinates=request.coordinates,
            time_of_day=request.time_of_day,
            rider_info=rider_info
        )
        return SafetyScoreResponse(
            route_safety_score=safety_data.get("route_safety_score", 0),
            average_score=safety_data.get("average_score", 0),
            segment_scores=safety_data.get("segment_scores", []),
            improvement_suggestions=safety_data.get("improvement_suggestions", [])
        )
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/safety/heatmap")
async def get_safety_heatmap(
    min_lat: float, 
    min_lng: float, 
    max_lat: float, 
    max_lng: float,
    grid_size: Optional[int] = 15
):
    """Get safety heatmap points for a bounding box."""
    try:
        import random
        # Create simulated heatmap points based on the bounding box
        points = []
        for _ in range(grid_size * 2):
            points.append({
                "lat": random.uniform(min_lat, max_lat),
                "lng": random.uniform(min_lng, max_lng),
                "intensity": random.uniform(0.3, 0.95)
            })
        return {"points": points}
    except Exception as e:
        logger.error(f"Error generating heatmap: {e}")
        return {"points": [], "error": str(e)}


@router.post("/safety/panic-button", response_model=PanicButtonResponse)
async def trigger_panic_button(
    request: PanicButtonRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Trigger emergency SOS alert with authenticated user identity."""
    try:
        # Derive rider identity from authenticated user to prevent spoofing
        rider_id = current_user.username
        result = await safety_service.trigger_panic_button(
            db=db,
            rider_id=rider_id,
            location=request.location,
            route_id=request.route_id,
            delivery_id=request.delivery_id,
            emergency_email=request.emergency_email
        )
        return PanicButtonResponse(**result)
    except Exception as e:
        logger.error(f"Error triggering panic button: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/safety/panic-button/resolve")
async def resolve_panic_button(
    request: PanicButtonResolveRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Resolve an active emergency SOS alert (restricted to admin, dispatcher, or the rider)."""
    if current_user.role not in ["admin", "super_admin", "dispatcher"] and current_user.username != request.rider_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to resolve this emergency alert"
        )
    try:
        return safety_service.resolve_panic_button(
            db=db,
            alert_id=request.alert_id,
            rider_id=request.rider_id,
            resolution_notes=request.resolution_notes
        )
    except Exception as e:
        logger.error(f"Error resolving panic button: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/safety/check-in", response_model=CheckInResponse)
async def rider_check_in(
    request: CheckInRequest,
    db: Session = Depends(get_db)
):
    """Record rider check-in."""
    try:
        result = safety_service.check_in(
            db=db,
            rider_id=request.rider_id,
            location=request.location,
            route_id=request.route_id,
            delivery_id=request.delivery_id,
            is_night_shift=request.is_night_shift
        )
        return CheckInResponse(**result)
    except Exception as e:
        logger.error(f"Error during check-in: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/safety/safe-zones", response_model=List[Dict])
async def get_safe_zones(
    request: SafeZonesRequest
):
    """Get nearby safe zones."""
    try:
        return safety_service.get_safe_zones(
            location=request.location,
            radius_meters=request.radius_meters,
            zone_types=request.zone_types
        )
    except Exception as e:
        logger.error(f"Error getting safe zones: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/safety/ride-along", response_model=RideAlongResponse)
async def create_ride_along(
    request: RideAlongRequest,
    db: Session = Depends(get_db)
):
    """Create a ride-along tracking link."""
    try:
        result = safety_service.create_ride_along(
            db=db,
            rider_id=request.rider_id,
            tracker_name=request.tracker_name,
            tracker_phone=request.tracker_phone,
            tracker_email=request.tracker_email,
            route_id=request.route_id,
            delivery_id=request.delivery_id,
            expires_hours=request.expires_hours
        )
        return RideAlongResponse(**result)
    except Exception as e:
        logger.error(f"Error creating ride-along: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/safety/ride-along/{share_token}")
async def get_ride_along_status(
    share_token: str,
    db: Session = Depends(get_db)
):
    """Get ride-along tracking status."""
    result = safety_service.get_ride_along_status(db, share_token)
    if not result:
        raise HTTPException(status_code=404, detail="Ride-along link invalid or expired")
    return result

@router.post("/safety/buddy-request")
async def request_buddy(
    request: BuddyRequest,
    db: Session = Depends(get_db)
):
    """Request a buddy for a shift."""
    return safety_service.request_buddy(db, request.rider_id, request.route_id)

@router.get("/safety/buddy-status/{rider_id}")
async def get_buddy_status(
    rider_id: str,
    db: Session = Depends(get_db)
):
    """Get current buddy pair status."""
    result = safety_service.get_buddy_pair(db, rider_id)
    if not result:
        return {"status": "none"}
    return result

@router.get("/safety/alerts", response_model=List[Dict])
async def get_safety_alerts(
    limit: int = 50,
    current_user: User = Depends(get_current_dispatcher),
    db: Session = Depends(get_db)
):
    """Retrieve all safety alerts (Panic/SOS) - Dispatcher/Admin only."""
    return safety_service.get_all_panic_alerts(db, limit)
