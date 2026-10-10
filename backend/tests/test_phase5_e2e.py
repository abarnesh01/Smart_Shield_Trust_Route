import pytest
import uuid
from database.models import User, Delivery, Customer, PanicAlert, DeliveryRoute, SafetyFeedback
from config.config import settings

ADMIN_CODE = settings.ADMIN_REGISTRATION_CODE or "SECRET_TEST"

def test_e2e_customer_flow(client, db_session):
    """1. Customer registration and login workflow."""
    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "username": "customer_e2e",
            "password": "CustomerPassword123!",
            "role": "customer",
            "full_name": "E2E Customer",
            "email": "customer_e2e@example.com",
            "phone": "9876543210"
        }
    )
    assert reg_res.status_code == 200
    assert reg_res.json()["role"] == "customer"

    login_res = client.post(
        "/api/v1/auth/login",
        json={
            "username": "customer_e2e",
            "password": "CustomerPassword123!",
            "role": "customer"
        }
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    assert token is not None
    assert login_res.cookies.get("access_token") is not None

def test_e2e_rider_driver_delivery_flow(client, db_session):
    """2. Rider & Driver authentication, delivery queue access, and route optimization."""
    # Register Rider
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "rider_e2e",
            "password": "RiderPassword123!",
            "role": "rider",
            "full_name": "E2E Rider",
            "phone": "9876543211",
            "vehicle_type": "motorcycle"
        }
    )
    rider_login = client.post(
        "/api/v1/auth/login",
        json={"username": "rider_e2e", "password": "RiderPassword123!", "role": "rider"}
    )
    assert rider_login.status_code == 200
    rider_cookies = rider_login.cookies

    # Register Driver (requires approval)
    driver_reg = client.post(
        "/api/v1/auth/register",
        json={
            "username": "driver_e2e",
            "password": "DriverPassword123!",
            "role": "driver",
            "full_name": "E2E Driver",
            "phone": "9876543212",
            "license_number": "DL-998877",
            "vehicle_type": "van"
        }
    )
    assert driver_reg.status_code == 200
    assert driver_reg.json()["status"] == "pending_approval"

    # Seed Customer & Delivery in DB
    cust_id = str(uuid.uuid4())
    customer = Customer(id=cust_id, name="Vanya Sharma")
    delivery = Delivery(
        id=str(uuid.uuid4()),
        order_id="ORD-E2E-100",
        customer_id=cust_id,
        pickup_location={"lat": 11.01, "lng": 76.95, "address": "Central Warehouse"},
        dropoff_location={"lat": 11.04, "lng": 76.98, "address": "T. Nagar Coimbatore"},
        status="in_transit",
        safety_score=94.0,
        estimated_distance=4.8,
        estimated_duration=16.0
    )
    db_session.add(customer)
    db_session.add(delivery)
    db_session.commit()

    # Access delivery queue as authenticated rider
    queue_res = client.get("/api/v1/dashboard/deliveries/queue", cookies=rider_cookies)
    assert queue_res.status_code == 200
    items = queue_res.json()["data"]
    match = [i for i in items if i["id"] == "ORD-E2E-100"]
    assert len(match) == 1
    assert match[0]["customer_name"] == "Vanya Sharma"

    # Optimize route for valid delivery
    opt_res = client.post(
        "/api/v1/dashboard/route/optimize",
        json={"delivery_ids": ["ORD-E2E-100"]},
        cookies=rider_cookies
    )
    assert opt_res.status_code == 200
    assert opt_res.json()["status"] == "success"
    assert len(opt_res.json()["data"]["sequence"]) == 1

