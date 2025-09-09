"""
Slack Bot for GitHub NLP Automation
Handles Slack events, slash commands, and interactive components
"""

import os
import logging
from typing import Dict, Any, Optional
import asyncio
import json

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.models.blocks import (
    SectionBlock, ContextBlock, InputBlock, DividerBlock,
    MarkdownTextObject, PlainTextObject, Option
)
from slack_sdk.models.views import View
from slack_sdk.models.blocks.block_elements import (
    StaticSelectElement, PlainTextInputElement
)

from shared.models import SlackRequest, GitHubOperation
from shared.messaging import MessageQueue
from shared.config import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

# Initialize Slack app with enhanced configuration
app = AsyncApp(
    token=settings.slack_bot_token,
    signing_secret=settings.slack_signing_secret if settings.slack_signing_secret else None,
    process_before_response=True,  # Acknowledge requests quickly
    oauth_settings=None  # We're using bot token directly
)
message_queue = MessageQueue()


class SlackBot:
    def __init__(self):
        self.client = AsyncWebClient(token=settings.slack_bot_token)
        
    async def send_message(self, channel: str, text: str, blocks: Optional[list] = None):
        """Send a message to a Slack channel"""
        try:
            result = await self.client.chat_postMessage(
                channel=channel,
                text=text,
                blocks=blocks
            )
            return result
        except SlackApiError as e:
            logger.error(f"Error sending message: {e}")
            return None
    
    async def update_message(self, channel: str, ts: str, text: str, blocks: Optional[list] = None):
        """Update an existing message"""
        try:
            result = await self.client.chat_update(
                channel=channel,
                ts=ts,
                text=text,
                blocks=blocks
            )
            return result
        except SlackApiError as e:
            logger.error(f"Error updating message: {e}")
            return None

    async def send_progress_update(self, channel: str, ts: str, status: str, details: str = ""):
        """Send a progress update for an ongoing operation using Block Kit"""
        blocks = [
            SectionBlock(
                text=MarkdownTextObject(
                    text=f"*Status:* {status}"
                )
            )
        ]
        
        if details:
            blocks.append(
                SectionBlock(
                    text=MarkdownTextObject(
                        text=f"*Details:* {details}"
                    )
                )
            )
            
        # Add context with timestamp
        blocks.append(
            ContextBlock(
                elements=[
                    MarkdownTextObject(
                        text=f"Last updated: <!date^{int(asyncio.get_event_loop().time())}^{{date_short}} {{time}}|now>"
                    )
                ]
            )
        )
        
        await self.update_message(channel, ts, f"Operation Status: {status}", blocks)


bot = SlackBot()


@app.command("/github")
async def handle_github_command(ack, respond, command):
    """Handle /github slash command"""
    await ack()
    
    user_id = command["user_id"]
    channel_id = command["channel_id"]
    text = command["text"]
    
    if not text:
        await respond({
            "text": "Please provide a command. Example: `/github create a new branch called feature-auth in my-repo`",
            "response_type": "ephemeral"
        })
        return
    
    # Send initial response
    response = await respond({
        "text": f"🔄 Processing your GitHub request: `{text}`",
        "response_type": "in_channel"
    })
    
    # Create request object
    request = SlackRequest(
        user_id=user_id,
        channel_id=channel_id,
        command=text,
        response_url=command.get("response_url"),
        trigger_id=command.get("trigger_id")
    )
    
    # Queue for processing
    await message_queue.publish("github_requests", request.dict())
    
    logger.info(f"GitHub command queued: {text} from user {user_id}")


@app.command("/code")
async def handle_code_command(ack, respond, command):
    """Handle /code slash command for direct code operations"""
    await ack()
    
    user_id = command["user_id"]
    channel_id = command["channel_id"]
    text = command["text"]
    
    if not text:
        await respond({
            "text": "Please provide a code request. Example: `/code add a Python function to validate emails`",
            "response_type": "ephemeral"
        })
        return
    
    # Send initial response
    await respond({
        "text": f"🧠 Analyzing your code request: `{text}`",
        "response_type": "in_channel"
    })
    
    # Create request object
    request = SlackRequest(
        user_id=user_id,
        channel_id=channel_id,
        command=text,
        command_type="code",
        response_url=command.get("response_url"),
        trigger_id=command.get("trigger_id")
    )
    
    # Queue for processing
    await message_queue.publish("code_requests", request.dict())


