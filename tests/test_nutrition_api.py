async def test_analyze_nutrition_accepts_image_and_persists_result(client):
    response = await client.post(
        "/api/v1/nutrition/analyze",
        files={"image": ("meal.jpg", b"fake-image-bytes", "image/jpeg")},
        data={"notes": "Dinner plate"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["food_name"] == "Chicken rice bowl"
    assert body["calories_kcal"] == 640
    assert body["macros"]["protein_g"] == 42

    persisted = await client.get(f"/api/v1/nutrition/analyses/{body['id']}")
    assert persisted.status_code == 200
    assert persisted.json()["food_name"] == "Chicken rice bowl"


async def test_analyze_nutrition_rejects_non_image_upload(client):
    response = await client.post(
        "/api/v1/nutrition/analyze",
        files={"image": ("meal.txt", b"not-an-image", "text/plain")},
    )

    assert response.status_code == 415
