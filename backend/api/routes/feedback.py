from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from database.database import get_db
from database.models import DeliveryFeedback, DeliveryRoute, CrowdsourcedAlert, User
from api.deps import get_current_dispatcher
from loguru import logger

router = APIRouter()

class FeedbackSubmit(BaseModel):
    route_id: str
    rider_id: str
    safety_rating: int
    route_quality_rating: int
    comfort_rating: int
    incidents_reported: List[dict] = []
    unsafe_areas: List[dict] = []
    feedback_text: Optional[str] = None

@router.post("/feedback/submit")
async def submit_feedback(feedback: FeedbackSubmit, db: Session = Depends(get_db)):
    """Submit rider feedback for a completed route."""
    try:
        # Find the internal route ID
        db_route = db.query(DeliveryRoute).filter(DeliveryRoute.route_id == feedback.route_id).first()
        if not db_route:
            # Fallback if route not in new table yet
            logger.warning(f"Route {feedback.route_id} not found in delivery_routes table")
            # In a real app, we might create a placeholder or error out
        
        new_feedback = DeliveryFeedback(
            route_id=db_route.id if db_route else None,
            rider_id=feedback.rider_id,
            safety_rating=feedback.safety_rating,
            route_quality_rating=feedback.route_quality_rating,
            comfort_rating=feedback.comfort_rating,
            incidents_reported=feedback.incidents_reported,
            unsafe_areas=feedback.unsafe_areas,
            feedback_text=feedback.feedback_text,
            submitted_at=datetime.utcnow()
        )
        
        db.add(new_feedback)
        db.commit()
        
        # After feedback is submitted, the RL agent could be updated
        # This is part of the feedback loop renovation
        
        return {"status": "success", "message": "Feedback submitted successfully"}
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class AlertSubmit(BaseModel):
    rider_id: str
    service_type: str
    location: dict
    is_faster: bool
    has_traffic_issues: bool

@router.post("/feedback/alert")
async def submit_alert(alert: AlertSubmit, db: Session = Depends(get_db)):
    """Submit a crowdsourced rider alert."""
    try:
        new_alert = CrowdsourcedAlert(
            rider_id=alert.rider_id,
            service_type=alert.service_type,
            location=alert.location,
            is_faster=alert.is_faster,
            has_traffic_issues=alert.has_traffic_issues,
            created_at=datetime.utcnow()
        )
        db.add(new_alert)
        db.commit()
        return {"status": "success", "message": "Alert submitted successfully"}
    except Exception as e:
        logger.error(f"Error submitting alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/feedback/alerts")
async def get_alerts(service_type: Optional[str] = None, db: Session = Depends(get_db)):
    """Retrieve crowdsourced alerts for visualization."""
    try:
        query = db.query(CrowdsourcedAlert)
        if service_type:
            query = query.filter(CrowdsourcedAlert.service_type == service_type)
        
        # Only get alerts from the last 4 hours for real-time relevance
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=4)
        alerts = query.filter(CrowdsourcedAlert.created_at >= cutoff).all()
        
        return {
            "status": "success",
            "data": [
                {
                    "id": a.id,
                    "service_type": a.service_type,
                    "location": a.location,
                    "is_faster": a.is_faster,
                    "has_traffic_issues": a.has_traffic_issues,
                    "created_at": a.created_at
                } for a in alerts
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/feedback/all")
async def list_all_feedback(
    current_user: User = Depends(get_current_dispatcher),
    db: Session = Depends(get_db)
):
    """List all delivery feedback for admin dashboard - Dispatcher/Admin only."""
    try:
        feedback_list = db.query(DeliveryFeedback).order_by(DeliveryFeedback.submitted_at.desc()).all()
        return {
            "status": "success",
            "data": [
                {
                    "id": f.id,
                    "route_id": f.route_id,
                    "rider_id": f.rider_id,
                    "safety_rating": f.safety_rating,
                    "route_quality_rating": f.route_quality_rating,
                    "comfort_rating": f.comfort_rating,
                    "feedback_text": f.feedback_text,
                    "submitted_at": f.submitted_at
                } for f in feedback_list
            ]
        }
    except Exception as e:
        logger.error(f"Error listing feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))
