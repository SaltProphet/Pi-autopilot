import os
from pydantic_settings import BaseSettings
from services.config_validator import ConfigValidator, ConfigValidationError


class Settings(BaseSettings):
    reddit_client_id: str
    reddit_client_secret: str
    reddit_user_agent: str = "Pi-Autopilot/2.0"
    
    openai_api_key: str
    openai_model: str = "gpt-4"
    
    gumroad_access_token: str
    
    database_path: str = "./data/pipeline.db"
    artifacts_path: str = "./data/artifacts"
    
    reddit_subreddits: str = "SideProject,Entrepreneur,startups"
    reddit_min_score: int = 10
    reddit_post_limit: int = 20
    
    max_regeneration_attempts: int = 1
    
    max_tokens_per_run: int = 50000
    max_usd_per_run: float = 5.0
    max_usd_lifetime: float = 100.0
    
    kill_switch: bool = False
    dry_run: bool = True
    
    openai_input_token_price: float = 0.03
    openai_output_token_price: float = 0.06
    
    # Sales feedback configuration
    zero_sales_suppression_count: int = 5
    refund_rate_max: float = 0.3
    sales_lookback_days: int = 30
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

# Validate configuration on startup
try:
    validator = ConfigValidator(settings)
    validator.validate_or_raise()
except ConfigValidationError as e:
    print("CONFIGURATION ERROR:")
    for error in e.errors:
        print(f"  - {error}")
    raise SystemExit("Configuration validation failed. Check .env file and try again.")

os.makedirs(os.path.dirname(settings.database_path), exist_ok=True)
os.makedirs(settings.artifacts_path, exist_ok=True)
