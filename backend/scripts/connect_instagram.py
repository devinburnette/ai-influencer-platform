#!/usr/bin/env python3
"""
Script to connect an Instagram account to a persona.
Run with: docker-compose exec backend python scripts/connect_instagram.py
"""

import sys
import asyncio
from pathlib import Path

# Add the backend directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session_maker, init_db
from app.models.persona import Persona
from app.models.platform_account import PlatformAccount


async def list_personas():
    """List all personas."""
    async with async_session_maker() as session:
        result = await session.execute(select(Persona))
        personas = result.scalars().all()
        
        if not personas:
            print("\n❌ No personas found. Create one in the dashboard first!")
            print("   Go to: http://localhost:3000/personas/new")
            return []
        
        print("\n📋 Available Personas:")
        print("-" * 50)
        for p in personas:
            status = "✅ Active" if p.is_active else "⏸️ Paused"
            print(f"  {p.id}: {p.name} ({status})")
        print("-" * 50)
        return personas


async def connect_instagram(persona_id: str, username: str, password: str = None, 
                           access_token: str = None, ig_business_id: str = None):
    """Connect an Instagram account to a persona."""
    async with async_session_maker() as session:
        # Get persona
        result = await session.execute(
            select(Persona).where(Persona.id == persona_id)
        )
        persona = result.scalar_one_or_none()
        
        if not persona:
            print(f"❌ Persona with ID {persona_id} not found")
            return False
        
        # Check if account already exists
        result = await session.execute(
            select(PlatformAccount).where(
                PlatformAccount.persona_id == persona_id,
                PlatformAccount.platform == "instagram"
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            print(f"⚠️ Instagram account already connected to {persona.name}")
            response = input("Do you want to update it? (y/n): ")
            if response.lower() != 'y':
                return False
            await session.delete(existing)
            await session.commit()
        
        # Create credentials based on method
        if access_token and ig_business_id:
            # Graph API method
            credentials = {
                "access_token": access_token,
                "instagram_business_id": ig_business_id,
                "use_graph_api": True
            }
            print("📡 Using Meta Graph API method")
        elif password:
            # Browser automation method
            credentials = {
                "username": username,
                "password": password,
                "use_graph_api": False
            }
            print("🌐 Using browser automation method")
        else:
            print("❌ Either password (for browser) or access_token+ig_business_id (for Graph API) required")
            return False
        
        # Create account
        account = PlatformAccount(
            persona_id=persona_id,
            platform="instagram",
            username=username,
            credentials=credentials,
            is_active=True
        )
        session.add(account)
        await session.commit()
        
        print(f"\n✅ Instagram account @{username} connected to {persona.name}!")
        return True


async def main():
    """Interactive setup wizard."""
    print("\n" + "=" * 60)
    print("🔗 Instagram Account Connection Wizard")
    print("=" * 60)
    
    # Initialize database
    await init_db()
    
    # List personas
    personas = await list_personas()
    if not personas:
        return
    
    # Get persona selection
    print("\nEnter the ID of the persona to connect:")
    persona_id = input("> ").strip()
    
    # Get Instagram username
    print("\nEnter the Instagram username (without @):")
    username = input("> ").strip()
    
    # Choose method
    print("\nChoose connection method:")
    print("  1. Browser Automation (easier setup, requires password)")
    print("  2. Meta Graph API (recommended for production, requires access token)")
    method = input("> ").strip()
    
    if method == "1":
        print("\n⚠️ Security Warning: Password will be stored. Use a dedicated account.")
        print("Enter the Instagram password:")
        import getpass
        password = getpass.getpass("> ")
        
        await connect_instagram(persona_id, username, password=password)
        
    elif method == "2":
        print("\nEnter the long-lived access token:")
        access_token = input("> ").strip()
        
        print("\nEnter the Instagram Business Account ID:")
        ig_business_id = input("> ").strip()
        
        await connect_instagram(persona_id, username, 
                               access_token=access_token, 
                               ig_business_id=ig_business_id)
    else:
        print("❌ Invalid option")
        return
    
    print("\n" + "=" * 60)
    print("🚀 Next Steps:")
    print("=" * 60)
    print("1. Go to your persona's page in the dashboard")
    print("2. Click 'Generate New Content'")
    print("3. Review and approve the content")
    print("4. The content will be posted on schedule!")
    print("\nOr trigger a manual post:")
    print("  docker-compose exec backend python scripts/trigger_post.py")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())


