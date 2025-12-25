# AI Influencer Platform

A platform for building and maintaining autonomous AI social media influencers. Create AI personas that curate content, post regularly, and engage with their community - all with minimal human intervention.

## Features

- **AI Persona Management**: Create and configure AI influencers with unique personalities, niches, and voices
- **Autonomous Content Creation**: AI-generated posts tailored to each persona's style and audience
- **Smart Engagement**: Automated liking and contextual commenting on relevant content
- **Multi-Platform Support**: Starting with Instagram, designed for expansion to other platforms
- **Operator Dashboard**: Monitor performance, review content, and adjust configurations
- **Safety Controls**: Rate limiting, content review queues, and kill switches

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Operator Dashboard (Next.js)                │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Persona API  │  │ Content API  │  │ Analytics API        │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────────┐
│  AI Engine   │      │   Workers    │      │ Platform Adapters│
│  (OpenAI/    │      │   (Celery)   │      │   (Instagram)    │
│   Anthropic) │      │              │      │                  │
└──────────────┘      └──────────────┘      └──────────────────┘
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- OpenAI API key and/or Anthropic API key
- (Optional) Meta Developer account for Instagram Graph API

### Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd ai-influencer-platform
   ```

2. Create environment file:
   ```bash
   cp .env.example .env
   ```

3. Edit `.env` with your API keys:
   ```env
   OPENAI_API_KEY=sk-...
   ANTHROPIC_API_KEY=sk-ant-...
   SECRET_KEY=your-secure-secret-key
   ```

4. Start all services:
   ```bash
   docker-compose up -d
   ```

5. Access the dashboard at http://localhost:3000

### Development

**Backend only:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Dashboard only:**
```bash
cd dashboard
npm install
npm run dev
```

## Configuration

### Persona Settings

Each AI persona can be configured with:

| Setting | Description |
|---------|-------------|
| `name` | Display name for the persona |
| `bio` | Instagram bio text |
| `niche` | Areas of influence (e.g., fitness, tech) |
| `voice_tone` | Communication style (casual, professional, etc.) |
| `emoji_usage` | Level of emoji use (none, minimal, heavy) |
| `hashtag_style` | Hashtag strategy |
| `posting_schedule` | Cron expression for posting times |
| `engagement_hours` | Active hours for engagement |
| `ai_provider` | Which LLM to use (openai, anthropic) |

### Rate Limits

Default daily limits (configurable per persona):

- Posts: 3/day
- Likes: 100/day
- Comments: 30/day
- Follows: 20/day

## API Documentation

Once running, access the API docs at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
ai-influencer-platform/
├── backend/
│   ├── app/
│   │   ├── api/           # REST endpoints
│   │   ├── models/        # Database models
│   │   ├── services/      # Business logic
│   │   │   ├── ai/        # AI providers
│   │   │   ├── platforms/ # Platform adapters
│   │   │   └── engagement/# Engagement logic
│   │   └── workers/       # Celery tasks
│   └── tests/
├── dashboard/
│   └── src/
│       ├── app/           # Next.js pages
│       └── components/    # React components
└── docker-compose.yml
```

## Security Considerations

- All API keys are stored as environment variables
- Content review queue available for human oversight
- Rate limiting prevents platform detection/bans
- Session management for browser automation
- Audit logging for all autonomous actions

## Disclaimer

This platform automates social media interactions. Be aware that:
1. Automation may violate platform Terms of Service
2. Accounts may be suspended or banned
3. Use responsibly and ethically
4. Consider disclosure requirements for AI-generated content

## License

MIT License - See LICENSE file for details


