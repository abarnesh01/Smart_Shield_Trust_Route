import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app
from database.database import Base, get_db
from database.models import (
    User, Route, SafetyFeedback, SafetyScore, DeliveryCompany, Rider, 
    DeliveryStatus, RouteMonitoring, PanicAlert, RiderCheckIn, SafeZone, 
    RideAlong, DeliveryRoute, RouteSegment, DeliveryFeedback, 
    HistoricalDelivery, CrowdsourcedAlert, RiderProfile, DriverProfile, 
    UserSession, Delivery, DeliveryBatch, DeliveryProof, Customer, BuddyPair
)

# Test fixtures are now in conftest.py

def test_register_user(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "password": "testpassword",
            "role": "rider",
            "full_name": "Test User",
            "phone": "1234567890",
            "email": "test@example.com"
        },
    )
    assert response.status_code == 200 # Current implementation returns 200 for register
    data = response.json()
    assert data["username"] == "testuser"
    assert data["role"] == "rider"

def test_login_user(client):
    # First register
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser2",
            "password": "testpassword2",
            "role": "rider",
            "full_name": "Test User 2",
            "phone": "1234567890",
            "email": "test2@example.com"
        },
    )
    
    # Then login
    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": "testuser2",
            "password": "testpassword2",
            "role": "rider"
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    
    # Check cookies
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies
    
def test_access_protected_with_cookie(client):
    # First register
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser_cookie",
            "password": "testpassword",
            "role": "rider",
            "full_name": "Test User Cookie",
            "phone": "1234567890",
            "email": "testcookie@example.com"
        },
    )
    
    # Login to get cookie
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "username": "testuser_cookie",
            "password": "testpassword",
            "role": "rider"
        },
    )
    assert login_response.status_code == 200
    cookies = login_response.cookies
    print(f"DEBUG TEST: Cookies in response: {cookies}")
    assert "access_token" in cookies
    
    # Access protected route with cookies
    # Use dict to avoid domain matching issues in TestClient
    response = client.get("/api/v1/users/profile", cookies={"access_token": cookies.get("access_token")})
    assert response.status_code == 200
    assert response.json()["username"] == "testuser_cookie"

def test_login_invalid_credentials(client):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": "nonexistent",
            "password": "wrongpassword",
            "role": "rider"
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"

def test_protected_route_unauthorized(client):
    client.cookies.clear()
    response = client.get("/api/v1/users/profile")
    assert response.status_code == 401
