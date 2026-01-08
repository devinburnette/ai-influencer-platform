#!/usr/bin/env python3
"""
Script to manually trigger content generation and posting.
Run with: docker-compose exec backend python scripts/trigger_post.py
"""

import sys
import asyncio
from pathlib import Path

# Add the backend directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.database import async_session_maker, init_db
from app.models.persona import Persona
from app.models.content import Content
from app.models.platform_account import PlatformAccount, Platform


async def list_personas_with_accounts():
    """List personas that have connected social media accounts."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Persona, PlatformAccount)
            .outerjoin(PlatformAccount)
            .where(PlatformAccount.is_connected == True)
        )
        rows = result.all()
        
        if not rows:
            print("\n❌ No personas with connected accounts found.")
            print("   Run: docker-compose exec backend python scripts/connect_twitter.py")
            print("   Or:  docker-compose exec backend python scripts/connect_instagram.py")
            return []
        
        print("\n📋 Personas with Connected Accounts:")
        print("-" * 60)
        for persona, account in rows:
            platform_emoji = "🐦" if account.platform == Platform.TWITTER else "📸"
            status = "✅" if account.is_connected else "⏸️"
            print(f"  {persona.id}: {persona.name}")
            print(f"     └─ {platform_emoji} @{account.username} ({account.platform.value}) {status}")
        print("-" * 60)
        return [(p, a) for p, a in rows]


async def list_content_for_persona(persona_id: str):
    """List content for a persona."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Content)
            .where(Content.persona_id == persona_id)
            .order_by(Content.created_at.desc())
            .limit(10)
        )
        contents = result.scalars().all()
        
        if not contents:
            print(f"\n📭 No content found for this persona.")
            return []
        
        print(f"\n📝 Recent Content:")
        print("-" * 60)
        for c in contents:
            status_emoji = {
                "draft": "📝",
                "pending_review": "👀",
                "approved": "✅",
                "scheduled": "📅",
                "posted": "🚀",
                "failed": "❌"
            }.get(c.status.value if hasattr(c.status, 'value') else str(c.status), "❓")
            caption_preview = c.caption[:50] + "..." if len(c.caption) > 50 else c.caption
            print(f"  {c.id}: {status_emoji} [{c.status.value if hasattr(c.status, 'value') else c.status}] {caption_preview}")
        print("-" * 60)
        return contents


async def generate_content(persona_id: str):
    """Generate new content for a persona."""
    print("\n🤖 Generating content...")
    
    # Import here to avoid circular imports
    from app.services.ai.content_generator import ContentGenerator
    from app.models.persona import Persona
    from app.models.content import Content, ContentStatus
    
    async with async_session_maker() as session:
        # Get persona
        result = await session.execute(
            select(Persona).where(Persona.id == persona_id)
        )
        persona = result.scalar_one_or_none()
        
        if not persona:
            print(f"❌ Persona not found")
            return None
        
        try:
            # Generate content
            generator = ContentGenerator()
            content_data = await generator.generate_post(persona)
            
            # Create content record
            content = Content(
                persona_id=persona_id,
                caption=content_data["caption"],
                hashtags=content_data["hashtags"],
                media_urls=[],
                status=ContentStatus.APPROVED,  # Auto-approve for manual trigger
            )
            session.add(content)
            await session.commit()
            await session.refresh(content)
            
            print(f"\n✅ Content generated!")
            print("-" * 60)
            print(f"Caption: {content.caption}")
            print(f"Hashtags: {' '.join('#' + h for h in content.hashtags)}")
            print("-" * 60)
            
            return content
            
        except Exception as e:
            print(f"\n❌ Error generating content: {e}")
            print("   Make sure your AI API key is configured in .env")
            return None


