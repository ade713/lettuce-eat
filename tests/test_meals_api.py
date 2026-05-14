async def test_analyze_meal_photo_endpoint_is_registered_for_stage_four(client):
    """Verify the staged meal-flow endpoint exists before storage and AI are wired."""

    response = await client.post(
        "/api/v1/meals/analyze-photo",
        files={"image": ("meal.jpg", b"fake-image-bytes", "image/jpeg")},
        data={"notes": "Dinner plate"},
    )

    assert response.status_code == 501
    assert response.json()["detail"] == "Meal photo analysis endpoint is not implemented yet."