@app.command("/pr")
async def handle_pr_command(ack, respond, command):
    """Handle /pr slash command for pull request operations"""
    await ack()
    
    user_id = command["user_id"]
    channel_id = command["channel_id"]
    text = command["text"]
    
    if not text:
        await respond({
            "text": "Please provide a PR request. Example: `/pr create pull request for feature-auth branch`",
            "response_type": "ephemeral"
        })
        return
    
    await respond({
        "text": f"📋 Processing your PR request: `{text}`",
        "response_type": "in_channel"
    })
    
    request = SlackRequest(
        user_id=user_id,
        channel_id=channel_id,
        command=text,
        command_type="pr",
        response_url=command.get("response_url"),
        trigger_id=command.get("trigger_id")
    )
    
    await message_queue.publish("pr_requests", request.dict())


@app.event("app_mention")
async def handle_app_mention(event, say):
    """Handle when the bot is mentioned in a channel"""
    user_id = event["user"]
    channel_id = event["channel"]
    text = event["text"]
    
    # Remove the bot mention from the text
    mention_pattern = r'<@[A-Z0-9]+>'
    import re
    clean_text = re.sub(mention_pattern, '', text).strip()
    
    if not clean_text:
        await say(
            text="Hi! I can help you with GitHub operations. Try `/github`, `/code`, or `/pr` commands!",
            channel=channel_id
        )
        return
    
    # Treat mentions as GitHub commands
    request = SlackRequest(
        user_id=user_id,
        channel_id=channel_id,
        command=clean_text,
        command_type="mention"
    )
    
    await say(
        text=f"🔄 I'll help you with: `{clean_text}`",
        channel=channel_id
    )
    
    await message_queue.publish("github_requests", request.dict())


@app.action("approve_pr")
async def handle_approve_pr(ack, body, action):
    """Handle PR approval button clicks"""
    await ack()
    
    user_id = body["user"]["id"]
    channel_id = body["channel"]["id"]
    
    # Extract PR information from the action value
    pr_data = json.loads(action["value"])
    
    operation = GitHubOperation(
        operation_type="approve_pr",
        repository=pr_data["repository"],
        pr_number=pr_data["pr_number"],
        user_id=user_id
    )
    
    await message_queue.publish("github_operations", operation.dict())
    
    # Update the message
    await bot.send_message(
        channel=channel_id,
        text=f"✅ PR #{pr_data['pr_number']} approval requested by <@{user_id}>"
    )


@app.action("reject_pr")
async def handle_reject_pr(ack, body, action):
    """Handle PR rejection button clicks"""
    await ack()
    
    user_id = body["user"]["id"]
    channel_id = body["channel"]["id"]
    
    pr_data = json.loads(action["value"])
    
    operation = GitHubOperation(
        operation_type="reject_pr",
        repository=pr_data["repository"],
        pr_number=pr_data["pr_number"],
        user_id=user_id
    )
    
    await message_queue.publish("github_operations", operation.dict())
    
    await bot.send_message(
        channel=channel_id,
        text=f"❌ PR #{pr_data['pr_number']} rejection requested by <@{user_id}>"
    )


