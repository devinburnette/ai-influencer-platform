"""Persona management API endpoints."""

from typing import List, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.persona import Persona, PersonaVoice

logger = structlog.get_logger()
router = APIRouter()


# Pydantic schemas
class VoiceConfig(BaseModel):
    """Voice configuration for a persona."""
    tone: str = Field(default="friendly", description="Communication tone")
    vocabulary_level: str = Field(default="casual", description="Vocabulary complexity")
    emoji_usage: str = Field(default="moderate", description="none, minimal, moderate, heavy")
    hashtag_style: str = Field(default="relevant", description="Hashtag strategy")
    signature_phrases: List[str] = Field(default_factory=list, description="Recurring phrases")


class PersonaCreate(BaseModel):
    """Schema for creating a new persona."""
    name: str = Field(..., min_length=1, max_length=100)
    bio: str = Field(..., max_length=500)
    niche: List[str] = Field(..., min_items=1, description="Areas of influence")
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    ai_provider: str = Field(default="openai", pattern="^(openai|anthropic)$")
    posting_schedule: str = Field(default="0 9,13,18 * * *", description="Cron expression")
    engagement_hours_start: int = Field(default=8, ge=0, le=23)
    engagement_hours_end: int = Field(default=22, ge=0, le=23)
    timezone: str = Field(default="UTC")
    auto_approve_content: bool = Field(default=False)
    is_active: bool = Field(default=True)
    higgsfield_character_id: Optional[str] = Field(None, description="Higgsfield Soul model character ID for image generation")
    # Custom prompt templates
    content_prompt_template: Optional[str] = Field(None, description="Custom system prompt for content generation. Supports placeholders: {name}, {bio}, {niche}, {tone}, etc.")
    comment_prompt_template: Optional[str] = Field(None, description="Custom system prompt for comment generation. Supports placeholders: {name}, {bio}, {niche}, {tone}, etc.")
    image_prompt_template: Optional[str] = Field(None, description="Custom prompt for image generation. Supports placeholders: {caption}, {niche}, {name}, {style_hints}")


class PersonaUpdate(BaseModel):
    """Schema for updating a persona."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    niche: Optional[List[str]] = None
    voice: Optional[VoiceConfig] = None
    ai_provider: Optional[str] = Field(None, pattern="^(openai|anthropic)$")
    posting_schedule: Optional[str] = None
    engagement_hours_start: Optional[int] = Field(None, ge=0, le=23)
    engagement_hours_end: Optional[int] = Field(None, ge=0, le=24)  # 24 = end of day
    timezone: Optional[str] = None
    auto_approve_content: Optional[bool] = None
    is_active: Optional[bool] = None
    higgsfield_character_id: Optional[str] = None
    content_prompt_template: Optional[str] = None
    comment_prompt_template: Optional[str] = None
    image_prompt_template: Optional[str] = None


class PersonaResponse(BaseModel):
    """Schema for persona response."""
    id: UUID
    name: str
    bio: str
    niche: List[str]
    voice: VoiceConfig
    ai_provider: str
    posting_schedule: str
    engagement_hours_start: int
    engagement_hours_end: int
    timezone: str
    auto_approve_content: bool
    is_active: bool
    follower_count: int
    following_count: int
    post_count: int
    # Daily engagement counters
    likes_today: int = 0
    comments_today: int = 0
    follows_today: int = 0
    # Higgsfield image generation
    higgsfield_character_id: Optional[str] = None
    # Custom prompt templates
    content_prompt_template: Optional[str] = None
    comment_prompt_template: Optional[str] = None
    image_prompt_template: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/", response_model=List[PersonaResponse])
async def list_personas(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """List all personas."""
    query = select(Persona)
    if active_only:
        query = query.where(Persona.is_active == True)
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    personas = result.scalars().all()
    
    return [_persona_to_response(p) for p in personas]


@router.post("/", response_model=PersonaResponse, status_code=status.HTTP_201_CREATED)
async def create_persona(
    persona_data: PersonaCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new AI persona."""
    # Create voice configuration
    voice = PersonaVoice(
        tone=persona_data.voice.tone,
        vocabulary_level=persona_data.voice.vocabulary_level,
        emoji_usage=persona_data.voice.emoji_usage,
        hashtag_style=persona_data.voice.hashtag_style,
        signature_phrases=persona_data.voice.signature_phrases,
    )
    
    persona = Persona(
        name=persona_data.name,
        bio=persona_data.bio,
        niche=persona_data.niche,
        voice=voice,
        ai_provider=persona_data.ai_provider,
        posting_schedule=persona_data.posting_schedule,
        engagement_hours_start=persona_data.engagement_hours_start,
        engagement_hours_end=persona_data.engagement_hours_end,
        timezone=persona_data.timezone,
        auto_approve_content=persona_data.auto_approve_content,
        is_active=persona_data.is_active,
        higgsfield_character_id=persona_data.higgsfield_character_id,
        content_prompt_template=persona_data.content_prompt_template,
        comment_prompt_template=persona_data.comment_prompt_template,
        image_prompt_template=persona_data.image_prompt_template,
    )
    
    db.add(persona)
    await db.flush()
    await db.refresh(persona)
    
    return _persona_to_response(persona)


