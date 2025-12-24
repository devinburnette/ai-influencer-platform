"""Content generation and management tasks."""

import asyncio
from typing import Optional
from uuid import UUID

import structlog
from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models.persona import Persona
from app.models.content import Content, ContentStatus
from app.services.ai.content_generator import ContentGenerator

logger = structlog.get_logger()


def run_async(coro):
    """Run async code in sync context."""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@shared_task(name="app.workers.tasks.content_tasks.generate_content_for_persona")
def generate_content_for_persona(
    persona_id: str,
    topic: Optional[str] = None,
) -> dict:
    """Generate content for a specific persona.
    
    Args:
        persona_id: UUID of the persona
        topic: Optional specific topic to generate about
        
    Returns:
        Dictionary with generation result
    """
    return run_async(_generate_content_for_persona(persona_id, topic))


async def _generate_content_for_persona(
    persona_id: str,
    topic: Optional[str] = None,
) -> dict:
    """Async implementation of content generation."""
    async with async_session_maker() as db:
        # Get persona
        result = await db.execute(
            select(Persona).where(Persona.id == UUID(persona_id))
        )
        persona = result.scalar_one_or_none()
        
        if not persona:
            logger.error("Persona not found", persona_id=persona_id)
            return {"success": False, "error": "Persona not found"}
        
        if not persona.is_active:
            logger.info("Persona is paused, skipping", persona_id=persona_id)
            return {"success": False, "error": "Persona is paused"}
        
        try:
            # Generate content
            generator = ContentGenerator()
            generated = await generator.generate_post(persona, topic=topic)
            
            # Determine initial status
            status = (
                ContentStatus.SCHEDULED
                if persona.auto_approve_content
                else ContentStatus.PENDING_REVIEW
            )
            
            # Create content record
            content = Content(
                persona_id=persona.id,
                caption=generated["caption"],
                hashtags=generated.get("hashtags", []),
                auto_generated=True,
                status=status,
            )
            
            db.add(content)
            await db.commit()
            await db.refresh(content)
            
            logger.info(
                "Content generated",
                persona=persona.name,
                content_id=str(content.id),
                status=status.value,
            )
            
            return {
                "success": True,
                "content_id": str(content.id),
                "status": status.value,
            }
            
        except Exception as e:
            logger.error(
                "Content generation failed",
                persona_id=persona_id,
                error=str(e),
            )
            return {"success": False, "error": str(e)}


@shared_task(name="app.workers.tasks.content_tasks.generate_content_batch")
def generate_content_batch() -> dict:
    """Generate content for all active personas that need it.
    
    Returns:
        Dictionary with batch results
    """
    return run_async(_generate_content_batch())


async def _generate_content_batch() -> dict:
    """Async implementation of batch content generation."""
    results = {"generated": 0, "skipped": 0, "errors": 0}
    
    async with async_session_maker() as db:
        # Get active personas
        result = await db.execute(
            select(Persona).where(Persona.is_active == True)
        )
        personas = result.scalars().all()
        
        for persona in personas:
            # Check if persona needs content
            pending_result = await db.execute(
                select(Content)
                .where(
                    Content.persona_id == persona.id,
                    Content.status.in_([
                        ContentStatus.PENDING_REVIEW,
                        ContentStatus.SCHEDULED,
                    ]),
                )
            )
            pending_count = len(pending_result.scalars().all())
            
            # Skip if enough content in queue
            if pending_count >= 5:
                logger.info(
                    "Enough content in queue",
                    persona=persona.name,
                    pending=pending_count,
                )
                results["skipped"] += 1
                continue
            
            try:
                # Generate new content
                generator = ContentGenerator()
                generated = await generator.generate_post(persona)
                
                status = (
                    ContentStatus.SCHEDULED
                    if persona.auto_approve_content
                    else ContentStatus.PENDING_REVIEW
                )
                
                content = Content(
                    persona_id=persona.id,
                    caption=generated["caption"],
                    hashtags=generated.get("hashtags", []),
                    auto_generated=True,
                    status=status,
                )
                
                db.add(content)
                results["generated"] += 1
                
                logger.info(
                    "Batch content generated",
                    persona=persona.name,
                )
                
            except Exception as e:
                logger.error(
                    "Batch generation failed for persona",
                    persona=persona.name,
                    error=str(e),
                )
                results["errors"] += 1
        
        await db.commit()
    
    logger.info("Batch content generation complete", results=results)
    return results


@shared_task(name="app.workers.tasks.content_tasks.generate_story_ideas")
def generate_story_ideas(persona_id: str, count: int = 5) -> dict:
    """Generate story ideas for a persona.
    
    Args:
        persona_id: UUID of the persona
        count: Number of ideas to generate
        
    Returns:
        Dictionary with generated ideas
    """
    return run_async(_generate_story_ideas(persona_id, count))


async def _generate_story_ideas(persona_id: str, count: int = 5) -> dict:
    """Async implementation of story idea generation."""
    async with async_session_maker() as db:
        result = await db.execute(
            select(Persona).where(Persona.id == UUID(persona_id))
        )
        persona = result.scalar_one_or_none()
        
        if not persona:
            return {"success": False, "error": "Persona not found"}
        
        try:
            generator = ContentGenerator()
            ideas = await generator.generate_story_ideas(persona, count)
            
            return {"success": True, "ideas": ideas}
            
        except Exception as e:
            logger.error(
                "Story idea generation failed",
                persona_id=persona_id,
                error=str(e),
            )
            return {"success": False, "error": str(e)}


@shared_task(name="app.workers.tasks.content_tasks.improve_content")
def improve_content(content_id: str, feedback: Optional[str] = None) -> dict:
    """Improve existing content based on feedback.
    
    Args:
        content_id: UUID of the content to improve
        feedback: Optional feedback for improvement
        
    Returns:
        Dictionary with improvement result
    """
    return run_async(_improve_content(content_id, feedback))


async def _improve_content(content_id: str, feedback: Optional[str] = None) -> dict:
    """Async implementation of content improvement."""
    async with async_session_maker() as db:
        # Get content
        result = await db.execute(
            select(Content).where(Content.id == UUID(content_id))
        )
        content = result.scalar_one_or_none()
        
        if not content:
            return {"success": False, "error": "Content not found"}
        
        # Get persona
        persona_result = await db.execute(
            select(Persona).where(Persona.id == content.persona_id)
        )
        persona = persona_result.scalar_one_or_none()
        
        if not persona:
            return {"success": False, "error": "Persona not found"}
        
        try:
            generator = ContentGenerator()
            improved = await generator.improve_caption(
                persona,
                content.caption,
                feedback,
            )
            
            # Update content
            content.caption = improved["caption"]
            content.hashtags = improved.get("hashtags", content.hashtags)
            
            await db.commit()
            
            return {
                "success": True,
                "improvements": improved.get("improvements", []),
            }
            
        except Exception as e:
            logger.error(
                "Content improvement failed",
                content_id=content_id,
                error=str(e),
            )
            return {"success": False, "error": str(e)}

