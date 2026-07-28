async def test_frontend_index_served(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "Carnet+" in resp.text


async def test_frontend_static_page_served(client):
    resp = await client.get("/choix-compte.html")
    assert resp.status_code == 200
    assert "Choisissez votre profil" in resp.text


async def test_api_routes_not_shadowed_by_static_mount(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
