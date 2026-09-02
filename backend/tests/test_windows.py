from tests.conftest import reset_db
def test_window_generation(client):
    reset_db()
    # ensure windows can be generated
    r = client.post("/api/windows/generate?horizon_start=2026-09-01&horizon_end=2026-09-03")
    assert r.json()["generated"] > 0
    r = client.get("/api/windows")
    assert len(r.json()) > 0
    # check window has required fields
    w = r.json()[0]
    assert "window_id" in w
    assert "availability_source" in w
    assert "Synthetic prototype" in w["availability_source"]
