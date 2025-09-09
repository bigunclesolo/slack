"""
Configuration management for the Slack-GitHub automation system
"""

import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Slack Configuration
    slack_bot_token: str = ""
    slack_app_token: str = ""
    slack_signing_secret: str = ""
    slack_admin_channel: Optional[str] = None  # Channel for error notifications
    slack_default_channel: Optional[str] = None  # Default channel for notifications
    
    # GitHub Configuration
    github_token: str = ""
    github_webhook_secret: Optional[str] = None
    
    # Transformer Models Configuration
    transformers_cache_dir: str = "./models"
    use_gpu_if_available: bool = True
    
    # Database Configuration
    database_url: str = "postgresql://user:password@localhost/slack_github_automation"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    
    # Redis Configuration
    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = 10
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_debug: bool = False
    api_reload: bool = False
    
    # Security Configuration
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    
    # Application Configuration
    app_name: str = "Slack-GitHub NLP Automation"
    app_version: str = "1.0.0"
    environment: str = "development"
    log_level: str = "INFO"
    
    # Feature Flags
    enable_transformers: bool = True
    enable_spacy: bool = True
    enable_code_generation: bool = True
    enable_auto_pr_creation: bool = True
    
    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 3600  # 1 hour in seconds
    
    # File Processing
    max_file_size_mb: int = 10
    allowed_file_extensions: str = ".py,.js,.ts,.java,.go,.rs,.cpp,.c,.h,.md,.txt,.json,.yaml,.yml"
    
    # NLP Settings
    nlp_confidence_threshold: float = 0.7
    use_transformers_for_low_confidence: bool = True
    intent_similarity_threshold: float = 0.3
    
    # Workflow Configuration
    max_workflow_steps: int = 20
    workflow_timeout_minutes: int = 30
    max_concurrent_workflows: int = 50
    
    # Monitoring and Logging
    enable_metrics: bool = True
    metrics_port: int = 9090
    log_format: str = "json"  # json or text

    # Pydantic settings (v2)
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
        
    def get_allowed_extensions(self) -> list:
        """Get list of allowed file extensions"""
        return [ext.strip() for ext in self.allowed_file_extensions.split(",")]
    
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment.lower() == "production"
    
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.environment.lower() == "development"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


def get_database_url() -> str:
    """Get database URL with fallback"""
    settings = get_settings()
    return settings.database_url


def get_redis_url() -> str:
    """Get Redis URL with fallback"""
    settings = get_settings()
    return settings.redis_url


def validate_settings() -> tuple[bool, list[str]]:
    """Validate all required settings are configured"""
    settings = get_settings()
    errors = []
    
    # Check required Slack settings
    if not settings.slack_bot_token:
        errors.append("SLACK_BOT_TOKEN is required")
    
    if not settings.slack_app_token:
        errors.append("SLACK_APP_TOKEN is required")
    
    # Check required GitHub settings
    if not settings.github_token:
        errors.append("GITHUB_TOKEN is required")
    
    # Check transformer settings if enabled
    if settings.enable_transformers:
        # No API key required for transformers, just log
        pass
    
    # Check database settings
    if not settings.database_url:
        errors.append("DATABASE_URL is required")
    
    # Check Redis settings
    if not settings.redis_url:
        errors.append("REDIS_URL is required")
    
    # Validate secret key in production
    if settings.is_production() and settings.secret_key == "your-secret-key-change-in-production":
        errors.append("SECRET_KEY must be changed in production")
    
    return len(errors) == 0, errors


def print_configuration():
    """Print current configuration (excluding secrets)"""
    settings = get_settings()
    
    print(f"🔧 {settings.app_name} v{settings.app_version}")
    print(f"Environment: {settings.environment}")
    print(f"Log Level: {settings.log_level}")
    print(f"API: {settings.api_host}:{settings.api_port}")
    print(f"Database: {settings.database_url.split('@')[1] if '@' in settings.database_url else 'Not configured'}")
    print(f"Redis: {settings.redis_url}")
    print(f"Features:")
    print(f"  - Transformers: {'✅' if settings.enable_transformers else '❌'}")
    print(f"  - spaCy: {'✅' if settings.enable_spacy else '❌'}")
    print(f"  - Code Generation: {'✅' if settings.enable_code_generation else '❌'}")
    print(f"  - Auto PR Creation: {'✅' if settings.enable_auto_pr_creation else '❌'}")
    print(f"Rate Limiting: {settings.rate_limit_requests} requests per {settings.rate_limit_window//60} minutes")
    print(f"Max File Size: {settings.max_file_size_mb}MB")
    print(f"Allowed Extensions: {settings.get_allowed_extensions()}")


if __name__ == "__main__":
    # Test configuration
    is_valid, validation_errors = validate_settings()
    
    if is_valid:
        print("✅ Configuration is valid")
        print_configuration()
    else:
        print("❌ Configuration errors:")
        for error in validation_errors:
            print(f"  - {error}")
        exit(1)
