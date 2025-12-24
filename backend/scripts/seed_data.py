#!/usr/bin/env python3
"""Seed script to create sample personas for testing."""

import asyncio
import sys
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import async_session_maker, init_db
from app.models.persona import Persona, PersonaVoice
from app.models.content import Content, ContentStatus


async def seed_personas():
    """Create sample personas for testing."""
    
    await init_db()
    
    personas_data = [
        {
            "name": "Alex FitLife",
            "bio": "🏋️ Fitness enthusiast | Personal trainer | Helping you become your best self one workout at a time 💪",
            "niche": ["fitness", "health", "workout", "nutrition", "motivation"],
            "voice": PersonaVoice(
                tone="inspirational",
                vocabulary_level="casual",
                emoji_usage="moderate",
                hashtag_style="relevant",
                signature_phrases=["Let's get it!", "No excuses!", "One day at a time"],
            ),
            "ai_provider": "openai",
        },
        {
            "name": "TechTina",
            "bio": "👩‍💻 Software Engineer | Tech reviewer | Making technology accessible for everyone 🚀",
            "niche": ["technology", "programming", "gadgets", "AI", "startups"],
            "voice": PersonaVoice(
                tone="friendly",
                vocabulary_level="sophisticated",
                emoji_usage="minimal",
                hashtag_style="minimal",
                signature_phrases=["Tech tip of the day:", "Let's break this down"],
            ),
            "ai_provider": "anthropic",
        },
        {
            "name": "Chef Marco",
            "bio": "👨‍🍳 Home cooking made simple | Recipe developer | Food is love on a plate 🍝",
            "niche": ["cooking", "recipes", "foodie", "homemade", "italian"],
            "voice": PersonaVoice(
                tone="friendly",
                vocabulary_level="casual",
                emoji_usage="heavy",
                hashtag_style="comprehensive",
                signature_phrases=["Buon appetito!", "The secret ingredient is love"],
            ),
            "ai_provider": "openai",
        },
    ]
    
    async with async_session_maker() as db:
        for data in personas_data:
            voice = data.pop("voice")
            persona = Persona(**data)
            persona.voice = voice
            db.add(persona)
            print(f"Created persona: {persona.name}")
        
        await db.commit()
    
    print("\n✅ Seed data created successfully!")
    print("You can now access the dashboard at http://localhost:3000")


async def seed_sample_content():
    """Create sample content for testing."""
    
    async with async_session_maker() as db:
        from sqlalchemy import select
        
        result = await db.execute(select(Persona).limit(1))
        persona = result.scalar_one_or_none()
        
        if not persona:
            print("No personas found. Run seed_personas first.")
            return
        
        content_samples = [
            {
                "caption": "Rise and grind! 🌅 There's no better feeling than crushing a workout before the world wakes up. What's your morning routine?",
                "hashtags": ["morningmotivation", "fitness", "workout", "riseandgrind", "fitlife"],
                "status": ContentStatus.PENDING_REVIEW,
            },
            {
                "caption": "Consistency beats intensity every single time. 💪 Focus on showing up, even when you don't feel like it. That's where the magic happens.",
                "hashtags": ["consistency", "motivation", "fitness", "mindset", "growth"],
                "status": ContentStatus.SCHEDULED,
            },
            {
                "caption": "Meal prep Sunday! 🥗 Spending a few hours today to set yourself up for a week of healthy eating. Your future self will thank you!",
                "hashtags": ["mealprep", "healthyeating", "nutrition", "sundayfunday", "fitfood"],
                "status": ContentStatus.POSTED,
            },
        ]
        
        for data in content_samples:
            content = Content(
                persona_id=persona.id,
                auto_generated=True,
                **data,
            )
            db.add(content)
            print(f"Created content: {data['caption'][:50]}...")
        
        await db.commit()
    
    print("\n✅ Sample content created!")


async def main():
    """Run all seed functions."""
    print("🌱 Seeding database...\n")
    
    await seed_personas()
    await seed_sample_content()
    
    print("\n🎉 Database seeding complete!")


if __name__ == "__main__":
    asyncio.run(main())