@router.get("/{persona_id}", response_model=PersonaResponse)
async def get_persona(
    persona_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific persona by ID."""
    result = await db.execute(select(Persona).where(Persona.id == persona_id))
    persona = result.scalar_one_or_none()
    
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona {persona_id} not found",
        )
    
    return _persona_to_response(persona)


@router.patch("/{persona_id}", response_model=PersonaResponse)
async def update_persona(
    persona_id: UUID,
    persona_data: PersonaUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a persona."""
    result = await db.execute(select(Persona).where(Persona.id == persona_id))
    persona = result.scalar_one_or_none()
    
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona {persona_id} not found",
        )
    
    update_data = persona_data.model_dump(exclude_unset=True)
    
    if "voice" in update_data and update_data["voice"]:
        voice_data = update_data.pop("voice")
        persona.voice = PersonaVoice(**voice_data)
    
    for field, value in update_data.items():
        setattr(persona, field, value)
    
    await db.flush()
    await db.refresh(persona)
    
    return _persona_to_response(persona)


@router.delete("/{persona_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_persona(
    persona_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a persona and all associated data (content, engagements, platform accounts)."""
    from sqlalchemy import delete
    from app.models.content import Content
    from app.models.engagement import Engagement
    from app.models.platform_account import PlatformAccount
    
    result = await db.execute(select(Persona).where(Persona.id == persona_id))
    persona = result.scalar_one_or_none()
    
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona {persona_id} not found",
        )
    
    # Explicitly delete all associated data to ensure cleanup
    # This works even if database CASCADE constraints aren't set
    await db.execute(delete(Content).where(Content.persona_id == persona_id))
    await db.execute(delete(Engagement).where(Engagement.persona_id == persona_id))
    await db.execute(delete(PlatformAccount).where(PlatformAccount.persona_id == persona_id))
    
    # Now delete the persona
    await db.delete(persona)


@router.post("/{persona_id}/pause", response_model=PersonaResponse)
async def pause_persona(
    persona_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Pause all activity for a persona (kill switch)."""
    result = await db.execute(select(Persona).where(Persona.id == persona_id))
    persona = result.scalar_one_or_none()
    
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona {persona_id} not found",
        )
    
    persona.is_active = False
    await db.flush()
    await db.refresh(persona)
    
    return _persona_to_response(persona)


@router.post("/{persona_id}/resume", response_model=PersonaResponse)
async def resume_persona(
    persona_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Resume activity for a paused persona."""
    result = await db.execute(select(Persona).where(Persona.id == persona_id))
    persona = result.scalar_one_or_none()
    
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona {persona_id} not found",
        )
    
    persona.is_active = True
    await db.flush()
    await db.refresh(persona)
    
    return _persona_to_response(persona)


# Platform Account schemas
class PlatformAccountResponse(BaseModel):
    """Schema for platform account response."""
    id: UUID
    platform: str
    username: str
    platform_user_id: Optional[str]
    profile_url: Optional[str]
    is_connected: bool
    is_primary: bool
    last_sync_at: Optional[str]
    connection_error: Optional[str]
    engagement_enabled: bool = False  # True if session cookies exist for browser automation
    engagement_paused: bool = False  # True if engagement is paused for this platform
    posting_paused: bool = False  # True if posting is paused for this platform
    # Platform-specific stats
    follower_count: int = 0
    following_count: int = 0
    post_count: int = 0

    class Config:
        from_attributes = True


class TwitterOAuthStartResponse(BaseModel):
    """Response when starting Twitter OAuth."""
    authorization_url: str
    oauth_token: str  # Needed to complete the flow


class TwitterOAuthCompleteRequest(BaseModel):
    """Request to complete Twitter OAuth with PIN."""
    oauth_token: str
    pin: str = Field(..., min_length=1, max_length=10)


# In-memory storage for OAuth tokens (in production, use Redis)
_oauth_tokens: dict = {}


@router.get("/{persona_id}/accounts", response_model=List[PlatformAccountResponse])
async def list_platform_accounts(
    persona_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """List all connected platform accounts for a persona."""
    from app.models.platform_account import PlatformAccount
    
    # Verify persona exists
    result = await db.execute(select(Persona).where(Persona.id == persona_id))
    persona = result.scalar_one_or_none()
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona {persona_id} not found",
        )
    
    # Get accounts
    accounts_result = await db.execute(
        select(PlatformAccount).where(PlatformAccount.persona_id == persona_id)
    )
    accounts = accounts_result.scalars().all()
    
    return [
        PlatformAccountResponse(
            id=acc.id,
            platform=acc.platform.value,
            username=acc.username,
            platform_user_id=acc.platform_user_id,
            profile_url=acc.profile_url,
            is_connected=acc.is_connected,
            is_primary=acc.is_primary,
            last_sync_at=acc.last_sync_at.isoformat() if acc.last_sync_at else None,
            connection_error=acc.connection_error,
            engagement_enabled=bool(acc.session_cookies),  # True if browser session exists
            engagement_paused=getattr(acc, 'engagement_paused', False),
            posting_paused=getattr(acc, 'posting_paused', False),
            follower_count=acc.follower_count or 0,
            following_count=acc.following_count or 0,
            post_count=acc.post_count or 0,
        )
        for acc in accounts
    ]


@router.post("/{persona_id}/accounts/twitter/start-oauth", response_model=TwitterOAuthStartResponse)
async def start_twitter_oauth(
    persona_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Start the Twitter OAuth flow. Returns an authorization URL for the user."""
    import tweepy
    from app.config import get_settings
    from app.models.platform_account import PlatformAccount, Platform
    
    settings = get_settings()
    
    # Check Twitter app credentials are configured
    if not settings.twitter_api_key or not settings.twitter_api_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Twitter API credentials not configured. Set TWITTER_API_KEY and TWITTER_API_SECRET in your .env file.",
        )
    
    # Verify persona exists
    result = await db.execute(select(Persona).where(Persona.id == persona_id))
    persona = result.scalar_one_or_none()
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona {persona_id} not found",
        )
    
    # Check if Twitter account already connected
    existing = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.persona_id == persona_id,
            PlatformAccount.platform == Platform.TWITTER,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Twitter account already connected. Disconnect first to connect a different account.",
        )
    
    # Create OAuth handler for PIN-based auth (no callback URL)
    try:
        auth = tweepy.OAuth1UserHandler(
            settings.twitter_api_key,
            settings.twitter_api_secret,
            callback="oob"  # Out-of-band / PIN-based
        )
        authorization_url = auth.get_authorization_url()
        
        # Store the request token for later
        _oauth_tokens[auth.request_token["oauth_token"]] = {
            "oauth_token_secret": auth.request_token["oauth_token_secret"],
            "persona_id": str(persona_id),
        }
        
        return TwitterOAuthStartResponse(
            authorization_url=authorization_url,
            oauth_token=auth.request_token["oauth_token"],
        )
    except tweepy.TweepyException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start Twitter OAuth: {str(e)}",
        )


