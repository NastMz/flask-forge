from importlib import import_module

def test_health():
    pkg = import_module("{{ package_name }}")
    app = pkg.create_app()
    c = app.test_client()
    r = c.get("/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"