async def post_content(content_id: str):
    """Post content to the connected platform."""
    from app.models.content import ContentStatus
    from app.services.platforms.registry import PlatformRegistry
    
    async with async_session_maker() as session:
        # Get content with persona
        result = await session.execute(
            select(Content, Persona)
            .join(Persona, Content.persona_id == Persona.id)
            .where(Content.id == content_id)
        )
        row = result.first()
        
        if not row:
            print("❌ Content not found")
            return False
        
        content, persona = row
        
        # Get connected platform account (prefer Twitter)
        account = None
        for platform in [Platform.TWITTER, Platform.INSTAGRAM]:
            account_result = await session.execute(
                select(PlatformAccount).where(
                    PlatformAccount.persona_id == persona.id,
                    PlatformAccount.platform == platform,
                    PlatformAccount.is_connected == True,
                )
            )
            account = account_result.scalar_one_or_none()
            if account:
                break
        
        if not account:
            print("❌ No connected platform account found")
            return False
        
        platform_name = account.platform.value
        platform_emoji = "🐦" if platform_name == "twitter" else "📸"
        print(f"\n📤 Posting to {platform_emoji} {platform_name.title()}...")
        
        try:
            # Create adapter based on platform
            if platform_name == "twitter":
                creds = account.session_cookies or {}
                adapter = PlatformRegistry.create_adapter(
                    "twitter",
                    api_key=creds.get("api_key"),
                    api_secret=creds.get("api_secret"),
                    access_token=creds.get("access_token"),
                    access_token_secret=creds.get("access_token_secret"),
                    bearer_token=creds.get("bearer_token"),
                )
                
                # Authenticate
                if not await adapter.authenticate(creds):
                    raise Exception("Twitter authentication failed")
                    
            elif platform_name == "instagram":
                from app.services.platforms.instagram.adapter import InstagramAdapter
                adapter = InstagramAdapter(
                    access_token=account.access_token,
                    instagram_account_id=account.platform_user_id,
                    session_cookies=account.session_cookies,
                )
                
                credentials = {}
                if account.access_token:
                    credentials["access_token"] = account.access_token
                    credentials["instagram_account_id"] = account.platform_user_id
                if account.session_cookies:
                    credentials["session_cookies"] = account.session_cookies
                    
                if not await adapter.authenticate(credentials):
                    raise Exception("Instagram authentication failed")
            else:
                raise Exception(f"Unsupported platform: {platform_name}")
            
            # Post content
            result = await adapter.post_content(
                caption=content.caption,
                hashtags=content.hashtags,
                media_paths=content.media_urls or None,
            )
            
            await adapter.close()
            
            if result.success:
                content.status = ContentStatus.POSTED
                content.platform_post_id = result.post_id
                content.platform_url = result.url
                await session.commit()
                
                print(f"\n🎉 Successfully posted to {platform_name.title()}!")
                print(f"   Post ID: {result.post_id}")
                if result.url:
                    print(f"   URL: {result.url}")
                return True
            else:
                print(f"\n❌ Posting failed: {result.error_message}")
                content.status = ContentStatus.FAILED
                await session.commit()
                return False
                
        except Exception as e:
            print(f"\n❌ Error posting: {e}")
            return False


async def main():
    """Interactive posting wizard."""
    print("\n" + "=" * 60)
    print("📤 Manual Post Trigger")
    print("=" * 60)
    
    # Initialize database
    await init_db()
    
    # List personas with accounts
    personas_with_accounts = await list_personas_with_accounts()
    if not personas_with_accounts:
        return
    
    # Get persona selection
    print("\nEnter the persona ID:")
    persona_id = input("> ").strip()
    
    # Show content options
    print("\nWhat would you like to do?")
    print("  1. Generate new content and post it")
    print("  2. Post existing content")
    print("  3. Just generate content (don't post)")
    choice = input("> ").strip()
    
    if choice == "1":
        # Generate and post
        content = await generate_content(persona_id)
        if content:
            print("\nPost this content now? (y/n)")
            if input("> ").strip().lower() == 'y':
                await post_content(str(content.id))
    
    elif choice == "2":
        # List and post existing
        contents = await list_content_for_persona(persona_id)
        if contents:
            print("\nEnter the content ID to post:")
            content_id = input("> ").strip()
            await post_content(content_id)
    
    elif choice == "3":
        # Just generate
        await generate_content(persona_id)
    
    else:
        print("❌ Invalid option")


if __name__ == "__main__":
    asyncio.run(main())