@router.post("/{persona_id}/accounts/twitter/complete-oauth", response_model=PlatformAccountResponse)
async def complete_twitter_oauth(
    persona_id: UUID,
    request: TwitterOAuthCompleteRequest,
    db: AsyncSession = Depends(get_db),
):
    """Complete the Twitter OAuth flow using the PIN from the user."""
    import tweepy
    from app.config import get_settings
    from app.models.platform_account import PlatformAccount, Platform
    
    settings = get_settings()
    
    # Retrieve the stored OAuth tokens
    if request.oauth_token not in _oauth_tokens:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth session expired or invalid. Please start the connection process again.",
        )
    
    stored_data = _oauth_tokens.pop(request.oauth_token)
    
    # Verify persona_id matches
    if stored_data["persona_id"] != str(persona_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth session does not match this persona.",
        )
    
    # Exchange PIN for access tokens
    try:
        auth = tweepy.OAuth1UserHandler(
            settings.twitter_api_key,
            settings.twitter_api_secret,
        )
        auth.request_token = {
            "oauth_token": request.oauth_token,
            "oauth_token_secret": stored_data["oauth_token_secret"],
        }
        
        access_token, access_token_secret = auth.get_access_token(request.pin)
        
        # Get user info
        auth.set_access_token(access_token, access_token_secret)
        api = tweepy.API(auth)
        user = api.verify_credentials()
        
        # Create platform account
        account = PlatformAccount(
            persona_id=persona_id,
            platform=Platform.TWITTER,
            username=user.screen_name,
            platform_user_id=str(user.id),
            access_token=access_token,
            refresh_token=access_token_secret,  # Store secret in refresh_token field
            is_connected=True,
            is_primary=True,
            profile_url=f"https://twitter.com/{user.screen_name}",
        )
        
        db.add(account)
        await db.flush()
        await db.refresh(account)
        
        return PlatformAccountResponse(
            id=account.id,
            platform=account.platform.value,
            username=account.username,
            platform_user_id=account.platform_user_id,
            profile_url=account.profile_url,
            is_connected=account.is_connected,
            is_primary=account.is_primary,
            last_sync_at=account.last_sync_at.isoformat() if account.last_sync_at else None,
            connection_error=account.connection_error,
            engagement_enabled=bool(account.session_cookies),
            engagement_paused=getattr(account, 'engagement_paused', False),
            posting_paused=getattr(account, 'posting_paused', False),
        )
    except tweepy.TweepyException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to complete Twitter OAuth: {str(e)}. Make sure the PIN is correct.",
        )


class InstagramConnectRequest(BaseModel):
    """Request to connect an Instagram account."""
    username: str
    instagram_account_id: str
    access_token: str


