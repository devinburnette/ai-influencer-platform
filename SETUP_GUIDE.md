# AI Influencer Platform - Setup Guide

## Prerequisites

Before you can post to social media, you need:

1. **An AI Provider API Key** (at least one):
   - OpenAI API key from [platform.openai.com](https://platform.openai.com)
   - Anthropic API key from [console.anthropic.com](https://console.anthropic.com)

2. **Social Media Platform API Access**:
   - **Twitter/X** (Recommended): Developer account at [developer.twitter.com](https://developer.twitter.com)
   - **Instagram**: Requires Meta Business verification (more difficult to obtain)

---

## 🐦 Twitter/X Setup (Recommended - Easier API Access)

Twitter's API is much easier to access than Meta's. You can get started within minutes.

### Step 1: Get Twitter API Credentials

1. Go to [developer.twitter.com/en/portal/dashboard](https://developer.twitter.com/en/portal/dashboard)
2. Sign in with your Twitter account
3. Create a new Project and App
4. Go to "Keys and Tokens" tab
5. Generate the following:
   - **API Key** (Consumer Key)
   - **API Secret** (Consumer Secret)
   - **Access Token**
   - **Access Token Secret**
   - **Bearer Token** (optional, for read-only operations)

⚠️ **Important**: Make sure your app has **Read and Write** permissions!
   - Go to Settings → User Authentication Settings
   - Set App permissions to "Read and Write"

### Step 2: Configure Environment

```bash
cd ~/ai-influencer-platform
cp env.example .env
```

Edit `.env` and add your credentials:
```bash
# AI Provider (at least one required)
OPENAI_API_KEY=sk-your-actual-openai-key
# OR
ANTHROPIC_API_KEY=sk-ant-your-actual-anthropic-key

# Twitter API Credentials
TWITTER_API_KEY=your_api_key
TWITTER_API_SECRET=your_api_secret
TWITTER_ACCESS_TOKEN=your_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret
TWITTER_BEARER_TOKEN=your_bearer_token
```

### Step 3: Start Services

```bash
docker-compose down
docker-compose up -d
```

### Step 4: Create Your Persona

1. Open http://localhost:3000
2. Click "Create Persona"
3. Fill in your AI influencer's details
4. Save

### Step 5: Connect Twitter Account

Use the interactive wizard:

```bash
docker-compose exec backend python scripts/connect_twitter.py
```

Or connect manually:

```bash
docker-compose exec backend python -c "
import asyncio
from app.database import async_session_maker, init_db
from app.models import PlatformAccount, Persona, Platform
from sqlalchemy import select

async def connect():
    await init_db()
    async with async_session_maker() as session:
        # Get your persona
        result = await session.execute(
            select(Persona).where(Persona.name == 'YOUR_PERSONA_NAME')
        )
        persona = result.scalar_one_or_none()
        
        if persona:
            account = PlatformAccount(
                persona_id=persona.id,
                platform=Platform.TWITTER,
                username='YOUR_TWITTER_USERNAME',
                profile_url='https://twitter.com/YOUR_TWITTER_USERNAME',
                session_cookies={
                    'api_key': 'YOUR_API_KEY',
                    'api_secret': 'YOUR_API_SECRET',
                    'access_token': 'YOUR_ACCESS_TOKEN',
                    'access_token_secret': 'YOUR_ACCESS_TOKEN_SECRET',
                    'bearer_token': 'YOUR_BEARER_TOKEN',
                },
                is_connected=True,
            )
            session.add(account)
            await session.commit()
            print(f'Connected Twitter account for {persona.name}')
        else:
            print('Persona not found')

asyncio.run(connect())
"
```

### Step 6: Generate & Post Content

Through the dashboard:
1. Go to your persona's detail page
2. Click "Generate New Content"
3. Review and approve the content
4. Content will be posted according to schedule

Or manually trigger a post:
```bash
docker-compose exec backend python scripts/trigger_post.py
```

---

## Twitter API Tiers

Twitter offers different API access levels:

| Tier | Price | Read | Write | Best For |
|------|-------|------|-------|----------|
| Free | $0 | 1,500 tweets/mo | 50 tweets/mo | Testing |
| Basic | $100/mo | 10,000 tweets/mo | 3,000 tweets/mo | Small accounts |
| Pro | $5,000/mo | 1M tweets/mo | 300,000 tweets/mo | Large scale |

For most AI influencer use cases, the **Basic** tier is sufficient.

---

## 📸 Instagram Setup (Optional - Requires Meta Approval)

⚠️ **Note**: Meta's API approval process is complex and time-consuming. We recommend starting with Twitter.

### Meta Graph API (Official Method)

1. Go to [developers.facebook.com](https://developers.facebook.com)
2. Create App → Business
3. Add "Instagram Graph API" product
4. Complete business verification (can take weeks)
5. Request necessary permissions:
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_read_engagement`

### Browser Automation (Alternative)

For testing, you can use browser automation (not recommended for production):

```bash
docker-compose exec backend python scripts/connect_instagram.py
```

---

## Content Generation

### Manual Generation
```bash
# Generate content for a specific persona
docker-compose exec backend python -c "
from app.workers.tasks.content_tasks import generate_content_for_persona
generate_content_for_persona.delay('PERSONA_ID')
"
```

### Automatic Generation
Content is automatically generated by the Celery beat scheduler based on each persona's posting schedule.

---

## Engagement Automation

### Manual Engagement Run
```bash
docker-compose exec backend python -c "
from app.workers.tasks.engagement_tasks import run_engagement_cycle
run_engagement_cycle.delay('PERSONA_ID')
"
```

### Automatic Engagement
The Celery beat scheduler runs engagement cycles every 30 minutes for active personas.

---

## Monitoring

### View Celery Logs
```bash
docker-compose logs -f celery_worker
```

### View Backend Logs
```bash
docker-compose logs -f backend
```

### Check Task Status
Open http://localhost:8000/docs for the API documentation.

---

## Safety & Rate Limits

The platform respects platform limits by default:
- Max 3 posts per day per persona
- Max 100 likes per day
- Max 30 comments per day
- Max 20 follows per day
- Random delays between actions (30-300 seconds)

You can adjust these in your `.env` file.

---

## Troubleshooting

### "Twitter authentication failed"
- Check all API credentials are correct
- Ensure your app has Read and Write permissions
- Regenerate tokens if they were compromised

### "Content generation failed"
- Check your AI API key is valid
- Check you have sufficient credits/quota

### "Posting failed"
- For Twitter: Check rate limits haven't been exceeded
- Ensure tweet is under 280 characters
- Check media files are valid formats (JPEG, PNG, GIF)

### Database issues
```bash
# Reset database
docker-compose down -v
docker-compose up -d
docker-compose exec backend python scripts/seed_data.py
```

---

## Character Limits

| Platform | Text Limit | Images | Video |
|----------|------------|--------|-------|
| Twitter/X | 280 chars | 4 max | 1 max |
| Instagram | 2,200 chars | 10 max | 1 max |

The platform automatically truncates content if it exceeds limits.
