#!/usr/bin/env python3
"""
Main application launcher for Slack-GitHub NLP Automation System
"""

import asyncio
import logging
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
import multiprocessing as mp

from shared.config import get_settings, validate_settings, print_configuration
from shared.messaging import cleanup_messaging
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'slack-bot'))
from app import main as slack_bot_main
from orchestrator.workflow import start_orchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ApplicationManager:
    """Manages the lifecycle of all application components"""
    
    def __init__(self):
        self.settings = get_settings()
        self.running = False
        self.tasks = []
    
    async def startup(self):
        """Initialize and start all application components"""
        logger.info("🚀 Starting Slack-GitHub NLP Automation System...")
        
        # Validate configuration
        is_valid, errors = validate_settings()
        if not is_valid:
            logger.error("❌ Configuration validation failed:")
            for error in errors:
                logger.error(f"  - {error}")
            sys.exit(1)
        
        # Print configuration
        print_configuration()
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.running = True
        
        # Start all components
        await self._start_components()
    
    async def _start_components(self):
        """Start all application components"""
        logger.info("Starting application components...")
        
        try:
            # Start Slack Bot
            logger.info("Starting Slack Bot...")
            slack_task = asyncio.create_task(slack_bot_main())
            self.tasks.append(slack_task)
            
            # Start Workflow Orchestrator
            logger.info("Starting Workflow Orchestrator...")
            orchestrator_task = asyncio.create_task(start_orchestrator())
            self.tasks.append(orchestrator_task)
            
            # Wait for all tasks to complete
            await asyncio.gather(*self.tasks, return_exceptions=True)
            
        except Exception as e:
            logger.error(f"Error starting components: {e}")
            await self.shutdown()
            raise
    
    def _signal_handler(self, sig, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {sig}, initiating graceful shutdown...")
        self.running = False
        asyncio.create_task(self.shutdown())
    
    async def shutdown(self):
        """Gracefully shutdown all components"""
        logger.info("🛑 Shutting down Slack-GitHub NLP Automation System...")
        
        self.running = False
        
        # Cancel all tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete cancellation
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        # Cleanup resources
        await cleanup_messaging()
        
        logger.info("✅ Shutdown complete")
    
    async def health_check(self):
        """Perform system health check"""
        health_status = {
            "status": "healthy",
            "components": {},
            "timestamp": asyncio.get_event_loop().time()
        }
        
        try:
            # Check messaging system
            from shared.messaging import get_message_queue
            message_queue = get_message_queue()
            redis_health = await message_queue.health_check()
            health_status["components"]["redis"] = redis_health
            
            # Check if components are running
            health_status["components"]["slack_bot"] = {
                "status": "running" if any(not t.done() for t in self.tasks) else "stopped"
            }
            
            # Overall status
            unhealthy_components = [
                name for name, status in health_status["components"].items()
                if status.get("status") != "healthy" and status.get("status") != "running"
            ]
            
            if unhealthy_components:
                health_status["status"] = "degraded"
                health_status["issues"] = unhealthy_components
            
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)
        
        return health_status


async def main():
    """Main application entry point"""
    app_manager = ApplicationManager()
    
    try:
        await app_manager.startup()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)
    finally:
        if app_manager.running:
            await app_manager.shutdown()


def run_development():
    """Run in development mode with auto-reload"""
    logger.info("🔧 Running in development mode")
    
    try:
        import uvloop
        uvloop.install()
        logger.info("Using uvloop for better performance")
    except ImportError:
        logger.info("uvloop not available, using default event loop")
    
    asyncio.run(main())


def run_production():
    """Run in production mode"""
    logger.info("🏭 Running in production mode")
    
    # Use uvloop for better performance in production
    try:
        import uvloop
        uvloop.install()
    except ImportError:
        pass
    
    # Set optimal process settings
    if hasattr(mp, 'set_start_method'):
        mp.set_start_method('spawn', force=True)
    
    asyncio.run(main())


def run_worker_mode():
    """Run as background worker (orchestrator only)"""
    logger.info("👷 Running in worker mode (orchestrator only)")
    
    async def worker_main():
        app_manager = ApplicationManager()
        try:
            # Validate configuration
            is_valid, errors = validate_settings()
            if not is_valid:
                logger.error("❌ Configuration validation failed:")
                for error in errors:
                    logger.error(f"  - {error}")
                sys.exit(1)
            
            # Start only the orchestrator
            await start_orchestrator()
            
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Worker error: {e}")
            sys.exit(1)
        finally:
            await cleanup_messaging()
    
    asyncio.run(worker_main())


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Slack-GitHub NLP Automation System")
    parser.add_argument(
        "--mode",
        choices=["development", "production", "worker"],
        default="development",
        help="Run mode (default: development)"
    )
    parser.add_argument(
        "--health-check",
        action="store_true",
        help="Run health check and exit"
    )
    
    args = parser.parse_args()
    
    if args.health_check:
        async def health_check():
            app_manager = ApplicationManager()
            health_status = await app_manager.health_check()
            
            print(f"Health Status: {health_status['status']}")
            for component, status in health_status["components"].items():
                print(f"  {component}: {status.get('status', 'unknown')}")
            
            if health_status["status"] != "healthy":
                sys.exit(1)
        
        asyncio.run(health_check())
    else:
        if args.mode == "development":
            run_development()
        elif args.mode == "production":
            run_production()
        elif args.mode == "worker":
            run_worker_mode()