# Global shortcuts for quick access
@app.shortcut("github_quick_action")
async def handle_github_shortcut(ack, shortcut, client):
    """Handle GitHub quick action global shortcut"""
    await ack()
    
    # Open a modal for GitHub operations
    await client.views_open(
        trigger_id=shortcut["trigger_id"],
        view=View(
            type="modal",
            callback_id="github_modal",
            title=PlainTextObject(text="GitHub Operations"),
            submit=PlainTextObject(text="Execute"),
            close=PlainTextObject(text="Cancel"),
            blocks=[
                SectionBlock(
                    text=MarkdownTextObject(
                        text="Choose a GitHub operation to perform:"
                    )
                ),
                InputBlock(
                    block_id="action_type",
                    element=StaticSelectElement(
                        placeholder=PlainTextObject(text="Select an action"),
                        action_id="action_select",
                        options=[
                            Option(
                                text=PlainTextObject(text="Create Branch"),
                                value="create_branch"
                            ),
                            Option(
                                text=PlainTextObject(text="Generate Code"),
                                value="generate_code"
                            ),
                            Option(
                                text=PlainTextObject(text="Create PR"),
                                value="create_pr"
                            ),
                            Option(
                                text=PlainTextObject(text="Custom Command"),
                                value="custom"
                            )
                        ]
                    ),
                    label=PlainTextObject(text="Action Type")
                ),
                InputBlock(
                    block_id="repository",
                    element=PlainTextInputElement(
                        action_id="repo_input",
                        placeholder=PlainTextObject(text="e.g., owner/repo-name")
                    ),
                    label=PlainTextObject(text="Repository")
                ),
                InputBlock(
                    block_id="description",
                    element=PlainTextInputElement(
                        action_id="desc_input",
                        multiline=True,
                        placeholder=PlainTextObject(
                            text="Describe what you want to do..."
                        )
                    ),
                    label=PlainTextObject(text="Description")
                )
            ]
        )
    )


@app.view("github_modal")
async def handle_github_modal_submission(ack, body, view):
    """Handle GitHub modal submission"""
    await ack()
    
    user_id = body["user"]["id"]
    
    # Extract form values
    values = view["state"]["values"]
    action_type = values["action_type"]["action_select"]["selected_option"]["value"]
    repository = values["repository"]["repo_input"]["value"]
    description = values["description"]["desc_input"]["value"]
    
    # Create command based on modal input
    if action_type == "create_branch":
        command = f"create a new branch in {repository}: {description}"
    elif action_type == "generate_code":
        command = f"generate code for {repository}: {description}"
    elif action_type == "create_pr":
        command = f"create pull request for {repository}: {description}"
    else:
        command = f"{description} in {repository}"
    
    # Create request object
    request = SlackRequest(
        user_id=user_id,
        channel_id=None,  # Modal doesn't have channel context
        command=command,
        command_type="modal"
    )
    
    await message_queue.publish("github_requests", request.dict())
    
    # Send confirmation DM
    try:
        await bot.client.chat_postMessage(
            channel=user_id,
            text=f"🚀 I'm processing your request: `{command}`"
        )
    except Exception as e:
        logger.error(f"Failed to send DM: {e}")


# Error handling middleware
@app.middleware
async def log_request(logger, body, next):
    """Log all incoming requests for debugging"""
    logger.info(f"Received Slack request: {body.get('type', 'unknown')}")
    await next()


@app.error
async def custom_error_handler(error, body):
    """Handle uncaught errors"""
    logger.error(f"Slack app error: {error}")
    logger.error(f"Request body: {body}")
    
    # Send error notification to admin channel if configured
    if hasattr(settings, 'slack_admin_channel') and settings.slack_admin_channel:
        try:
            await bot.client.chat_postMessage(
                channel=settings.slack_admin_channel,
                text=f"⚠️ Slack app error: {str(error)[:500]}..."
            )
        except Exception as e:
            logger.error(f"Failed to send error notification: {e}")


async def process_operation_updates():
    """Process operation status updates from the queue"""
    async for message in message_queue.consume("operation_updates"):
        try:
            update_data = json.loads(message)
            
            await bot.send_progress_update(
                channel=update_data["channel_id"],
                ts=update_data["message_ts"],
                status=update_data["status"],
                details=update_data.get("details", "")
            )
            
        except Exception as e:
            logger.error(f"Error processing operation update: {e}")


async def main():
    """Main application entry point"""
    handler = AsyncSocketModeHandler(app, settings.slack_app_token)
    
    # Start the background task for processing updates
    asyncio.create_task(process_operation_updates())
    
    # Start the Slack app
    await handler.start_async()


if __name__ == "__main__":
    asyncio.run(main())