@router.post("/{persona_id}/accounts/instagram/connect", response_model=PlatformAccountResponse)
async def connect_instagram_account(
    persona_id: UUID,
    connect_data: InstagramConnectRequest,
    db: AsyncSession = Depends(get_db),
):
    """Connect an Instagram Business account to a persona."""
    from app.models.platform_account import PlatformAccount, Platform
    
    # Check persona exists
    result = await db.execute(select(Persona).where(Persona.id == persona_id))
    persona = result.scalar_one_or_none()
    
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Persona not found",
        )
    
    # Check if Instagram account already connected
    result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.persona_id == persona_id,
            PlatformAccount.platform == Platform.INSTAGRAM,
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An Instagram account is already connected to this persona",
        )
    
    # Verify the token works by making a test API call
    import httpx
    from app.config import get_settings
    api_settings = get_settings()
    username = connect_data.username
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://graph.facebook.com/{api_settings.meta_graph_api_version}/{connect_data.instagram_account_id}",
                params={
                    "fields": "id,username",
                    "access_token": connect_data.access_token,
                },
            )
            if response.status_code == 200:
                ig_data = response.json()
                # Use username from API if available
                username = ig_data.get("username", connect_data.username)
            else:
                # Log the error but continue - token might have limited permissions
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                logger.warning(
                    "Instagram API verification returned non-200",
                    status_code=response.status_code,
                    error=error_data,
                )
                # If it's a permissions error, we can still try to save the account
                # The actual posting will validate permissions
                if response.status_code >= 500:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail=f"Instagram API is temporarily unavailable: {error_data.get('error', {}).get('message', 'Unknown error')}",
                    )
    except httpx.HTTPError as e:
        logger.warning("Failed to verify Instagram token, proceeding anyway", error=str(e))
        # Continue anyway - we'll validate when actually posting
    
    # Create the platform account
    account = PlatformAccount(
        persona_id=persona_id,
        platform=Platform.INSTAGRAM,
        username=username,
        platform_user_id=connect_data.instagram_account_id,
        access_token=connect_data.access_token,
        is_connected=True,
        is_primary=True,
        profile_url=f"https://instagram.com/{username}",
    )
    
    db.add(account)
    await db.flush()
    await db.refresh(account)
    
    return PlatformAccountResponse(
        id=account.id,
        platform=account.platform.value,
        username=account.username,
        platform_user_id=account.platform_user_id,
        profile_url=account.profile_url,
        is_connected=account.is_connected,
        is_primary=account.is_primary,
        last_sync_at=account.last_sync_at.isoformat() if account.last_sync_at else None,
        connection_error=account.connection_error,
        engagement_enabled=bool(account.session_cookies),
        engagement_paused=getattr(account, 'engagement_paused', False),
        posting_paused=getattr(account, 'posting_paused', False),
    )


@router.delete("/{persona_id}/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_platform_account(
    persona_id: UUID,
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Disconnect a platform account from a persona."""
    from app.models.platform_account import PlatformAccount
    
    result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.id == account_id,
            PlatformAccount.persona_id == persona_id,
        )
    )
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Platform account not found",
        )
    
    await db.delete(account)


class TwitterBrowserLoginRequest(BaseModel):
    """Request for Twitter browser login."""
    username: str
    password: str


class TwitterBrowserLoginResponse(BaseModel):
    """Response for Twitter browser login."""
    success: bool
    message: str
    has_cookies: bool = False


@router.post(
    "/{persona_id}/accounts/twitter/browser-login",
    response_model=TwitterBrowserLoginResponse,
)
async def twitter_browser_login(
    persona_id: UUID,
    request: TwitterBrowserLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Login to Twitter via browser to capture session cookies.
    
    This allows engagement features to work even without paid API access.
    The session cookies are stored and used for browser-based automation.
    
    Note: This may trigger 2FA or security challenges from Twitter.
    """
    from app.models.platform_account import PlatformAccount, Platform
    from app.services.platforms.twitter.browser import TwitterBrowser
    
    # Get persona
    result = await db.execute(select(Persona).where(Persona.id == persona_id))
    persona = result.scalar_one_or_none()
    
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Persona not found",
        )
    
    # Get existing Twitter account for this persona
    result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.persona_id == persona_id,
            PlatformAccount.platform == Platform.TWITTER,
        )
    )
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Twitter account connected. Connect via OAuth first.",
        )
    
    # Initialize browser and attempt login
    browser = TwitterBrowser()
    try:
        success = await browser.login(request.username, request.password)
        
        if success:
            # Get cookies and store them
            cookies = await browser.get_cookies()
            
            if cookies:
                account.session_cookies = cookies
                await db.commit()
                
                logger.info(
                    "Twitter browser login successful",
                    persona=persona.name,
                    username=request.username,
                    cookie_count=len(cookies),
                )
                
                return TwitterBrowserLoginResponse(
                    success=True,
                    message="Login successful! Browser automation is now available for engagement.",
                    has_cookies=True,
                )
            else:
                return TwitterBrowserLoginResponse(
                    success=False,
                    message="Login succeeded but no cookies captured.",
                    has_cookies=False,
                )
        else:
            return TwitterBrowserLoginResponse(
                success=False,
                message="Login failed. Check credentials or handle security challenge manually.",
                has_cookies=False,
            )
    except Exception as e:
        logger.error("Twitter browser login error", error=str(e))
        return TwitterBrowserLoginResponse(
            success=False,
            message=f"Login error: {str(e)}",
            has_cookies=False,
        )
    finally:
        await browser.close()


class ManualCookiesRequest(BaseModel):
    """Request for manually setting session cookies."""
    cookies: str  # JSON string of cookies or raw cookie string


