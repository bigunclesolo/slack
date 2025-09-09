#!/usr/bin/env python3
"""
Simple test launcher for just the Slack bot
"""

import asyncio
import sys
import os
import logging
import pytest

# Add current directory to path
sys.path.append(os.path.dirname(__file__))
sys.path.append(os.path.join(os.path.dirname(__file__), 'slack-bot'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_slack_bot():
    """Test the Slack bot import and basic functionality"""
    try:
        # Import from slack-bot directory
        from app import app
        from shared.config import get_settings
        
        logger.info("🤖 Testing Slack Bot imports...")
        
        # Get settings
        settings = get_settings()
        
        # Test configuration validation
        assert settings.slack_bot_token, "SLACK_BOT_TOKEN not configured"
        assert settings.slack_app_token, "SLACK_APP_TOKEN not configured"
            
        logger.info("✅ Slack tokens are configured")
        logger.info("✅ Slack bot imports successfully!")
        
        # Test that the app object exists and has expected properties
        assert app is not None, "Slack app should be initialized"
        assert hasattr(app, 'client'), "Slack app should have a client"
        
        # Test SlackBot class instantiation
        from app import SlackBot
        bot = SlackBot()
        assert bot is not None, "SlackBot should be instantiable"
        assert bot.client is not None, "SlackBot should have a client"
        
        logger.info("✅ All Slack bot tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error testing Slack bot: {e}")
        raise  # Re-raise for pytest to catch

if __name__ == "__main__":
    asyncio.run(test_slack_bot())
