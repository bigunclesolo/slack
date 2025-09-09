# Slack-GitHub NLP Automation System

## Overview
This system enables users to interact with GitHub repositories through Slack using natural language commands. Users can request code changes, create pull requests, and commit changes through conversational interfaces.

## Architecture

```
┌─────────────┐    ┌─────────────────┐    ┌──────────────────┐
│   Slack     │───▶│   NLP Engine    │───▶│  GitHub Engine   │
│   App       │    │                 │    │                  │
│             │◀───│  - Intent       │◀───│  - API Client    │
│ - Webhooks  │    │    Extraction   │    │  - Code Gen      │
│ - Commands  │    │  - Entity       │    │  - PR Management │
│ - UI        │    │    Recognition  │    │  - Branch Ops    │
└─────────────┘    └─────────────────┘    └──────────────────┘
       │                      │                      │
       │                      │                      │
       ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────┐
│              Workflow Orchestrator                          │
│  - Request Processing   - Error Handling                    │
│  - State Management     - Progress Tracking                 │
│  - User Feedback        - Security Checks                   │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Slack App
- **Purpose**: Modern Slack app interface for receiving user commands and sending responses
- **Features**:
  - Slash commands (`/github`, `/code`, `/pr`)
  - Global shortcuts for quick access (Ctrl+/ or Cmd+/)
  - Interactive buttons and rich modals with Block Kit
  - Real-time status updates with timestamps
  - File upload support for code snippets
  - Direct message capabilities
  - Error handling with admin notifications
  - Socket Mode for real-time events (no webhooks needed)

### 2. NLP Engine
- **Purpose**: Parse natural language into structured commands
- **Capabilities**:
  - Intent classification (create, update, delete, review)
  - Entity extraction (repository, file paths, code snippets)
  - Context awareness for multi-turn conversations
  - Confidence scoring

### 3. GitHub Integration Engine
- **Purpose**: Execute operations on GitHub repositories
- **Operations**:
  - Repository cloning and branch management
  - File creation, modification, and deletion
  - Pull request creation and management
  - Code review automation
  - Commit and push operations

### 4. Workflow Orchestrator
- **Purpose**: Coordinate all system components
- **Responsibilities**:
  - Request routing and processing
  - State management across operations
  - Error handling and recovery
  - Security and permission enforcement

## Example Use Cases

1. **Create Feature Branch**
   - User: "Create a new feature branch called 'user-authentication' in the main-app repo"
   - System: Creates branch, updates Slack with status

2. **Code Generation**
   - User: "Add a login function in Python that validates email and password"
   - System: Generates code, creates PR, requests review

3. **Bug Fix**
   - User: "Fix the null pointer exception in UserService.java line 45"
   - System: Analyzes code, suggests fix, creates PR

4. **Documentation Update**
   - User: "Update the README with installation instructions for Docker"
   - System: Modifies README.md, commits changes

## Technology Stack

### Backend
- **Language**: Python 3.9+
- **Framework**: FastAPI for API endpoints
- **NLP**: OpenAI GPT-4 API + spaCy for preprocessing
- **GitHub**: PyGithub for API interactions
- **Database**: PostgreSQL for state management
- **Message Queue**: Redis for async processing

### Slack Integration
- **SDK**: Slack Bolt for Python
- **Authentication**: OAuth 2.0
- **Real-time**: Socket Mode for events

### Infrastructure
- **Containerization**: Docker
- **Orchestration**: Docker Compose (development), Kubernetes (production)
- **CI/CD**: GitHub Actions
- **Monitoring**: Prometheus + Grafana
- **Logging**: Structured logging with ELK stack

## Security Considerations

1. **Authentication & Authorization**
   - Slack OAuth for user identity
   - GitHub Personal Access Tokens (scoped)
   - Role-based access control

2. **Input Validation**
   - Sanitize all user inputs
   - Validate file paths and repository access
   - Rate limiting and abuse prevention

3. **Code Safety**
   - Sandbox code execution for validation
   - Automated security scanning
   - Review requirements for sensitive operations

## Setup & Connection Instructions

### Quick Setup

1. **Clone the repository and setup environment**:
   ```bash
   git clone <repository-url>
   cd slack-github-automation
   cp .env.example .env
   ```

2. **Create and configure your Slack App**:
   - Go to [Slack API](https://api.slack.com/apps)
   - Click "Create New App" → "From scratch"
   - Enter app name and select your workspace

3. **Configure Slack App permissions**:
   - Go to "OAuth & Permissions" and add these Bot Token Scopes:
     - `app_mentions:read` - Read mentions of your app
     - `channels:history` - View messages in public channels
     - `chat:write` - Send messages
     - `commands` - Add slash commands
     - `files:read` - View files shared in channels
     - `users:read` - View people in workspace
     - `im:write` - Send direct messages
     - `channels:read` - View basic channel information
     - `groups:read` - View basic private channel information

4. **Enable Socket Mode**:
   - Go to "Socket Mode" and enable it
   - Generate an App Token with `connections:write` scope
   - Copy the App Token (starts with `xapp-`)

5. **Install App and get Bot Token**:
   - Click "Install to Workspace"
   - Copy the Bot User OAuth Token (starts with `xoxb-`)

6. **Add Slash Commands**:
   - Go to "Slash Commands" and create:
     - `/github` - "Execute GitHub operations with natural language"
     - `/code` - "Generate or modify code using AI"
     - `/pr` - "Manage pull requests"
   - Leave Request URL empty (using Socket Mode)

7. **Create GitHub Personal Access Token**:
   - Go to GitHub Settings → Developer settings → Personal access tokens
   - Generate new token with these scopes:
     - `repo` (full repository access)
     - `read:user`
     - `user:email`

8. **Configure Environment Variables**:
   Edit your `.env` file with your tokens:
   ```bash
   # Required: Slack Configuration
   SLACK_BOT_TOKEN=xoxb-your-bot-token-here
   SLACK_APP_TOKEN=xapp-your-app-token-here
   
   # Required: GitHub Configuration
   GITHUB_TOKEN=ghp_your-github-token-here
   ```

9. **Install Dependencies and Start**:
   ```bash
   pip3 install -r requirements.txt
   python -m spacy download en_core_web_sm
   docker-compose up -d postgres redis
   python main.py --mode development
   ```

### Usage Examples

Once connected, you can use these commands in Slack:

- **Create branches**: `/github create a new branch called feature-auth in my-repo`
- **Generate code**: `/code add a Python function to validate email addresses`
- **Create PRs**: `/pr create pull request from feature-auth to main`
- **Mention app**: `@SlackGitApp fix the bug in src/auth.py line 45`

### Troubleshooting Connection Issues

1. **App not responding**:
   - Verify Slack app installation and bot token
   - Ensure Socket Mode is enabled
   - Check that app token has `connections:write` scope

2. **GitHub operations failing**:
   - Verify GitHub token permissions include `repo` scope
   - Check that token hasn't expired
   - Ensure repository access is granted

3. **Database/Redis errors**:
   - Verify Docker containers are running: `docker-compose ps`
   - Check connection strings in `.env` file

For detailed setup instructions, see `/SETUP.md`.

## Getting Started

See individual component READMEs for detailed technical information:
- `/slack-app/README.md`
- `/nlp-engine/README.md`
- `/github-engine/README.md`
- `/orchestrator/README.md`
