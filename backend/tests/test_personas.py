"""Tests for persona API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_personas_empty(client: AsyncClient):
    """Test listing personas when none exist."""
    response = await client.get("/api/personas/")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_persona(client: AsyncClient):
    """Test creating a new persona."""
    persona_data = {
        "name": "Test Persona",
        "bio": "A test persona for unit testing",
        "niche": ["testing", "development"],
        "voice": {
            "tone": "friendly",
            "vocabulary_level": "casual",
            "emoji_usage": "minimal",
            "hashtag_style": "relevant",
            "signature_phrases": [],
        },
        "ai_provider": "openai",
    }
    
    response = await client.post("/api/personas/", json=persona_data)
    assert response.status_code == 201
    
    data = response.json()
    assert data["name"] == "Test Persona"
    assert data["bio"] == "A test persona for unit testing"
    assert data["niche"] == ["testing", "development"]
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_get_persona(client: AsyncClient):
    """Test getting a specific persona."""
    # First create a persona
    persona_data = {
        "name": "Get Test",
        "bio": "Testing get endpoint",
        "niche": ["testing"],
    }
    
    create_response = await client.post("/api/personas/", json=persona_data)
    persona_id = create_response.json()["id"]
    
    # Then get it
    response = await client.get(f"/api/personas/{persona_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Get Test"


@pytest.mark.asyncio
async def test_update_persona(client: AsyncClient):
    """Test updating a persona."""
    # Create
    persona_data = {
        "name": "Update Test",
        "bio": "Original bio",
        "niche": ["testing"],
    }
    
    create_response = await client.post("/api/personas/", json=persona_data)
    persona_id = create_response.json()["id"]
    
    # Update
    update_data = {"bio": "Updated bio", "is_active": False}
    response = await client.patch(f"/api/personas/{persona_id}", json=update_data)
    
    assert response.status_code == 200
    assert response.json()["bio"] == "Updated bio"
    assert response.json()["is_active"] is False


@pytest.mark.asyncio
async def test_delete_persona(client: AsyncClient):
    """Test deleting a persona."""
    # Create
    persona_data = {
        "name": "Delete Test",
        "bio": "Will be deleted",
        "niche": ["testing"],
    }
    
    create_response = await client.post("/api/personas/", json=persona_data)
    persona_id = create_response.json()["id"]
    
    # Delete
    response = await client.delete(f"/api/personas/{persona_id}")
    assert response.status_code == 204
    
    # Verify gone
    get_response = await client.get(f"/api/personas/{persona_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_pause_resume_persona(client: AsyncClient):
    """Test pausing and resuming a persona."""
    # Create
    persona_data = {
        "name": "Pause Test",
        "bio": "Testing pause/resume",
        "niche": ["testing"],
    }
    
    create_response = await client.post("/api/personas/", json=persona_data)
    persona_id = create_response.json()["id"]
    
    # Pause
    pause_response = await client.post(f"/api/personas/{persona_id}/pause")
    assert pause_response.status_code == 200
    assert pause_response.json()["is_active"] is False
    
    # Resume
    resume_response = await client.post(f"/api/personas/{persona_id}/resume")
    assert resume_response.status_code == 200
    assert resume_response.json()["is_active"] is True

