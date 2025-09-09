#!/usr/bin/env python3
"""
Production deployment script for Slack-GitHub automation
"""

import sys
import os
import asyncio
import logging
import signal
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
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('slack-github-bot.log')
    ]
)
logger = logging.getLogger(__name__)

class SlackGitHubBot:
    def __init__(self):
        self.app = None
        self.handler = None
        self.settings = get_settings()
        
    async def create_app(self):
        """Create and configure Slack app with all handlers"""
        self.app = AsyncApp(
            token=self.settings.slack_bot_token,
            process_before_response=True
        )
        
        # GitHub operations command
        @self.app.command("/github")
        async def handle_github_command(ack, say, command):
            await ack()
            user_id = command['user_id']
            text = command['text']
            
            logger.info(f"GitHub command from {user_id}: {text}")
            
            # Basic response for now
            await say({
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"🤖 *GitHub Operation Received*\n\n*Command:* `{text}`\n*Status:* Processing..."
                        }
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"Requested by <@{user_id}>"
                            }
                        ]
                    }
                ]
            })
        
        # Code generation command
        @self.app.command("/code")
        async def handle_code_command(ack, say, command):
            await ack()
            user_id = command['user_id']
            text = command['text']
            
            logger.info(f"Code command from {user_id}: {text}")
            
            await say({
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"💻 *Code Generation Request*\n\n*Request:* `{text}`\n*Status:* Generating code..."
                        }
                    }
                ]
            })
        
        # Pull request command
        @self.app.command("/pr")
        async def handle_pr_command(ack, say, command):
            await ack()
            user_id = command['user_id']
            text = command['text']
            
            logger.info(f"PR command from {user_id}: {text}")
            
            await say({
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"🔄 *Pull Request Operation*\n\n*Command:* `{text}`\n*Status:* Processing PR request..."
                        }
                    }
                ]
            })
        
        # App mentions
        @self.app.event("app_mention")
        async def handle_mention(event, say):
            user_id = event['user']
            text = event['text']
            
            logger.info(f"Mention from {user_id}: {text}")
            
            await say({
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"👋 Hello <@{user_id}>!\n\nI received your message: `{text}`\n\n*Available commands:*\n• `/github` - GitHub operations\n• `/code` - Code generation\n• `/pr` - Pull request management"
                        }
                    }
                ]
            })
        
        # Error handling
        @self.app.error
        async def error_handler(error, body, logger):
            logger.error(f"Error: {error}")
            logger.error(f"Request body: {body}")
        
        logger.info("✅ Slack app configured with all handlers")
        return self.app
    
    async def start(self):
        """Start the bot"""
        logger.info("🚀 Starting Slack-GitHub automation bot...")
        
        # Validate configuration
        is_valid, errors = validate_settings()
        if not is_valid:
            logger.error("❌ Configuration errors:")
            for error in errors:
                logger.error(f"  - {error}")
            return False
        
        logger.info("✅ Configuration validated")
        print_configuration()
        
        # Create app
        await self.create_app()
        
        # Start Socket Mode handler
        self.handler = AsyncSocketModeHandler(self.app, self.settings.slack_app_token)
        
        logger.info("🔌 Connecting to Slack...")
        await self.handler.start_async()
        
        return True
    
    async def stop(self):
        """Stop the bot gracefully"""
        if self.handler:
            logger.info("🛑 Stopping Slack connection...")
            await self.handler.close_async()
        logger.info("👋 Bot stopped")

# Global bot instance
bot = SlackGitHubBot()

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down...")
    asyncio.create_task(bot.stop())

async def main():
    """Main function"""
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        success = await bot.start()
        if success:
            logger.info("🎉 Bot is running successfully!")
            # Keep running until interrupted
            while True:
                await asyncio.sleep(1)
        else:
            logger.error("❌ Failed to start bot")
            return 1
    except KeyboardInterrupt:
        logger.info("👋 Shutting down gracefully...")
        await bot.stop()
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")
        await bot.stop()
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
