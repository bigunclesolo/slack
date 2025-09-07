"""
Shared data models for the Slack-GitHub automation system
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class CommandType(str, Enum):
    GITHUB = "github"
    CODE = "code"
    PR = "pr"
    MENTION = "mention"


class SlackRequest(BaseModel):
    """Model for Slack user requests"""
    user_id: str
    channel_id: str
    command: str
    command_type: CommandType = CommandType.GITHUB
    response_url: Optional[str] = None
    trigger_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        use_enum_values = True


class Intent(BaseModel):
    """Model for extracted intent from NLP"""
    type: str
    confidence: float
    parameters: Dict[str, Any] = Field(default_factory=dict)


class Entity(BaseModel):
    """Model for extracted entities from NLP"""
    type: str
    value: str
    confidence: float
    start_pos: int = 0
    end_pos: int = 0


class ProcessedRequest(BaseModel):
    """Model for processed NLP request"""
    original_text: str
    intent: str
    confidence: float
    entities: Dict[str, str] = Field(default_factory=dict)
    raw_entities: List[Entity] = Field(default_factory=list)
    processing_time: Optional[float] = None
    
    def get_entity(self, entity_type: str) -> Optional[str]:
        """Get entity value by type"""
        return self.entities.get(entity_type)
    
    def has_entity(self, entity_type: str) -> bool:
        """Check if entity exists"""
        return entity_type in self.entities


class GitHubOperation(BaseModel):
    """Model for GitHub operations"""
    operation_type: str
    repository: Optional[str] = None
    branch: Optional[str] = None
    file_path: Optional[str] = None
    content: Optional[str] = None
    commit_message: Optional[str] = None
    pr_number: Optional[int] = None
    pr_title: Optional[str] = None
    pr_body: Optional[str] = None
    user_id: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    
    @classmethod
    def from_processed_request(cls, processed: ProcessedRequest, user_id: str) -> 'GitHubOperation':
        """Create GitHubOperation from ProcessedRequest"""
        return cls(
            operation_type=processed.intent,
            repository=processed.get_entity("repository"),
            branch=processed.get_entity("branch"),
            file_path=processed.get_entity("file"),
            user_id=user_id,
            parameters={
                "description": processed.get_entity("description"),
                "language": processed.get_entity("language"),
                "function": processed.get_entity("function")
            }
        )


class OperationStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OperationResult(BaseModel):
    """Model for operation execution results"""
    operation_id: str
    status: OperationStatus
    success: bool
    result_data: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    processing_time: Optional[float] = None
    
    def mark_completed(self, success: bool, result_data: Dict[str, Any] = None, 
                      error_message: str = None):
        """Mark operation as completed"""
        self.end_time = datetime.now()
        self.processing_time = (self.end_time - self.start_time).total_seconds()
        self.success = success
        self.status = OperationStatus.COMPLETED if success else OperationStatus.FAILED
        if result_data:
            self.result_data = result_data
        if error_message:
            self.error_message = error_message
    
    class Config:
        use_enum_values = True


class UserPreferences(BaseModel):
    """Model for user preferences and settings"""
    user_id: str
    preferred_language: str = "python"
    default_branch: str = "main"
    auto_create_pr: bool = True
    notification_level: str = "normal"  # minimal, normal, verbose
    github_username: Optional[str] = None
    repositories: List[str] = Field(default_factory=list)
    
    def add_repository(self, repo_name: str):
        """Add repository to user's list"""
        if repo_name not in self.repositories:
            self.repositories.append(repo_name)
    
    def remove_repository(self, repo_name: str):
        """Remove repository from user's list"""
        if repo_name in self.repositories:
            self.repositories.remove(repo_name)


class CodeSnippet(BaseModel):
    """Model for code snippets and templates"""
    id: str
    name: str
    language: str
    code: str
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    created_by: str
    created_at: datetime = Field(default_factory=datetime.now)
    usage_count: int = 0


class WorkflowStep(BaseModel):
    """Model for workflow steps"""
    step_id: str
    step_type: str  # nlp, github, validation, notification
    parameters: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)
    timeout_seconds: int = 300
    retry_count: int = 0
    max_retries: int = 3


class WorkflowExecution(BaseModel):
    """Model for workflow execution tracking"""
    execution_id: str
    request_id: str
    user_id: str
    channel_id: str
    steps: List[WorkflowStep]
    current_step: int = 0
    status: OperationStatus = OperationStatus.PENDING
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    results: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    
    def get_current_step(self) -> Optional[WorkflowStep]:
        """Get the current step being executed"""
        if 0 <= self.current_step < len(self.steps):
            return self.steps[self.current_step]
        return None
    
    def advance_step(self):
        """Move to the next step"""
        self.current_step += 1
    
    def is_completed(self) -> bool:
        """Check if workflow is completed"""
        return self.current_step >= len(self.steps)
    
    class Config:
        use_enum_values = True


class SlackMessage(BaseModel):
    """Model for Slack messages"""
    channel_id: str
    text: str
    blocks: Optional[List[Dict[str, Any]]] = None
    thread_ts: Optional[str] = None
    user_id: Optional[str] = None
    message_type: str = "message"
    
    def add_code_block(self, code: str, language: str = ""):
        """Add a code block to the message"""
        code_block = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"```{language}\n{code}\n```"
            }
        }
        
        if self.blocks is None:
            self.blocks = []
        
        self.blocks.append(code_block)
    
    def add_button(self, text: str, action_id: str, value: str = ""):
        """Add an action button to the message"""
        if self.blocks is None:
            self.blocks = []
        
        # Find or create actions block
        actions_block = None
        for block in self.blocks:
            if block.get("type") == "actions":
                actions_block = block
                break
        
        if actions_block is None:
            actions_block = {
                "type": "actions",
                "elements": []
            }
            self.blocks.append(actions_block)
        
        button = {
            "type": "button",
            "text": {
                "type": "plain_text",
                "text": text
            },
            "action_id": action_id,
            "value": value
        }
        
        actions_block["elements"].append(button)


class SystemConfig(BaseModel):
    """Model for system configuration"""
    slack_bot_token: str
    slack_app_token: str
    github_token: str
    openai_api_key: str
    database_url: str
    redis_url: str
    
    # API Settings
    max_request_size: int = 1024 * 1024  # 1MB
    request_timeout: int = 30
    max_concurrent_operations: int = 10
    
    # NLP Settings
    nlp_confidence_threshold: float = 0.7
    use_openai_for_low_confidence: bool = True
    
    # GitHub Settings
    default_branch: str = "main"
    max_file_size: int = 1024 * 1024  # 1MB
    
    # Security Settings
    rate_limit_per_user: int = 60  # requests per hour
    allowed_file_extensions: List[str] = Field(default_factory=lambda: [
        ".py", ".js", ".ts", ".java", ".go", ".rs", ".cpp", ".c", ".h",
        ".md", ".txt", ".json", ".yaml", ".yml", ".xml", ".html", ".css"
    ])
    
    class Config:
        env_file = ".env"
