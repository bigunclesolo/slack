#!/usr/bin/env python3
"""
Comprehensive test suite for the Slack-GitHub automation app
"""

import sys
import os
import logging
from pathlib import Path

# Add project paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "slack-bot"))
sys.path.insert(0, str(project_root / "shared"))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_configuration():
    """Test configuration loading and validation"""
    logger.info("🔧 Testing configuration...")
    try:
        from shared.config import get_settings, validate_settings
        settings = get_settings()
        is_valid, errors = validate_settings()
        
        if is_valid:
            logger.info("✅ Configuration is valid")
            logger.info(f"Environment: {settings.environment}")
            logger.info(f"Slack tokens configured: {bool(settings.slack_bot_token and settings.slack_app_token)}")
            logger.info(f"GitHub token configured: {bool(settings.github_token)}")
            return True
        else:
            logger.error("❌ Configuration errors:")
            for error in errors:
                logger.error(f"  - {error}")
            return False
    except Exception as e:
        logger.error(f"❌ Configuration test failed: {e}")
        return False

def test_slack_imports():
    """Test Slack bot imports"""
    logger.info("🤖 Testing Slack bot imports...")
    try:
        from slack_bolt.async_app import AsyncApp
        from slack_sdk.web.async_client import AsyncWebClient
        logger.info("✅ Slack SDK imports successful")
        return True
    except Exception as e:
        logger.error(f"❌ Slack imports failed: {e}")
        return False

def test_shared_models():
    """Test shared models"""
    logger.info("📋 Testing shared models...")
    try:
        from shared.models import SlackRequest, GitHubOperation
        
        # Test SlackRequest creation
        request = SlackRequest(
            user_id="U123456",
            channel_id="C123456",
            text="test command",
            command="/github"
        )
        logger.info(f"✅ SlackRequest created: {request.user_id}")
        
        # Test GitHubOperation creation
        operation = GitHubOperation(
            operation_type="create_branch",
            repository="test/repo",
            branch_name="feature-test",
            user_id="U123456"
        )
        logger.info(f"✅ GitHubOperation created: {operation.operation_type}")
        return True
    except Exception as e:
        logger.error(f"❌ Shared models test failed: {e}")
        return False

def test_environment_variables():
    """Test environment variables are loaded"""
    logger.info("🌍 Testing environment variables...")
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        required_vars = ['SLACK_BOT_TOKEN', 'SLACK_APP_TOKEN', 'GITHUB_TOKEN']
        missing_vars = []
        
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            logger.warning(f"⚠️  Missing environment variables: {missing_vars}")
            logger.info("Note: This is expected if running without proper .env setup")
        else:
            logger.info("✅ All required environment variables are set")
        
        return True
    except Exception as e:
        logger.error(f"❌ Environment test failed: {e}")
        return False

def test_dependencies():
    """Test that all required dependencies are available"""
    logger.info("📦 Testing dependencies...")
    dependencies = [
        'slack_bolt',
        'slack_sdk', 
        'pydantic',
        'pydantic_settings',
        'dotenv',
        'asyncio'
    ]
    
    missing_deps = []
    for dep in dependencies:
        try:
            __import__(dep)
            logger.info(f"✅ {dep} available")
        except ImportError:
            missing_deps.append(dep)
            logger.error(f"❌ {dep} not available")
    
    if missing_deps:
        logger.error(f"Missing dependencies: {missing_deps}")
        return False
    
    logger.info("✅ All dependencies available")
    return True

def main():
    """Run all tests"""
    logger.info("🚀 Starting Slack-GitHub automation app tests...")
    
    tests = [
        ("Dependencies", test_dependencies),
        ("Environment Variables", test_environment_variables),
        ("Configuration", test_configuration),
        ("Slack Imports", test_slack_imports),
        ("Shared Models", test_shared_models),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        logger.info(f"\n--- Running {test_name} Test ---")
        try:
            if test_func():
                passed += 1
                logger.info(f"✅ {test_name} test PASSED")
            else:
                logger.error(f"❌ {test_name} test FAILED")
        except Exception as e:
            logger.error(f"❌ {test_name} test FAILED with exception: {e}")
    
    logger.info(f"\n🏁 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! The app is ready to run.")
        return True
    else:
        logger.error(f"💥 {total - passed} tests failed. Please fix the issues before running the app.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
