async def test_analyze_meal_photo_endpoint_is_registered_for_stage_four(client):
    """Verify a valid upload reaches the staged meal-flow implementation boundary."""

    response = await client.post(
        "/api/v1/meals/analyze-photo",
        files={"image": ("meal.jpg", b"fake-image-bytes", "image/jpeg")},
        data={"notes": "Dinner plate"},
    )

    assert response.status_code == 501
    assert response.json()["detail"] == "Meal photo analysis endpoint is not implemented yet."


async def test_analyze_meal_photo_rejects_non_image_upload(client):
    """Verify unsupported upload content types are rejected before staged work runs."""

    response = await client.post(
        "/api/v1/meals/analyze-photo",
        files={"image": ("meal.txt", b"not-an-image", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json()["detail"] == "Upload must be a JPEG, PNG, WEBP, or non-animated GIF image."


async def test_analyze_meal_photo_rejects_empty_image(client):
    """Verify empty image uploads are rejected before storage or AI analysis."""

    response = await client.post(
        "/api/v1/meals/analyze-photo",
        files={"image": ("meal.jpg", b"", "image/jpeg")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Image is empty."


async def test_analyze_meal_photo_rejects_oversized_image(client):
    """Verify uploads over the configured max size are rejected before storage."""

    oversized_image = b"0" * (10 * 1024 * 1024 + 1)

    response = await client.post(
        "/api/v1/meals/analyze-photo",
        files={"image": ("meal.jpg", oversized_image, "image/jpeg")},
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "Image exceeds 10 MB limit."