@router.post(
    "/{persona_id}/accounts/twitter/set-cookies",
    response_model=TwitterBrowserLoginResponse,
)
async def set_twitter_cookies(
    persona_id: UUID,
    request: ManualCookiesRequest,
    db: AsyncSession = Depends(get_db),
):
    """Manually set Twitter session cookies for browser automation.
    
    This is an alternative to browser login when automated login fails.
    User can export cookies from their browser and paste them here.
    
    Accepts either:
    - JSON object: {"auth_token": "xxx", "ct0": "xxx", ...}
    - Cookie string: "auth_token=xxx; ct0=xxx; ..."
    """
    import json
    from app.models.platform_account import PlatformAccount, Platform
    
    # Get persona
    result = await db.execute(select(Persona).where(Persona.id == persona_id))
    persona = result.scalar_one_or_none()
    
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Persona not found",
        )
    
    # Get existing Twitter account for this persona
    result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.persona_id == persona_id,
            PlatformAccount.platform == Platform.TWITTER,
        )
    )
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Twitter account connected. Connect via OAuth first.",
        )
    
    # Parse cookies
    try:
        cookies_str = request.cookies.strip()
        
        # Try parsing as JSON first
        if cookies_str.startswith("{"):
            cookies = json.loads(cookies_str)
        else:
            # Parse cookie string format: "name=value; name2=value2"
            cookies = {}
            for part in cookies_str.split(";"):
                part = part.strip()
                if "=" in part:
                    name, value = part.split("=", 1)
                    cookies[name.strip()] = value.strip()
        
        # Validate we have essential cookies
        essential_cookies = ["auth_token", "ct0"]
        missing = [c for c in essential_cookies if c not in cookies]
        
        if missing:
            return TwitterBrowserLoginResponse(
                success=False,
                message=f"Missing essential cookies: {', '.join(missing)}. Required: auth_token, ct0",
                has_cookies=False,
            )
        
        # Store cookies
        account.session_cookies = cookies
        await db.commit()
        
        logger.info(
            "Twitter cookies set manually",
            persona=persona.name,
            cookie_count=len(cookies),
        )
        
        return TwitterBrowserLoginResponse(
            success=True,
            message=f"Cookies saved! {len(cookies)} cookies stored. Engagement is now enabled.",
            has_cookies=True,
        )
        
    except json.JSONDecodeError:
        return TwitterBrowserLoginResponse(
            success=False,
            message="Invalid cookie format. Use JSON or 'name=value; name2=value2' format.",
            has_cookies=False,
        )
    except Exception as e:
        logger.error("Set cookies error", error=str(e))
        return TwitterBrowserLoginResponse(
            success=False,
            message=f"Error: {str(e)}",
            has_cookies=False,
        )


class GuidedSessionResponse(BaseModel):
    """Response for guided browser session flow."""
    success: bool
    message: str
    cookies_captured: bool = False
    username: Optional[str] = None


class InstagramCookiesResponse(BaseModel):
    """Response for Instagram cookie operations."""
    success: bool
    message: str
    has_cookies: bool = False


@router.post(
    "/{persona_id}/accounts/instagram/set-cookies",
    response_model=InstagramCookiesResponse,
)
async def set_instagram_cookies(
    persona_id: UUID,
    request: ManualCookiesRequest,
    db: AsyncSession = Depends(get_db),
):
    """Manually set Instagram session cookies for browser automation.
    
    This is an alternative to browser login when automated login fails.
    User can export cookies from their browser and paste them here.
    
    Accepts either:
    - JSON object: {"sessionid": "xxx", "ds_user_id": "xxx", ...}
    - Cookie string: "sessionid=xxx; ds_user_id=xxx; ..."
    """
    import json
    from app.models.platform_account import PlatformAccount, Platform
    
    # Get persona
    result = await db.execute(select(Persona).where(Persona.id == persona_id))
    persona = result.scalar_one_or_none()
    
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Persona not found",
        )
    
    # Get existing Instagram account for this persona
    result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.persona_id == persona_id,
            PlatformAccount.platform == Platform.INSTAGRAM,
        )
    )
    account = result.scalar_one_or_none()
    
    # For Instagram, we can create the account if it doesn't exist
    create_new = account is None
    
    # Parse cookies
    try:
        cookies_str = request.cookies.strip()
        
        # Try parsing as JSON first
        if cookies_str.startswith("{"):
            cookies = json.loads(cookies_str)
        else:
            # Parse cookie string format: "name=value; name2=value2"
            cookies = {}
            for part in cookies_str.split(";"):
                part = part.strip()
                if "=" in part:
                    name, value = part.split("=", 1)
                    cookies[name.strip()] = value.strip()
        
        # Validate we have at least one essential cookie
        essential_cookies = ["sessionid", "ds_user_id"]
        has_essential = any(c in cookies for c in essential_cookies)
        
        if not has_essential:
            return InstagramCookiesResponse(
                success=False,
                message=f"Missing essential cookies. Need at least one of: {', '.join(essential_cookies)}",
                has_cookies=False,
            )
        
        # Create or update account
        if create_new:
            # Try to get username from ds_user_id or default
            username = cookies.get("ds_user", "instagram_user")
            account = PlatformAccount(
                persona_id=persona_id,
                platform=Platform.INSTAGRAM,
                username=username,
                is_connected=True,
                is_primary=True,
                session_cookies=cookies,
            )
            db.add(account)
        else:
            account.session_cookies = cookies
        
        await db.commit()
        
        logger.info(
            "Instagram cookies set manually",
            persona=persona.name,
            cookie_count=len(cookies),
            created_new=create_new,
        )
        
        return InstagramCookiesResponse(
            success=True,
            message=f"Cookies saved! {len(cookies)} cookies stored. Instagram session is now enabled.",
            has_cookies=True,
        )
        
    except json.JSONDecodeError:
        return InstagramCookiesResponse(
            success=False,
            message="Invalid cookie format. Use JSON or 'name=value; name2=value2' format.",
            has_cookies=False,
        )
    except Exception as e:
        logger.error("Set Instagram cookies error", error=str(e))
        return InstagramCookiesResponse(
            success=False,
            message=f"Error: {str(e)}",
            has_cookies=False,
        )


