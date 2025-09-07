"""
Unit tests for shared.models module
"""

import pytest
from datetime import datetime
from shared.models import (
    CommandType, SlackRequest, ProcessedRequest, Entity,
    GitHubOperation, OperationResult, OperationStatus,
    UserPreferences, SlackMessage
)


class TestSlackRequest:
    def test_slack_request_creation(self):
        """Test basic SlackRequest creation"""
        request = SlackRequest(
            user_id="U123456",
            channel_id="C123456",
            command="create a python function"
        )
        
        assert request.user_id == "U123456"
        assert request.channel_id == "C123456"
        assert request.command == "create a python function"
        assert request.command_type == CommandType.GITHUB
        assert isinstance(request.timestamp, datetime)

    def test_slack_request_with_custom_type(self):
        """Test SlackRequest with custom command type"""
        request = SlackRequest(
            user_id="U123456",
            channel_id="C123456",
            command="generate code",
            command_type=CommandType.CODE
        )
        
        assert request.command_type == CommandType.CODE


class TestProcessedRequest:
    def test_processed_request_creation(self):
        """Test ProcessedRequest creation and methods"""
        entities = {"repository": "my-repo", "language": "python"}
        request = ProcessedRequest(
            original_text="create a function in my-repo",
            intent="create_function",
            confidence=0.95,
            entities=entities
        )
        
        assert request.original_text == "create a function in my-repo"
        assert request.intent == "create_function"
        assert request.confidence == 0.95
        assert request.entities == entities

    def test_get_entity(self):
        """Test get_entity method"""
        request = ProcessedRequest(
            original_text="test",
            intent="test",
            confidence=0.8,
            entities={"repo": "test-repo", "file": "main.py"}
        )
        
        assert request.get_entity("repo") == "test-repo"
        assert request.get_entity("file") == "main.py"
        assert request.get_entity("nonexistent") is None

    def test_has_entity(self):
        """Test has_entity method"""
        request = ProcessedRequest(
            original_text="test",
            intent="test", 
            confidence=0.8,
            entities={"repo": "test-repo"}
        )
        
        assert request.has_entity("repo") is True
        assert request.has_entity("nonexistent") is False


class TestGitHubOperation:
    def test_github_operation_creation(self):
        """Test GitHubOperation creation"""
        operation = GitHubOperation(
            operation_type="create_file",
            repository="test-repo",
            file_path="src/main.py",
            content="print('hello world')",
            user_id="U123456"
        )
        
        assert operation.operation_type == "create_file"
        assert operation.repository == "test-repo"
        assert operation.file_path == "src/main.py"
        assert operation.user_id == "U123456"

    def test_from_processed_request(self):
        """Test creating GitHubOperation from ProcessedRequest"""
        processed = ProcessedRequest(
            original_text="create a function in my-repo",
            intent="create_function",
            confidence=0.95,
            entities={
                "repository": "my-repo",
                "file": "utils.py",
                "language": "python"
            }
        )
        
        operation = GitHubOperation.from_processed_request(processed, "U123456")
        
        assert operation.operation_type == "create_function"
        assert operation.repository == "my-repo"
        assert operation.file_path == "utils.py"
        assert operation.user_id == "U123456"
        assert operation.parameters["language"] == "python"


class TestOperationResult:
    def test_operation_result_creation(self):
        """Test OperationResult creation"""
        result = OperationResult(
            operation_id="op123",
            status=OperationStatus.PENDING,
            success=False
        )
        
        assert result.operation_id == "op123"
        assert result.status == OperationStatus.PENDING
        assert result.success is False
        assert isinstance(result.start_time, datetime)

    def test_mark_completed_success(self):
        """Test marking operation as successfully completed"""
        result = OperationResult(
            operation_id="op123",
            status=OperationStatus.PROCESSING,
            success=False
        )
        
        result_data = {"file_url": "https://github.com/repo/blob/main/file.py"}
        result.mark_completed(success=True, result_data=result_data)
        
        assert result.success is True
        assert result.status == OperationStatus.COMPLETED
        assert result.result_data == result_data
        assert result.end_time is not None
        assert result.processing_time is not None

    def test_mark_completed_failure(self):
        """Test marking operation as failed"""
        result = OperationResult(
            operation_id="op123",
            status=OperationStatus.PROCESSING,
            success=False
        )
        
        error_msg = "Repository not found"
        result.mark_completed(success=False, error_message=error_msg)
        
        assert result.success is False
        assert result.status == OperationStatus.FAILED
        assert result.error_message == error_msg


class TestUserPreferences:
    def test_user_preferences_creation(self):
        """Test UserPreferences creation with defaults"""
        prefs = UserPreferences(user_id="U123456")
        
        assert prefs.user_id == "U123456"
        assert prefs.preferred_language == "python"
        assert prefs.default_branch == "main"
        assert prefs.auto_create_pr is True
        assert prefs.repositories == []

    def test_add_repository(self):
        """Test adding repository to user preferences"""
        prefs = UserPreferences(user_id="U123456")
        prefs.add_repository("my-repo")
        prefs.add_repository("another-repo")
        prefs.add_repository("my-repo")  # duplicate
        
        assert len(prefs.repositories) == 2
        assert "my-repo" in prefs.repositories
        assert "another-repo" in prefs.repositories

    def test_remove_repository(self):
        """Test removing repository from user preferences"""
        prefs = UserPreferences(
            user_id="U123456", 
            repositories=["repo1", "repo2", "repo3"]
        )
        
        prefs.remove_repository("repo2")
        assert len(prefs.repositories) == 2
        assert "repo2" not in prefs.repositories
        
        prefs.remove_repository("nonexistent")  # should not error
        assert len(prefs.repositories) == 2


class TestSlackMessage:
    def test_slack_message_creation(self):
        """Test SlackMessage creation"""
        message = SlackMessage(
            channel_id="C123456",
            text="Hello world!"
        )
        
        assert message.channel_id == "C123456"
        assert message.text == "Hello world!"
        assert message.blocks is None
        assert message.message_type == "message"

    def test_add_code_block(self):
        """Test adding code block to message"""
        message = SlackMessage(channel_id="C123456", text="Check this code:")
        
        code = "def hello():\n    print('Hello!')"
        message.add_code_block(code, "python")
        
        assert message.blocks is not None
        assert len(message.blocks) == 1
        assert message.blocks[0]["type"] == "section"
        assert "python" in message.blocks[0]["text"]["text"]
        assert code in message.blocks[0]["text"]["text"]

    def test_add_button(self):
        """Test adding button to message"""
        message = SlackMessage(channel_id="C123456", text="Choose an action:")
        
        message.add_button("Approve", "approve_action", "approve_123")
        
        assert message.blocks is not None
        assert len(message.blocks) == 1
        assert message.blocks[0]["type"] == "actions"
        assert len(message.blocks[0]["elements"]) == 1
        
        button = message.blocks[0]["elements"][0]
        assert button["type"] == "button"
        assert button["text"]["text"] == "Approve"
        assert button["action_id"] == "approve_action"
        assert button["value"] == "approve_123"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
