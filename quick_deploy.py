#!/usr/bin/env python3
"""Quick deployment script for Slack app"""

import os
import asyncio
import logging
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    bot_token = os.getenv("SLACK_BOT_TOKEN")
    app_token = os.getenv("SLACK_APP_TOKEN")
    
    if not bot_token or not app_token:
        logger.error("Missing SLACK_BOT_TOKEN or SLACK_APP_TOKEN")
        return
    
    # Create Slack app
    app = AsyncApp(token=bot_token)
    
    @app.command("/github")
    async def handle_github(ack, say, command):
        await ack()
        await say(f"🤖 GitHub: {command['text']}")
    
    @app.command("/code")
    async def handle_code(ack, say, command):
        await ack()
        await say(f"💻 Code: {command['text']}")
    
    @app.command("/pr")
    async def handle_pr(ack, say, command):
        await ack()
        await say(f"🔄 PR: {command['text']}")
    
    @app.event("app_mention")
    async def handle_mention(event, say):
        await say(f"👋 Hello! I got: {event['text']}")
    
    # Start Socket Mode
    handler = AsyncSocketModeHandler(app, app_token)
    logger.info("🚀 Starting Slack app...")
    await handler.start_async()

if __name__ == "__main__":
    asyncio.run(main())