def test_e2e_safety_heatmap_and_sos_flow(client, db_session):
    # 1. Register rider for SOS
    client.post(
        "/api/v1/auth/register",
        json={"username": "rider_sos", "password": "Password123!", "role": "rider"}
    )
    rider_login = client.post("/api/v1/auth/login", json={"username": "rider_sos", "password": "Password123!", "role": "rider"})
    rider_cookies = rider_login.cookies

    # 2. Register dispatcher for SOS resolution
    client.post(
        "/api/v1/auth/register",
        json={"username": "disp_sos", "password": "Password123!", "role": "dispatcher", "admin_code": ADMIN_CODE}
    )
    disp_login = client.post("/api/v1/auth/login", json={"username": "disp_sos", "password": "Password123!", "role": "dispatcher"})
    disp_cookies = disp_login.cookies

    # 3. Test safety heatmap empty state
    heatmap_empty = client.get("/api/v1/safety/heatmap", params={"min_lat": 12.0, "min_lng": 77.0, "max_lat": 12.5, "max_lng": 77.5})
    assert heatmap_empty.status_code == 200
    assert heatmap_empty.json()["points"] == []

    # 4. Trigger SOS Panic alert
    sos_res = client.post(
        "/api/v1/safety/panic-button",
        json={"rider_id": "rider_sos", "location": {"latitude": 12.2, "longitude": 77.2}},
        cookies=rider_cookies
    )
    assert sos_res.status_code == 200
    alert_id = sos_res.json()["alert_id"]

    # 5. Verify heatmap now contains incident
    heatmap_incident = client.get("/api/v1/safety/heatmap", params={"min_lat": 12.0, "min_lng": 77.0, "max_lat": 12.5, "max_lng": 77.5})
    assert heatmap_incident.status_code == 200
    points = heatmap_incident.json()["points"]
    assert len(points) == 1
    assert points[0]["lat"] == 12.2

    # 6. Unauthorized user (different rider) attempting resolution gets 403
    client.post(
        "/api/v1/auth/register",
        json={"username": "other_rider", "password": "Password123!", "role": "rider"}
    )
    other_rider_login = client.post("/api/v1/auth/login", json={"username": "other_rider", "password": "Password123!", "role": "rider"})
    unauth_resolve = client.post(
        "/api/v1/safety/panic-button/resolve",
        json={"alert_id": alert_id, "rider_id": "rider_sos"},
        cookies=other_rider_login.cookies
    )
    assert unauth_resolve.status_code == 403

    # 7. Authorized dispatcher resolves SOS alert
    auth_resolve = client.post(
        "/api/v1/safety/panic-button/resolve",
        json={"alert_id": alert_id, "rider_id": "rider_sos", "resolution_notes": "Patrol dispatched and rider secured."},
        cookies=disp_cookies
    )
    assert auth_resolve.status_code == 200
    assert auth_resolve.json()["status"] == "resolved"

def test_e2e_admin_broadcast_and_analytics_flow(client, db_session):
    # 1. Register admin
    client.post(
        "/api/v1/auth/register",
        json={"username": "admin_e2e", "password": "AdminPassword123!", "role": "admin", "admin_code": ADMIN_CODE}
    )
    admin_login = client.post("/api/v1/auth/login", json={"username": "admin_e2e", "password": "AdminPassword123!", "role": "admin"})
    admin_cookies = admin_login.cookies

    # 2. Get Admin Analytics Trends
    trends_res = client.get("/api/v1/admin/analytics-trends", cookies=admin_cookies)
    assert trends_res.status_code == 200
    trends = trends_res.json()
    assert "deliveryTime" in trends
    assert "safetyDistribution" in trends

    # 3. Post Admin Broadcast
    broadcast_res = client.post(
        "/api/v1/admin/broadcast",
        json={"message": "System Maintenance scheduled at 02:00 UTC", "target": "all"},
        cookies=admin_cookies
    )
    assert broadcast_res.status_code == 200
    assert broadcast_res.json()["status"] == "success"
    assert broadcast_res.json()["broadcast_details"]["message"] == "System Maintenance scheduled at 02:00 UTC"

def test_e2e_security_token_and_unauthorized_flow(client):
    # 1. Request without token/cookie on protected endpoint returns 401
    unauth_res = client.get("/api/v1/admin/analytics-trends")
    assert unauth_res.status_code in [401, 403]

    # 2. Request with invalid token returns 401
    invalid_token_res = client.get("/api/v1/admin/analytics-trends", headers={"Authorization": "Bearer invalid_token_xyz"})
    assert invalid_token_res.status_code in [401, 403]
