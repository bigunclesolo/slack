# Slack-GitHub NLP Automation System Setup Guide

## Quick Start

### Prerequisites

- Python 3.9 or higher
- Docker and Docker Compose
- Redis (can be run via Docker)
- PostgreSQL (can be run via Docker)
- Slack App with bot permissions
- GitHub Personal Access Token
- Transformer models (automatically downloaded)

### 1. Clone and Setup

```bash
git clone <repository-url>
cd slack-github-automation
cp .env.example .env
```

### 2. Configure Environment Variables

Edit the `.env` file with your credentials:

```bash
# Required: Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-token-here

# Required: GitHub Configuration
GITHUB_TOKEN=ghp_your-github-token-here

# Optional: Transformer Configuration (for enhanced NLP)
TRANSFORMERS_CACHE_DIR=./models
USE_GPU_IF_AVAILABLE=true
```

### 3. Install Dependencies

```bash
python -m pip install -r requirements.txt

# Optional: Install spaCy language model
python -m spacy download en_core_web_sm
```

### 4. Start Infrastructure (Docker)

```bash
# Start PostgreSQL and Redis
docker-compose up -d postgres redis

# Or start all services
docker-compose up -d
```

### 5. Run the Application

```bash
# Development mode
python main.py --mode development

# Production mode
python main.py --mode production

# Worker mode (orchestrator only)
python main.py --mode worker
```

## Detailed Setup

### Slack App Configuration

1. **Create Slack App**
   - Go to [Slack API](https://api.slack.com/apps)
   - Click "Create New App" → "From scratch"
   - Enter app name and select workspace

2. **Configure Bot Token Scopes**
   - Go to "OAuth & Permissions"
   - Add these scopes under "Bot Token Scopes":
     - `app_mentions:read`
     - `channels:history`
     - `chat:write`
     - `commands`
     - `files:read`
     - `users:read`

3. **Install App to Workspace**
   - Click "Install to Workspace"
   - Copy the "Bot User OAuth Token" (starts with `xoxb-`)

4. **Enable Socket Mode**
   - Go to "Socket Mode"
   - Enable Socket Mode
   - Generate an App Token with `connections:write` scope
   - Copy the "App Token" (starts with `xapp-`)

5. **Add Slash Commands**
   - Go to "Slash Commands"
   - Create commands: `/github`, `/code`, `/pr`
   - Leave Request URL empty (using Socket Mode)

### GitHub Configuration

1. **Create Personal Access Token**
   - Go to GitHub Settings → Developer settings → Personal access tokens
   - Generate new token with these scopes:
     - `repo` (full repository access)
     - `read:user`
     - `user:email`

### Database Setup

The application will automatically create necessary tables on first run. If you need to set up manually:

```sql
-- Create database
CREATE DATABASE slack_github_automation;

-- Create user
CREATE USER slack_user WITH PASSWORD 'slack_password';
GRANT ALL PRIVILEGES ON DATABASE slack_github_automation TO slack_user;
```

### Production Deployment

#### Option 1: Docker Compose (Recommended)

```bash
# Production deployment
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

#### Option 2: Kubernetes

```bash
# Apply Kubernetes manifests
kubectl apply -f k8s/
```

#### Option 3: Manual Deployment

```bash
# Set production environment
export ENVIRONMENT=production

# Install production dependencies
pip install -r requirements.txt

# Run with process manager (e.g., supervisord, systemd)
python main.py --mode production
```

## Configuration Options

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `SLACK_BOT_TOKEN` | Slack bot token | Yes | - |
| `SLACK_APP_TOKEN` | Slack app token | Yes | - |
| `GITHUB_TOKEN` | GitHub personal access token | Yes | - |
| `TRANSFORMERS_CACHE_DIR` | Directory for transformer models | No | `./models` |
| `DATABASE_URL` | PostgreSQL connection string | Yes | `postgresql://...` |
| `REDIS_URL` | Redis connection string | Yes | `redis://localhost:6379/0` |
| `LOG_LEVEL` | Logging level | No | `INFO` |
| `ENVIRONMENT` | Environment (development/production) | No | `development` |

### Feature Flags

- `ENABLE_TRANSFORMERS`: Use transformer models for advanced NLP (default: true)
- `ENABLE_SPACY`: Use spaCy for entity extraction (default: true)
- `ENABLE_CODE_GENERATION`: Enable code generation features (default: true)
- `ENABLE_AUTO_PR_CREATION`: Automatically create PRs (default: true)

## Usage Examples

### Basic Commands

```
# Create a new branch
/github create a new branch called feature-auth in my-repo

# Generate code
/code add a Python function to validate email addresses

# Create pull request
/pr create pull request from feature-auth to main

# Mention the bot
@SlackGitBot fix the bug in src/auth.py line 45
```

### Advanced Usage

```
# Multiple operations
/github create branch feature-login, add login.py file with authentication logic, then create PR

# Code modifications
/code modify the user_service.py file to add password hashing

# Repository management
/github clone repository myorg/myapp and create development branch
```

## Monitoring and Troubleshooting

### Health Check

```bash
python main.py --health-check
```

### Logs

```bash
# View logs in Docker
docker-compose logs -f slack-bot
docker-compose logs -f orchestrator

# View application logs
tail -f logs/application.log
```

### Metrics

- Prometheus metrics: `http://localhost:9090`
- Grafana dashboard: `http://localhost:3001` (admin/admin)

### Common Issues

1. **"Bot not responding"**
   - Check Slack app installation
   - Verify bot token and app token
   - Ensure Socket Mode is enabled

2. **"GitHub operations failing"**
   - Verify GitHub token permissions
   - Check repository access
   - Ensure token hasn't expired

3. **"Database connection errors"**
   - Verify PostgreSQL is running
   - Check connection string
   - Ensure database exists

4. **"Redis connection errors"**
   - Verify Redis is running
   - Check Redis URL
   - Ensure Redis is accessible

## Security Considerations

### Production Security

1. **Environment Variables**
   - Never commit `.env` files
   - Use secure secret management
   - Rotate tokens regularly

2. **Network Security**
   - Use TLS/SSL in production
   - Restrict database access
   - Configure firewall rules

3. **Access Control**
   - Implement user permissions
   - Rate limiting
   - Input validation

### Slack Security

1. **Token Security**
   - Store tokens securely
   - Use minimal required scopes
   - Monitor token usage

2. **Webhook Verification**
   - Enable request signing
   - Verify request signatures
   - Use HTTPS endpoints

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=.

# Run specific test modules
pytest tests/test_nlp.py
pytest tests/test_github.py
```

### Code Quality

```bash
# Format code
black .

# Lint code
flake8

# Type checking
mypy .
```

### Contributing

1. Fork the repository
2. Create feature branch
3. Make changes
4. Add tests
5. Submit pull request

## Support

For issues and questions:

1. Check the troubleshooting guide
2. Review logs for error messages
3. Open GitHub issue with details
4. Include system information and logs
