# AI Influencer Platform

A comprehensive platform for building and managing autonomous AI-powered social media personas. Create AI influencers that generate content, post regularly, and authentically engage with their community across multiple platforms.

> ⚠️ **Important**: This software automates social media interactions. Please read the [Disclaimers](#disclaimers) section carefully before use.

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Platform Setup](#platform-setup)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [Disclaimers](#disclaimers)
- [License](#license)

## Features

### Persona Management
- **Multi-Persona Support**: Create and manage multiple AI influencer personas
- **Customizable Voices**: Define unique personalities, tones, vocabulary levels, and signature phrases
- **Niche Targeting**: Configure content focus areas and engagement hashtags
- **Platform-Specific Settings**: Independent configuration per social platform

### Content Creation
- **AI-Powered Generation**: Automated content creation using OpenAI GPT-4 or Anthropic Claude
- **Vision-Enhanced Comments**: Analyzes images in posts for contextually relevant comments
- **Image Generation**: Optional AI image generation via Higgsfield API
- **Content Review Queue**: Approve or edit content before posting
- **Smart Scheduling**: Configurable posting schedules with timezone support
- **Character Limit Handling**: Automatic enforcement of platform-specific limits

### Engagement Automation
- **Smart Engagement**: Automated likes, comments, and follows based on relevance scoring
- **Hashtag-Based Discovery**: Finds relevant content through hashtag searches
- **Duplicate Prevention**: Tracks engaged posts to avoid redundant interactions
- **Per-Persona Limits**: Configurable daily limits for each engagement type
- **Human-Like Timing**: Random delays between actions to mimic natural behavior

### Multi-Platform Support
- **Instagram**: Graph API + browser automation for full feature support
- **Twitter/X**: API v2 + browser automation fallback for rate limit handling
- **Extensible Architecture**: Designed for easy addition of new platforms

### Dashboard
- **Analytics**: Per-persona, per-platform performance metrics
- **Content Management**: Review, edit, approve, and schedule content
- **Engagement Monitoring**: Real-time activity feed with platform indicators
- **Platform Controls**: Independent pause/resume for posting and engagement per platform

### Safety & Control
- **Rate Limiting**: Configurable daily limits to prevent platform detection
- **Content Review**: Optional human-in-the-loop approval workflow
- **Engagement Pausing**: Instantly pause/resume automation per persona or platform
- **Action Logging**: Complete audit trail of all automated actions

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Operator Dashboard (Next.js)                      │
│                       http://localhost:3000                          │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        FastAPI Backend                               │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  ┌───────────┐  │
│  │ Persona API  │  │ Content API  │  │ Analytics  │  │ Settings  │  │
│  └──────────────┘  └──────────────┘  └────────────┘  └───────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
┌─────────────────┐     ┌──────────────────┐     ┌───────────────────┐
│   AI Providers  │     │  Celery Workers  │     │ Platform Adapters │
│  ┌───────────┐  │     │  ┌────────────┐  │     │  ┌─────────────┐  │
│  │  OpenAI   │  │     │  │  Content   │  │     │  │  Instagram  │  │
│  │   GPT-4   │  │     │  │ Generation │  │     │  │ Graph API + │  │
│  └───────────┘  │     │  └────────────┘  │     │  │  Browser    │  │
│  ┌───────────┐  │     │  ┌────────────┐  │     │  └─────────────┘  │
│  │ Anthropic │  │     │  │  Posting   │  │     │  ┌─────────────┐  │
│  │  Claude   │  │     │  │   Tasks    │  │     │  │  Twitter/X  │  │
│  └───────────┘  │     │  └────────────┘  │     │  │  API v2 +   │  │
│  ┌───────────┐  │     │  ┌────────────┐  │     │  │  Browser    │  │
│  │Higgsfield │  │     │  │ Engagement │  │     │  └─────────────┘  │
│  │  (Images) │  │     │  │   Tasks    │  │     │                   │
│  └───────────┘  │     │  └────────────┘  │     │                   │
└─────────────────┘     └──────────────────┘     └───────────────────┘
         │                       │                         │
         └───────────────────────┼─────────────────────────┘
                                 ▼
                    ┌────────────────────────┐
                    │   PostgreSQL + Redis   │
                    └────────────────────────┘
```

## Quick Start

### Prerequisites

- **Docker** and **Docker Compose** (v2.0+)
- **AI Provider API Key** (at least one):
  - [OpenAI API Key](https://platform.openai.com/api-keys)
  - [Anthropic API Key](https://console.anthropic.com/)
- **Optional**: Platform-specific API credentials (see [Platform Setup](#platform-setup))

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/devinburnette/ai-influencer-platform.git
   cd ai-influencer-platform
   ```

2. **Create environment file**:
   ```bash
   cp env.example .env
   ```

3. **Configure minimum required variables** in `.env`:
   ```env
   # Required: At least one AI provider
   ANTHROPIC_API_KEY=sk-ant-your-key-here
   # OR
   OPENAI_API_KEY=sk-your-key-here
   
   # Required: Application secret
   SECRET_KEY=generate-a-secure-random-string
   ```

4. **Start all services**:
   ```bash
   docker-compose up -d
   ```

5. **Access the dashboard**: http://localhost:3000

6. **Create your first persona** and connect a platform account.

## Platform Setup

### Twitter/X (Recommended - Easier Setup)

Twitter's API is more accessible than Meta's. Free tier allows 50 tweets/month.

> **Note**: The free tier has strict rate limits that may cause analytics sync to fail intermittently. Profile stats (followers, following) sync when API quota is available. Engagement actions (likes, follows) use browser automation to avoid API limits.

1. **Get API Credentials**:
   - Go to [developer.twitter.com/en/portal/dashboard](https://developer.twitter.com/en/portal/dashboard)
   - Create a Project and App
   - Set App permissions to **"Read and Write"**
   - Generate all keys and tokens

2. **Add to `.env`**:
   ```env
   TWITTER_API_KEY=your_api_key
   TWITTER_API_SECRET=your_api_secret
   TWITTER_ACCESS_TOKEN=your_access_token
   TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret
   TWITTER_BEARER_TOKEN=your_bearer_token
   ```

3. **Connect via Dashboard**:
   - Go to Personas → Your Persona → Connected Platforms
   - Click "Connect Twitter"
   - Complete the OAuth flow

4. **Enable Browser Automation** (for engagement):
   - Click "Enable Session" on the Twitter account
   - Follow instructions to provide session cookies
   - This allows likes, follows, and rate-limit fallback

### Instagram

Instagram requires either Meta Business verification (complex) or browser automation.

#### Option A: Meta Graph API (Official)

1. Create a Meta Developer account at [developers.facebook.com](https://developers.facebook.com)
2. Create a Business App
3. Add Instagram Graph API product
4. Complete Business Verification (can take weeks)
5. Generate a long-lived access token

```env
META_APP_ID=your_app_id
META_APP_SECRET=your_app_secret
```

#### Option B: Browser Automation (Simpler)

1. Connect Instagram through the dashboard
2. Provide your Instagram Business Account ID and Access Token
3. Enable browser session for engagement features

### Higgsfield (AI Image Generation)

Optional - generates images to accompany posts.

1. Get API credentials from [docs.higgsfield.ai](https://docs.higgsfield.ai/)
2. Create a character/style for your persona
3. Add to `.env`:
   ```env
   HIGGSFIELD_API_KEY=your_api_key
   HIGGSFIELD_API_SECRET=your_api_secret
   ```
4. Add the Character ID to your persona in the dashboard

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Application secret for security |
| `ANTHROPIC_API_KEY` | One required | Anthropic Claude API key |
| `OPENAI_API_KEY` | One required | OpenAI GPT-4 API key |
| `DEFAULT_AI_PROVIDER` | No | `anthropic` or `openai` (default: `openai`) |
| `TWITTER_API_KEY` | For Twitter | Twitter API credentials |
| `TWITTER_API_SECRET` | For Twitter | Twitter API credentials |
| `META_APP_ID` | For Instagram | Meta App credentials |
| `META_APP_SECRET` | For Instagram | Meta App credentials |
| `HIGGSFIELD_API_KEY` | No | For AI image generation |
| `MAX_POSTS_PER_DAY` | No | Default: 3 |
| `MAX_LIKES_PER_DAY` | No | Default: 100 |
| `MAX_COMMENTS_PER_DAY` | No | Default: 30 |
| `MAX_FOLLOWS_PER_DAY` | No | Default: 20 |
| `MIN_ACTION_DELAY` | No | Minimum seconds between actions (default: 30) |
| `MAX_ACTION_DELAY` | No | Maximum seconds between actions (default: 300) |

### Persona Settings

| Setting | Description |
|---------|-------------|
| `name` | Display name for the persona |
| `bio` | Social media bio text |
| `niche` | Content focus areas and engagement hashtags |
| `voice.tone` | Communication style (casual, professional, witty, etc.) |
| `voice.emoji_usage` | Level of emoji use (none, minimal, moderate, heavy) |
| `voice.vocabulary_level` | Simple, conversational, or sophisticated |
| `posting_schedule` | When to post (morning, afternoon, evening, late_night) |
| `engagement_hours_start/end` | Active hours for engagement (0-23) |
| `ai_provider` | Which LLM to use for this persona |
| `auto_approve_content` | Skip review queue for generated content |
| `higgsfield_character_id` | Character ID for AI image generation |

## Usage

### Creating a Persona

1. Navigate to **Personas** → **New Persona**
2. Fill in personality details, niche, and voice settings
3. Configure posting schedule and engagement hours
4. Save and connect platform accounts

### Content Workflow

1. **Automatic Generation**: Content is generated based on posting schedule
2. **Review Queue**: Content appears in Content → Pending Review (unless auto-approve is enabled)
3. **Approval**: Approve, edit, or reject content
4. **Posting**: Approved content is posted at scheduled times

### Manual Actions

```bash
# Trigger content generation
docker-compose exec backend python -c "
from app.workers.tasks.content_tasks import generate_content_for_persona
generate_content_for_persona.delay('PERSONA_ID')
"

# Trigger engagement cycle
docker-compose exec backend python -c "
from app.workers.tasks.engagement_tasks import run_engagement_cycle
run_engagement_cycle.delay()
"

# Sync analytics from platforms
docker-compose exec backend python -c "
from app.workers.tasks.engagement_tasks import sync_analytics
sync_analytics.delay()
"
```

### Monitoring

```bash
# View all logs
docker-compose logs -f

# View specific service
docker-compose logs -f celery-worker

# Check service status
docker-compose ps
```

## API Documentation

Once running, access interactive API docs at:
- **Swagger UI**: http://localhost:8000/docs

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/personas/` | GET/POST | List or create personas |
| `/api/personas/{id}` | GET/PATCH/DELETE | Manage specific persona |
| `/api/personas/{id}/accounts` | GET | List platform accounts |
| `/api/content/` | GET | List all content |
| `/api/content/{id}/approve` | POST | Approve pending content |
| `/api/content/{id}/post-now` | POST | Immediately post content |
| `/api/analytics/overview` | GET | Dashboard statistics |
| `/api/analytics/activity-log` | GET | Recent engagement activity |

## Project Structure

```
ai-influencer-platform/
├── backend/
│   ├── app/
│   │   ├── api/              # REST API endpoints
│   │   │   ├── personas.py   # Persona management
│   │   │   ├── content.py    # Content management
│   │   │   ├── analytics.py  # Analytics & activity
│   │   │   └── settings.py   # App settings
│   │   ├── models/           # SQLAlchemy models
│   │   ├── services/
│   │   │   ├── ai/           # AI providers (OpenAI, Anthropic)
│   │   │   ├── image/        # Image generation (Higgsfield)
│   │   │   ├── platforms/    # Platform adapters
│   │   │   │   ├── instagram/
│   │   │   │   └── twitter/
│   │   │   └── engagement/   # Engagement strategies
│   │   └── workers/          # Celery background tasks
│   │       └── tasks/
│   ├── alembic/              # Database migrations
│   ├── scripts/              # Utility scripts
│   └── tests/
├── dashboard/
│   └── src/
│       ├── app/              # Next.js pages
│       ├── components/       # React components
│       └── lib/              # API client & utilities
├── scripts/
│   ├── guided_login.py       # Browser session helper
│   ├── backup_db.sh          # Database backup script
│   └── restore_db.sh         # Database restore script
├── backups/                   # Database backups (gitignored)
├── docker-compose.yml
├── env.example
└── README.md
```

## Backup & Restore

### Manual Backup

```bash
# Create a backup
./scripts/backup_db.sh

# Backups are stored in ./backups/ with timestamps
# Example: backups/ai_influencer_20241226_120000.sql.gz
```

### Restore from Backup

```bash
# List available backups
ls -la backups/

# Restore a specific backup (will prompt for confirmation)
./scripts/restore_db.sh backups/ai_influencer_20241226_120000.sql.gz

# Restart services after restore
docker-compose restart backend celery-worker celery-beat
```

### Automated Daily Backups

Set up a cron job to run backups automatically:

```bash
# Edit crontab
crontab -e

# Add this line to backup daily at 2 AM
0 2 * * * cd /path/to/ai-influencer-platform && ./scripts/backup_db.sh >> backups/backup.log 2>&1
```

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKUP_DIR` | `./backups` | Directory to store backups |
| `RETAIN_DAYS` | `7` | Days to keep old backups |

```bash
# Example: Keep 30 days of backups in custom directory
BACKUP_DIR=/mnt/backups RETAIN_DAYS=30 ./scripts/backup_db.sh
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd dashboard
npm install
npm run dev
```

## Disclaimers

### ⚠️ Terms of Service

**This software automates social media interactions, which may violate the Terms of Service of various platforms:**

- **Twitter/X**: Automation is heavily restricted. See [Twitter's Automation Rules](https://help.twitter.com/en/rules-and-policies/twitter-automation). Automated likes, follows, and certain engagement patterns are prohibited.

- **Instagram/Meta**: Automation violates [Instagram's Terms of Use](https://help.instagram.com/581066165581870). Using unofficial automation can result in account action.

**By using this software, you acknowledge that:**

1. Your accounts may be **suspended, restricted, or permanently banned**
2. You are solely responsible for compliance with platform rules
3. The authors and contributors assume no liability for account actions

### ⚠️ No Warranty

This software is provided "AS IS", without warranty of any kind, express or implied. The authors are not responsible for:

- Account suspensions or bans
- Loss of followers or engagement
- Any damages arising from use of this software
- Content generated by AI systems

### ⚠️ Ethical Considerations

Please consider the following before deploying AI influencers:

1. **Disclosure**: Many jurisdictions require disclosure of AI-generated content and paid partnerships. Check local laws and platform policies.

2. **Authenticity**: AI-generated personas may be considered deceptive. Consider ethical implications of synthetic influencers.

3. **Content Responsibility**: You are responsible for all content generated and posted, even if AI-generated.

4. **Data Privacy**: This platform stores session data and credentials. Secure your deployment appropriately.

5. **Rate Limiting**: Aggressive automation can degrade platform experience for others. Use responsibly.

### ⚠️ Legal

This software is intended for educational and research purposes. Users are responsible for:

- Compliance with all applicable laws and regulations
- Compliance with platform Terms of Service
- Proper disclosure of automated/AI-generated content
- Securing API keys and credentials
- Any consequences of using this software

## License

MIT License - See [LICENSE](LICENSE) file for details.

---

## Support

- **Issues**: [GitHub Issues](https://github.com/devinburnette/ai-influencer-platform/issues)
- **Discussions**: [GitHub Discussions](https://github.com/devinburnette/ai-influencer-platform/discussions)

---

**Remember**: With great automation comes great responsibility. Use this platform ethically and in compliance with platform rules.
