#!/usr/bin/env python3
"""
Script to connect a Twitter/X account to a persona.
Run with: docker-compose exec backend python scripts/connect_twitter.py

To get Twitter API credentials:
1. Go to https://developer.twitter.com/en/portal/dashboard
2. Create a new project and app
3. Generate API Key, API Secret, Access Token, and Access Token Secret
4. Make sure your app has Read and Write permissions
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
from app.models.platform_account import PlatformAccount, Platform


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


async def verify_twitter_credentials(api_key: str, api_secret: str, 
                                      access_token: str, access_token_secret: str,
                                      bearer_token: str = None) -> tuple[bool, dict]:
    """Verify Twitter credentials by making a test API call."""
    from app.services.platforms.twitter.api import TwitterAPI
    
    api = TwitterAPI(
        api_key=api_key,
        api_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
        bearer_token=bearer_token,
    )
    
    try:
        if await api.verify_credentials():
            profile = await api.get_me()
            await api.close()
            return True, {
                "user_id": api._user_id,
                "username": api._username,
                "profile": profile,
            }
    except Exception as e:
        print(f"❌ Verification failed: {e}")
    finally:
        await api.close()
    
    return False, {}


async def connect_twitter(
    persona_id: str,
    username: str,
    api_key: str,
    api_secret: str,
    access_token: str,
    access_token_secret: str,
    bearer_token: str = None,
    platform_user_id: str = None,
):
    """Connect a Twitter account to a persona."""
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
                PlatformAccount.platform == Platform.TWITTER
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            print(f"⚠️ Twitter account already connected to {persona.name}")
            response = input("Do you want to update it? (y/n): ")
            if response.lower() != 'y':
                return False
            await session.delete(existing)
            await session.commit()
        
        # Store credentials in session_cookies field (JSON)
        # In production, these should be encrypted
        credentials = {
            "api_key": api_key,
            "api_secret": api_secret,
            "access_token": access_token,
            "access_token_secret": access_token_secret,
            "bearer_token": bearer_token,
        }
        
        # Create account
        account = PlatformAccount(
            persona_id=persona_id,
            platform=Platform.TWITTER,
            username=username,
            platform_user_id=platform_user_id,
            profile_url=f"https://twitter.com/{username}",
            session_cookies=credentials,  # Using this field for API credentials
            is_connected=True,
            is_primary=True,
        )
        session.add(account)
        await session.commit()
        
        print(f"\n✅ Twitter account @{username} connected to {persona.name}!")
        return True


async def main():
    """Interactive setup wizard."""
    print("\n" + "=" * 60)
    print("🐦 Twitter/X Account Connection Wizard")
    print("=" * 60)
    
    print("\n📝 Before you start, you'll need Twitter API credentials.")
    print("   Get them from: https://developer.twitter.com/en/portal/dashboard")
    print("\n   Required credentials:")
    print("   • API Key (Consumer Key)")
    print("   • API Secret (Consumer Secret)")
    print("   • Access Token")
    print("   • Access Token Secret")
    print("   • Bearer Token (optional, for read-only operations)")
    
    # Initialize database
    await init_db()
    
    # List personas
    personas = await list_personas()
    if not personas:
        return
    
    # Get persona selection
    print("\nEnter the ID of the persona to connect:")
    persona_id = input("> ").strip()
    
    # Get API credentials
    print("\n🔑 Enter your Twitter API credentials:")
    
    print("\nAPI Key (Consumer Key):")
    api_key = input("> ").strip()
    
    print("\nAPI Secret (Consumer Secret):")
    import getpass
    api_secret = getpass.getpass("> ")
    
    print("\nAccess Token:")
    access_token = input("> ").strip()
    
    print("\nAccess Token Secret:")
    access_token_secret = getpass.getpass("> ")
    
    print("\nBearer Token (press Enter to skip):")
    bearer_token = input("> ").strip() or None
    
    # Verify credentials
    print("\n🔍 Verifying credentials...")
    valid, info = await verify_twitter_credentials(
        api_key, api_secret, access_token, access_token_secret, bearer_token
    )
    
    if not valid:
        print("\n❌ Could not verify Twitter credentials.")
        print("   Please check your API keys and tokens.")
        print("   Make sure your app has Read and Write permissions.")
        return
    
    username = info.get("username", "unknown")
    user_id = info.get("user_id")
    profile = info.get("profile")
    
    print(f"\n✅ Credentials verified!")
    print(f"   Account: @{username}")
    if profile:
        print(f"   Name: {profile.display_name}")
        print(f"   Followers: {profile.follower_count:,}")
        print(f"   Following: {profile.following_count:,}")
        print(f"   Tweets: {profile.post_count:,}")
    
    # Confirm connection
    print(f"\nConnect @{username} to the selected persona? (y/n):")
    if input("> ").strip().lower() != 'y':
        print("❌ Connection cancelled.")
        return
    
    # Connect account
    await connect_twitter(
        persona_id=persona_id,
        username=username,
        api_key=api_key,
        api_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
        bearer_token=bearer_token,
        platform_user_id=user_id,
    )
    
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

