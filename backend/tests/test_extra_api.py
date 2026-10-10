import pytest
from fastapi.testclient import TestClient
from api.main import app

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def test_optimize_route_simple(client):
    response = client.post(
        "/api/v1/optimize-route",
        json={
            "origin": {"lat": 13.0, "lng": 80.0},
            "destination": {"lat": 13.1, "lng": 80.1}
        }
    )
    assert response.status_code in [200, 400] 

def test_dashboard_stats(client):
    response = client.get("/api/v1/dashboard/stats")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert "active_deliveries" in response.json()["data"]

def test_delivery_queue(client):
    response = client.get("/api/v1/dashboard/deliveries/queue")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert isinstance(response.json()["data"], list)

    # Insert test delivery and verify it is retrieved
    from database.database import SessionLocal
    from database.models import Delivery, Customer
    import uuid

    db = SessionLocal()
    cust_id = str(uuid.uuid4())
    customer = Customer(id=cust_id, name="Test Customer")
    delivery = Delivery(
        id=str(uuid.uuid4()),
        order_id=f"ORD-{uuid.uuid4().hex[:6].upper()}",
        customer_id=cust_id,
        pickup_location={"lat": 11.01, "lng": 76.95, "address": "Hub A"},
        dropoff_location={"lat": 11.02, "lng": 76.96, "address": "Destination B"},
        status="in_transit",
        safety_score=92.0,
        estimated_distance=4.2,
        estimated_duration=18.0
    )
    db.add(customer)
    db.add(delivery)
    db.commit()

    try:
        res = client.get("/api/v1/dashboard/deliveries/queue")
        assert res.status_code == 200
        items = res.json()["data"]
        matching = [item for item in items if item["id"] == delivery.order_id]
        assert len(matching) == 1
        assert matching[0]["customer_name"] == "Test Customer"
        assert matching[0]["address"] == "Destination B"
        assert matching[0]["safety_score"] == 92
        assert matching[0]["priority"] == "High"
    finally:
        db.delete(delivery)
        db.delete(customer)
        db.commit()
        db.close()

def test_dashboard_route_optimize_empty(client):
    response = client.post("/api/v1/dashboard/route/optimize", json={"delivery_ids": []})
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["data"]["sequence"] == []

def test_zone_safety(client):
    response = client.get("/api/v1/dashboard/zones/safety")
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_weather_endpoint(client):
    response = client.get("/api/v1/dashboard/weather?lat=13.0&lon=80.0")
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_safety_heatmap(client):
    response = client.get(
        "/api/v1/safety/heatmap",
        params={
            "min_lat": 12.9,
            "min_lng": 79.9,
            "max_lat": 13.1,
            "max_lng": 80.1,
            "grid_size": 2
        }
    )
    assert response.status_code == 200
    assert "points" in response.json()