@router.post(
    "/{persona_id}/accounts/twitter/guided-session",
    response_model=GuidedSessionResponse,
)
async def twitter_guided_session(
    persona_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Launch a guided browser session to capture Twitter cookies.
    
    This opens a VISIBLE browser window where the user logs into Twitter.
    Once login is detected, cookies are captured and stored automatically.
    The user handles any 2FA or security challenges directly.
    
    Flow:
    1. Opens browser to Twitter login page
    2. User logs in normally (visible window)
    3. System detects successful login
    4. Cookies are captured and stored
    5. Browser closes automatically
    """
    import asyncio
    from playwright.async_api import async_playwright
    from app.models.platform_account import PlatformAccount, Platform
    
    # Get persona
    result = await db.execute(select(Persona).where(Persona.id == persona_id))
    persona = result.scalar_one_or_none()
    
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Persona not found",
        )
    
    # Get existing Twitter account for this persona
    result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.persona_id == persona_id,
            PlatformAccount.platform == Platform.TWITTER,
        )
    )
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Twitter account connected. Connect via OAuth first to get API access, then use this to add session cookies for engagement.",
        )
    
    logger.info("Starting guided Twitter session", persona=persona.name)
    
    playwright = None
    browser = None
    
    try:
        playwright = await async_playwright().start()
        
        # Launch VISIBLE browser (not headless)
        try:
            browser = await playwright.chromium.launch(
                headless=False,  # User sees the browser!
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--start-maximized",
                ],
            )
        except Exception as launch_error:
            error_str = str(launch_error)
            # Check if this is a display/X Server error
            if "XServer" in error_str or "display" in error_str.lower() or "Target page, context or browser has been closed" in error_str:
                logger.warning("No display available for guided session", error=error_str)
                return GuidedSessionResponse(
                    success=False,
                    message="Cannot open browser window - no display available. This happens when running in Docker without display forwarding. Please use the 'Paste Cookies' method instead: copy your cookies from browser DevTools.",
                    cookies_captured=False,
                )
            raise  # Re-raise other errors
        
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        
        # Anti-detection
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        
        page = await context.new_page()
        
        # Navigate to Twitter login
        await page.goto("https://twitter.com/i/flow/login", wait_until="domcontentloaded")
        
        logger.info("Browser opened - waiting for user to complete login")
        
        # Wait for user to complete login (detect /home URL or session cookies)
        # Give them up to 5 minutes to handle 2FA, etc.
        max_wait_seconds = 300  # 5 minutes
        poll_interval = 2  # Check every 2 seconds
        logged_in = False
        
        for _ in range(max_wait_seconds // poll_interval):
            await asyncio.sleep(poll_interval)
            
            current_url = page.url
            
            # Check if we've reached the home page (successful login)
            if "/home" in current_url and "login" not in current_url:
                logged_in = True
                logger.info("Login detected - user reached home page")
                break
            
            # Also check for essential cookies
            cookies = await context.cookies()
            cookie_names = {c["name"] for c in cookies}
            if "auth_token" in cookie_names and "ct0" in cookie_names:
                logged_in = True
                logger.info("Login detected - essential cookies found")
                break
            
            # Check if browser was closed by user
            if page.is_closed():
                logger.info("Browser was closed by user")
                break
        
        if not logged_in:
            return GuidedSessionResponse(
                success=False,
                message="Login timed out or browser was closed. Please try again.",
                cookies_captured=False,
            )
        
        # Give a moment for all cookies to settle
        await asyncio.sleep(2)
        
        # Capture cookies
        all_cookies = await context.cookies()
        
        # Filter for Twitter/X cookies
        twitter_cookies = {
            c["name"]: c["value"]
            for c in all_cookies
            if "twitter.com" in c.get("domain", "") or "x.com" in c.get("domain", "")
        }
        
        # Validate essential cookies
        essential = ["auth_token", "ct0"]
        missing = [c for c in essential if c not in twitter_cookies]
        
        if missing:
            return GuidedSessionResponse(
                success=False,
                message=f"Login appeared successful but missing cookies: {', '.join(missing)}",
                cookies_captured=False,
            )
        
        # Store cookies
        account.session_cookies = twitter_cookies
        await db.commit()
        
        logger.info(
            "Twitter session cookies captured via guided flow",
            persona=persona.name,
            cookie_count=len(twitter_cookies),
        )
        
        return GuidedSessionResponse(
            success=True,
            message=f"Success! Captured {len(twitter_cookies)} cookies. Engagement features are now enabled.",
            cookies_captured=True,
            username=account.username,
        )
        
    except Exception as e:
        error_str = str(e)
        logger.error("Guided session error", error=error_str)
        
        # Check for display-related errors
        if "XServer" in error_str or "display" in error_str.lower() or "has been closed" in error_str:
            return GuidedSessionResponse(
                success=False,
                message="Cannot open browser window - no display available. Please use the 'Paste Cookies' method instead.",
                cookies_captured=False,
            )
        
        return GuidedSessionResponse(
            success=False,
            message=f"Error: {error_str}",
            cookies_captured=False,
        )
    finally:
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()


@router.post(
    "/{persona_id}/accounts/instagram/guided-session",
    response_model=GuidedSessionResponse,
)
async def instagram_guided_session(
    persona_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Launch a guided browser session to capture Instagram cookies.
    
    This opens a VISIBLE browser window where the user logs into Instagram.
    Once login is detected, cookies are captured and stored automatically.
    The user handles any 2FA or security challenges directly.
    """
    import asyncio
    from playwright.async_api import async_playwright
    from app.models.platform_account import PlatformAccount, Platform
    
    # Get persona
    result = await db.execute(select(Persona).where(Persona.id == persona_id))
    persona = result.scalar_one_or_none()
    
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Persona not found",
        )
    
    # Get or create Instagram account for this persona
    result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.persona_id == persona_id,
            PlatformAccount.platform == Platform.INSTAGRAM,
        )
    )
    account = result.scalar_one_or_none()
    
    # For Instagram, we can create the account during this flow if it doesn't exist
    # since we don't have a separate OAuth step
    create_new_account = account is None
    
    logger.info("Starting guided Instagram session", persona=persona.name, create_new=create_new_account)
    
    playwright = None
    browser = None
    
    try:
        playwright = await async_playwright().start()
        
        # Launch VISIBLE browser
        try:
            browser = await playwright.chromium.launch(
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--start-maximized",
                ],
            )
        except Exception as launch_error:
            error_str = str(launch_error)
            # Check if this is a display/X Server error
            if "XServer" in error_str or "display" in error_str.lower() or "Target page, context or browser has been closed" in error_str:
                logger.warning("No display available for guided session", error=error_str)
                return GuidedSessionResponse(
                    success=False,
                    message="Cannot open browser window - no display available. This happens when running in Docker without display forwarding. Please use the 'Paste Cookies' method instead: copy your cookies from browser DevTools.",
                    cookies_captured=False,
                )
            raise  # Re-raise other errors
        
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        
        # Anti-detection
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        
        page = await context.new_page()
        
        # Navigate to Instagram login
        await page.goto("https://www.instagram.com/accounts/login/", wait_until="domcontentloaded")
        
        logger.info("Browser opened - waiting for user to complete Instagram login")
        
        # Wait for user to complete login
        max_wait_seconds = 300  # 5 minutes
        poll_interval = 2
        logged_in = False
        username = None
        
        for _ in range(max_wait_seconds // poll_interval):
            await asyncio.sleep(poll_interval)
            
            current_url = page.url
            
            # Check if we're past the login page
            if "instagram.com" in current_url and "/accounts/login" not in current_url:
                # Check for essential cookies
                cookies = await context.cookies()
                cookie_dict = {c["name"]: c["value"] for c in cookies if "instagram.com" in c.get("domain", "")}
                
                if "sessionid" in cookie_dict or "ds_user_id" in cookie_dict:
                    logged_in = True
                    logger.info("Instagram login detected")
                    
                    # Try to get username from the page
                    try:
                        # Check URL for username
                        if current_url.count("/") >= 4:
                            parts = current_url.rstrip("/").split("/")
                            potential_username = parts[-1] if parts[-1] else parts[-2]
                            if potential_username and potential_username not in ["", "direct", "explore", "reels"]:
                                username = potential_username
                        
                        # Or try to find it on the page
                        if not username:
                            profile_link = await page.query_selector('a[href*="instagram.com/"][role="link"]')
                            if profile_link:
                                href = await profile_link.get_attribute("href")
                                if href:
                                    username = href.rstrip("/").split("/")[-1]
                    except Exception:
                        pass
                    
                    break
            
            # Check if browser was closed
            if page.is_closed():
                logger.info("Browser was closed by user")
                break
        
        if not logged_in:
            return GuidedSessionResponse(
                success=False,
                message="Login timed out or browser was closed. Please try again.",
                cookies_captured=False,
            )
        
        # Give a moment for cookies to settle
        await asyncio.sleep(2)
        
        # Capture cookies
        all_cookies = await context.cookies()
        
        instagram_cookies = {
            c["name"]: c["value"]
            for c in all_cookies
            if "instagram.com" in c.get("domain", "")
        }
        
        if not instagram_cookies:
            return GuidedSessionResponse(
                success=False,
                message="Login appeared successful but no cookies were captured.",
                cookies_captured=False,
            )
        
        # Create or update account
        if create_new_account:
            account = PlatformAccount(
                persona_id=persona_id,
                platform=Platform.INSTAGRAM,
                username=username or "instagram_user",
                is_connected=True,
                is_primary=True,
                session_cookies=instagram_cookies,
                profile_url=f"https://instagram.com/{username}" if username else None,
            )
            db.add(account)
        else:
            account.session_cookies = instagram_cookies
            if username:
                account.username = username
                account.profile_url = f"https://instagram.com/{username}"
        
        await db.commit()
        
        logger.info(
            "Instagram session cookies captured via guided flow",
            persona=persona.name,
            cookie_count=len(instagram_cookies),
            username=username,
        )
        
        return GuidedSessionResponse(
            success=True,
            message=f"Success! Captured {len(instagram_cookies)} cookies. Instagram is now connected.",
            cookies_captured=True,
            username=username,
        )
        
    except Exception as e:
        error_str = str(e)
        logger.error("Guided Instagram session error", error=error_str)
        
        # Check for display-related errors
        if "XServer" in error_str or "display" in error_str.lower() or "has been closed" in error_str:
            return GuidedSessionResponse(
                success=False,
                message="Cannot open browser window - no display available. Please use the 'Paste Cookies' method instead.",
                cookies_captured=False,
            )
        
        return GuidedSessionResponse(
            success=False,
            message=f"Error: {error_str}",
            cookies_captured=False,
        )
    finally:
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()


class PlatformToggleRequest(BaseModel):
    """Request to toggle platform engagement or posting."""
    engagement_paused: Optional[bool] = None
    posting_paused: Optional[bool] = None


class PlatformToggleResponse(BaseModel):
    """Response for platform toggle operations."""
    success: bool
    platform: str
    engagement_paused: bool
    posting_paused: bool
    message: str


@router.patch(
    "/{persona_id}/accounts/{platform}/toggle",
    response_model=PlatformToggleResponse,
)
async def toggle_platform_status(
    persona_id: UUID,
    platform: str,
    request: PlatformToggleRequest,
    db: AsyncSession = Depends(get_db),
):
    """Toggle engagement and/or posting status for a specific platform.
    
    This allows independent control over each platform's automation.
    Set engagement_paused=true to stop engagement (likes, follows, comments) for this platform.
    Set posting_paused=true to stop posting content to this platform.
    """
    from app.models.platform_account import PlatformAccount, Platform as PlatformEnum
    
    # Validate platform
    try:
        platform_enum = PlatformEnum(platform.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid platform: {platform}. Supported: twitter, instagram",
        )
    
    # Get persona
    result = await db.execute(select(Persona).where(Persona.id == persona_id))
    persona = result.scalar_one_or_none()
    
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Persona not found",
        )
    
    # Get platform account
    result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.persona_id == persona_id,
            PlatformAccount.platform == platform_enum,
        )
    )
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {platform} account connected for this persona",
        )
    
    # Update flags
    changes = []
    if request.engagement_paused is not None:
        account.engagement_paused = request.engagement_paused
        changes.append(f"engagement {'paused' if request.engagement_paused else 'resumed'}")
    
    if request.posting_paused is not None:
        account.posting_paused = request.posting_paused
        changes.append(f"posting {'paused' if request.posting_paused else 'resumed'}")
    
    await db.commit()
    
    logger.info(
        "Platform status toggled",
        persona=persona.name,
        platform=platform,
        changes=changes,
    )
    
    return PlatformToggleResponse(
        success=True,
        platform=platform,
        engagement_paused=account.engagement_paused,
        posting_paused=account.posting_paused,
        message=f"Successfully updated: {', '.join(changes)}" if changes else "No changes made",
    )


