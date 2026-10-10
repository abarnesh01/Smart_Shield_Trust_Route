import pytest
from database.models import User, Delivery, Customer, PanicAlert, DeliveryRoute, HistoricalDelivery, SafetyScore
from database.database import SessionLocal
import uuid

def test_safety_heatmap_empty_and_real(client, db_session):
    # 1. Empty dataset returns empty points list
    res = client.get(
        "/api/v1/safety/heatmap",
        params={"min_lat": 10.0, "min_lng": 70.0, "max_lat": 12.0, "max_lng": 78.0}
    )
    assert res.status_code == 200
    assert res.json()["points"] == []

    # 2. Real incident in DB returns exact point
    alert = PanicAlert(
        rider_id="rider_p4",
        location={"latitude": 11.01, "longitude": 76.95},
        status="active"
    )
    db_session.add(alert)
    db_session.commit()

    res_real = client.get(
        "/api/v1/safety/heatmap",
        params={"min_lat": 11.0, "min_lng": 76.9, "max_lat": 11.1, "max_lng": 77.0}
    )
    assert res_real.status_code == 200
    pts = res_real.json()["points"]
    assert len(pts) == 1
    assert pts[0]["lat"] == 11.01
    assert pts[0]["lng"] == 76.95
    assert pts[0]["intensity"] == 0.2
    assert pts[0]["type"] == "panic_alert"

def test_delivery_queue_empty_and_real(client, db_session):
    # 1. Empty dataset returns empty data array
    res = client.get("/api/v1/dashboard/deliveries/queue")
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    # 2. Real deliveries in DB
    cust_id = str(uuid.uuid4())
    cust = Customer(id=cust_id, name="Anita Desai")
    deliv = Delivery(
        id=str(uuid.uuid4()),
        order_id="ORD-PHASE4-01",
        customer_id=cust_id,
        pickup_location={"lat": 11.01, "lng": 76.95, "address": "Store A"},
        dropoff_location={"lat": 11.05, "lng": 76.98, "address": "RS Puram, Coimbatore"},
        status="in_transit",
        safety_score=89.0,
        estimated_distance=5.5,
        estimated_duration=20.0
    )
    db_session.add(cust)
    db_session.add(deliv)
    db_session.commit()

    res_data = client.get("/api/v1/dashboard/deliveries/queue")
    assert res_data.status_code == 200
    items = res_data.json()["data"]
    match = [i for i in items if i["id"] == "ORD-PHASE4-01"]
    assert len(match) == 1
    assert match[0]["customer_name"] == "Anita Desai"
    assert match[0]["address"] == "RS Puram, Coimbatore"
    assert match[0]["priority"] == "High"

def test_dashboard_route_optimize_empty_and_real(client, db_session):
    # 1. Empty request
    res_empty = client.post("/api/v1/dashboard/route/optimize", json={"delivery_ids": []})
    assert res_empty.status_code == 200
    assert res_empty.json()["data"]["sequence"] == []

    # 2. Real deliveries in DB
    deliv1 = Delivery(
        id=str(uuid.uuid4()),
        order_id="ORD-OPT-1",
        pickup_location={"lat": 11.01, "lng": 76.95},
        dropoff_location={"lat": 11.03, "lng": 76.97},
        status="pending"
    )
    deliv2 = Delivery(
        id=str(uuid.uuid4()),
        order_id="ORD-OPT-2",
        pickup_location={"lat": 11.01, "lng": 76.95},
        dropoff_location={"lat": 11.06, "lng": 76.99},
        status="pending"
    )
    db_session.add_all([deliv1, deliv2])
    db_session.commit()

    res_opt = client.post("/api/v1/dashboard/route/optimize", json={"delivery_ids": ["ORD-OPT-1", "ORD-OPT-2"]})
    assert res_opt.status_code == 200
    opt_data = res_opt.json()
    assert opt_data["status"] == "success"
    assert len(opt_data["data"]["sequence"]) == 2
    assert opt_data["data"]["total_distance_meters"] > 0

from config.config import settings

def test_admin_analytics_trends_and_auth(client, db_session):
    admin_code = settings.ADMIN_REGISTRATION_CODE or "SECRET_TEST"
    # 1. Register rider and dispatcher
    client.post(
        "/api/v1/auth/register",
        json={"username": "rider_p4", "password": "password", "role": "rider"}
    )
    client.post(
        "/api/v1/auth/register",
        json={"username": "disp_p4", "password": "password", "role": "dispatcher", "admin_code": admin_code}
    )

    # 2. Rider cannot access admin analytics (403)
    login_rider = client.post("/api/v1/auth/login", json={"username": "rider_p4", "password": "password", "role": "rider"})
    res_rider = client.get("/api/v1/admin/analytics-trends", cookies=login_rider.cookies)
    assert res_rider.status_code in [401, 403]

    # 3. Dispatcher can access admin analytics
    login_disp = client.post("/api/v1/auth/login", json={"username": "disp_p4", "password": "password", "role": "dispatcher"})
    res_disp = client.get("/api/v1/admin/analytics-trends", cookies=login_disp.cookies)
    assert res_disp.status_code == 200
    trends = res_disp.json()
    assert "deliveryTime" in trends
    assert "safetyDistribution" in trends
    assert len(trends["deliveryTime"]) == 7

def test_admin_broadcast_auth_and_execution(client, db_session):
    admin_code = settings.ADMIN_REGISTRATION_CODE or "SECRET_TEST"
    # 1. Register admin
    client.post(
        "/api/v1/auth/register",
        json={"username": "admin_p4", "password": "password", "role": "admin", "admin_code": admin_code}
    )
    client.post(
        "/api/v1/auth/register",
        json={"username": "rider_p4_b", "password": "password", "role": "rider"}
    )

    # 2. Rider cannot broadcast (403)
    login_rider = client.post("/api/v1/auth/login", json={"username": "rider_p4_b", "password": "password", "role": "rider"})
    res_unauth = client.post("/api/v1/admin/broadcast", json={"message": "Hack"}, cookies=login_rider.cookies)
    assert res_unauth.status_code in [401, 403]

    # 3. Admin can broadcast
    login_admin = client.post("/api/v1/auth/login", json={"username": "admin_p4", "password": "password", "role": "admin"})
    res_admin = client.post("/api/v1/admin/broadcast", json={"message": "Severe Weather Warning", "target": "all"}, cookies=login_admin.cookies)
    assert res_admin.status_code == 200
    assert res_admin.json()["status"] == "success"
    assert res_admin.json()["broadcast_details"]["message"] == "Severe Weather Warning"

