#!/usr/bin/env python3
"""
Simplified deployment script for Slack-GitHub automation
"""

import sys
import os
import asyncio
import logging
from pathlib import Path

# Add project paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "slack-bot"))
sys.path.insert(0, str(project_root / "shared"))

from shared.config import get_settings, validate_settings, print_configuration
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def create_slack_app():
    """Create and configure Slack app"""
    settings = get_settings()
    
    app = AsyncApp(
        token=settings.slack_bot_token,
        process_before_response=True
    )
    
    @app.command("/github")
    async def handle_github_command(ack, say, command):
        await ack()
        await say(f"🤖 GitHub command received: {command['text']}")
        logger.info(f"GitHub command: {command['text']}")
    
    @app.command("/code")
    async def handle_code_command(ack, say, command):
        await ack()
        await say(f"💻 Code command received: {command['text']}")
        logger.info(f"Code command: {command['text']}")
    
    @app.command("/pr")
    async def handle_pr_command(ack, say, command):
        await ack()
        await say(f"🔄 PR command received: {command['text']}")
        logger.info(f"PR command: {command['text']}")
    
    @app.event("app_mention")
    async def handle_mention(event, say):
        await say(f"👋 Hello <@{event['user']}>! I received your message: {event['text']}")
        logger.info(f"Mention from {event['user']}: {event['text']}")
    
    return app

async def main():
    """Main deployment function"""
    logger.info("🚀 Starting Slack-GitHub automation deployment...")
    
    # Validate configuration
    is_valid, errors = validate_settings()
    if not is_valid:
        logger.error("❌ Configuration errors:")
        for error in errors:
            logger.error(f"  - {error}")
        return False
    
    logger.info("✅ Configuration validated")
    print_configuration()
    
    # Create Slack app
    try:
        app = await create_slack_app()
        logger.info("✅ Slack app created successfully")
        
        # Start Socket Mode handler
        settings = get_settings()
        handler = AsyncSocketModeHandler(app, settings.slack_app_token)
        
        logger.info("🔌 Starting Socket Mode connection...")
        await handler.start_async()
        
    except Exception as e:
        logger.error(f"❌ Deployment failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Shutting down gracefully...")
    except Exception as e:
        logger.error(f"💥 Deployment error: {e}")
        sys.exit(1)