def _persona_to_response(persona: Persona) -> PersonaResponse:
    """Convert Persona model to response schema."""
    return PersonaResponse(
        id=persona.id,
        name=persona.name,
        bio=persona.bio,
        niche=persona.niche,
        voice=VoiceConfig(
            tone=persona.voice.tone,
            vocabulary_level=persona.voice.vocabulary_level,
            emoji_usage=persona.voice.emoji_usage,
            hashtag_style=persona.voice.hashtag_style,
            signature_phrases=persona.voice.signature_phrases,
        ),
        ai_provider=persona.ai_provider,
        posting_schedule=persona.posting_schedule,
        engagement_hours_start=persona.engagement_hours_start,
        engagement_hours_end=persona.engagement_hours_end,
        timezone=persona.timezone,
        auto_approve_content=persona.auto_approve_content,
        is_active=persona.is_active,
        follower_count=persona.follower_count,
        following_count=persona.following_count,
        post_count=persona.post_count,
        likes_today=persona.likes_today or 0,
        comments_today=persona.comments_today or 0,
        follows_today=persona.follows_today or 0,
        higgsfield_character_id=persona.higgsfield_character_id,
        content_prompt_template=persona.content_prompt_template,
        comment_prompt_template=persona.comment_prompt_template,
        image_prompt_template=persona.image_prompt_template,
    )


