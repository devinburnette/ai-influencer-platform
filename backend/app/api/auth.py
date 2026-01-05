"""Authentication API endpoints for platform connections."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.config import get_settings
from app.database import get_db
from app.models.persona import Persona
from app.models.platform_account import PlatformAccount, Platform
from app.services.platforms.fanvue.browser import FanvueBrowser

router = APIRouter()
settings = get_settings()
logger = structlog.get_logger()


class FanvueConnectRequest(BaseModel):
    """Request to connect Fanvue account."""
    persona_id: str
    email: EmailStr
    password: str


class FanvueConnectResponse(BaseModel):
    """Response after connecting Fanvue account."""
    success: bool
    message: str
    username: Optional[str] = None


class FanvueStatusResponse(BaseModel):
    """Fanvue connection status."""
    connected: bool
    username: Optional[str] = None
    profile_url: Optional[str] = None
    last_sync_at: Optional[str] = None


# ===== Fanvue Browser-Based Authentication =====

@router.post("/fanvue/connect", response_model=FanvueConnectResponse)
async def connect_fanvue(
    request: FanvueConnectRequest,
    db: AsyncSession = Depends(get_db),
):
    """Connect a Fanvue account to a persona using browser automation.
    
    This endpoint uses Playwright to log in to Fanvue and establish a session.
    The session cookies are stored locally for future automation.
    """
    # Verify persona exists
    result = await db.execute(
        select(Persona).where(Persona.id == UUID(request.persona_id))
    )
    persona = result.scalar_one_or_none()
    
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Persona not found",
        )
    
    browser = None
    try:
        # Create browser session using persona ID as session identifier
        browser = FanvueBrowser(
            session_id=request.persona_id,
            headless=True,
        )
        
        # Attempt login
        success = await browser.login(request.email, request.password)
        
        if not success:
            await browser.close()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to log in to Fanvue. Please check your credentials.",
            )
        
        # Get username
        username = await browser.get_username() or request.email.split("@")[0]
        
        # Close browser (session is saved to disk)
        await browser.close()
        
        # Check for existing Fanvue account for this persona
        existing_result = await db.execute(
            select(PlatformAccount).where(
                PlatformAccount.persona_id == persona.id,
                PlatformAccount.platform == Platform.FANVUE,
            )
        )
        account = existing_result.scalar_one_or_none()
        
        if account:
            # Update existing account
            account.username = username
            account.is_connected = True
            account.connection_error = None
            # Store email for re-authentication if needed (encrypted in production)
            account.access_token = request.email  # Using access_token field for email
        else:
            # Create new account
            account = PlatformAccount(
                persona_id=persona.id,
                platform=Platform.FANVUE,
                username=username,
                profile_url=f"https://www.fanvue.com/{username}",
                access_token=request.email,  # Store email for re-auth
                is_connected=True,
            )
            db.add(account)
        
        await db.commit()
        
        logger.info(
            "Fanvue account connected via browser automation",
            persona_id=request.persona_id,
            username=username,
        )
        
        return FanvueConnectResponse(
            success=True,
            message="Successfully connected to Fanvue",
            username=username,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Fanvue connection failed", error=str(e))
        if browser:
            await browser.close()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to connect to Fanvue: {str(e)}",
        )


@router.post("/fanvue/{persona_id}/verify")
async def verify_fanvue_connection(
    persona_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Verify that the Fanvue session is still valid.
    
    Checks if the stored browser session can still access Fanvue.
    """
    # Verify persona exists
    result = await db.execute(
        select(Persona).where(Persona.id == UUID(persona_id))
    )
    persona = result.scalar_one_or_none()
    
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Persona not found",
        )
    
    # Check for existing Fanvue account
    account_result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.persona_id == persona.id,
            PlatformAccount.platform == Platform.FANVUE,
        )
    )
    account = account_result.scalar_one_or_none()
    
    if not account or not account.is_connected:
        return {
            "valid": False,
            "message": "No Fanvue account connected",
        }
    
    browser = None
    try:
        browser = FanvueBrowser(
            session_id=persona_id,
            headless=True,
        )
        
        # Load cookies from database BEFORE checking login status
        if account.session_cookies:
            if isinstance(account.session_cookies, list):
                await browser.set_cookies_from_list(account.session_cookies)
            elif isinstance(account.session_cookies, dict):
                await browser.set_cookies_from_db(account.session_cookies)
            logger.info(
                "Loaded cookies for Fanvue validation",
                persona_id=persona_id,
                cookie_count=len(account.session_cookies) if account.session_cookies else 0,
            )
        else:
            # No cookies stored - definitely not valid
            await browser.close()
            return {
                "valid": False,
                "message": "No session cookies stored. Please reconnect to Fanvue.",
            }
        
        is_logged_in = await browser.is_logged_in()
        await browser.close()
        
        if not is_logged_in:
            # Mark connection_error but keep is_connected for now
            # to avoid disconnecting on transient issues
            account.connection_error = "Session may be expired - try reconnecting"
            await db.commit()
            
            return {
                "valid": False,
                "message": "Fanvue session expired. Please reconnect.",
            }
        
        # Session is valid - clear any previous errors
        if account.connection_error:
            account.connection_error = None
            await db.commit()
        
        return {
            "valid": True,
            "message": "Fanvue session is valid",
            "username": account.username,
        }
        
    except Exception as e:
        logger.error("Fanvue verification failed", error=str(e))
        if browser:
            await browser.close()
        return {
            "valid": False,
            "message": f"Verification failed: {str(e)}",
        }


@router.delete("/fanvue/{persona_id}")
async def disconnect_fanvue(
    persona_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Disconnect Fanvue account from a persona.
    
    Removes the stored session and marks the account as disconnected.
    """
    result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.persona_id == UUID(persona_id),
            PlatformAccount.platform == Platform.FANVUE,
        )
    )
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Fanvue account found for this persona",
        )
    
    # Mark as disconnected
    account.is_connected = False
    account.access_token = None
    account.refresh_token = None
    
    await db.commit()
    
    # Clean up browser session files
    try:
        import shutil
        from pathlib import Path
        session_dir = Path(f"/tmp/fanvue_sessions/{persona_id}")
        if session_dir.exists():
            shutil.rmtree(session_dir)
    except Exception as e:
        logger.warning("Failed to clean up Fanvue session files", error=str(e))
    
    return {"success": True, "message": "Fanvue account disconnected"}


@router.get("/fanvue/{persona_id}/status", response_model=FanvueStatusResponse)
async def get_fanvue_status(
    persona_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get Fanvue connection status for a persona."""
    result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.persona_id == UUID(persona_id),
            PlatformAccount.platform == Platform.FANVUE,
        )
    )
    account = result.scalar_one_or_none()
    
    if not account:
        return FanvueStatusResponse(
            connected=False,
            username=None,
        )
    
    return FanvueStatusResponse(
        connected=account.is_connected,
        username=account.username,
        profile_url=account.profile_url,
        last_sync_at=account.last_sync_at.isoformat() if account.last_sync_at else None,
    )
