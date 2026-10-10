import pytest
from api.models.safety_scorer import SafetyScorer
from api.models.route_optimizer import RouteOptimizer
from api.schemas.delivery import Coordinate, DeliveryStop

@pytest.fixture(autouse=True)
def setup_db():
    from database.database import Base, engine
    Base.metadata.create_all(bind=engine)
    yield

@pytest.mark.asyncio
async def test_safety_scorer_basic():
    scorer = SafetyScorer()
    coord = Coordinate(latitude=13.0, longitude=80.0)
    
    # Test score_location (returns Tuple[float, List])
    score, factors = scorer.score_location(coord)
    assert 0 <= score <= 100
    assert isinstance(factors, list)

@pytest.mark.asyncio
async def test_route_optimizer_basic():
    optimizer = RouteOptimizer()
    start = Coordinate(latitude=13.0, longitude=80.0)
    stops = [
        DeliveryStop(
            stop_id="S1", 
            address="Addr 1", 
            coordinates=Coordinate(latitude=13.1, longitude=80.1)
        )
    ]
    
    # Test optimize_route (async)
    result = await optimizer.optimize_route(start, stops)
    assert result is not None
    assert "sequence" in result
    assert "segments" in result

@pytest.mark.asyncio
async def test_safety_scorer_route():
    scorer = SafetyScorer()
    coords = [
        Coordinate(latitude=13.0, longitude=80.0),
        Coordinate(latitude=13.05, longitude=80.05),
        Coordinate(latitude=13.1, longitude=80.1)
    ]
    
    # Test score_route (returns Dict)
    metrics = scorer.score_route(coords)
    assert "route_safety_score" in metrics
    assert "risk_level" in metrics

@pytest.mark.asyncio
async def test_route_optimizer_alternatives():
    optimizer = RouteOptimizer()
    start = Coordinate(latitude=13.0, longitude=80.0)
    stop = DeliveryStop(
        stop_id="S2", 
        address="Addr 2", 
        coordinates=Coordinate(latitude=13.1, longitude=80.1)
    )
    
    # Test _optimize_single_leg_alternatives (private) - it is async
    # It returns a best_route Dict which contains an "alternatives" List
    best_route = await optimizer._optimize_single_leg_alternatives(
        start, stop, optimize_for=["time", "safety"], rider_info=None, departure_time=None
    )
    assert isinstance(best_route, dict)
    assert "alternatives" in best_route
    assert isinstance(best_route["alternatives"], list)
