# utilities/config.py
"""
Configuration Module for Task 9: Centralized configuration management.
"""
import os
import logging
from typing import Dict, Any

class AIConfig:
    """AI Model Configuration"""
    
    # Model settings
    MODEL_NAME = "sshleifer/distilbart-cnn-12-6"
    FALLBACK_MODEL = "sshleifer/distilbart-cnn-6-6"  # Smaller model for testing/fallback
    
    # Processing settings
    MAX_INPUT_LENGTH = 1024  # Max tokens for input
    MIN_SUMMARY_LENGTH = 50  # Minimum summary length
    MAX_SUMMARY_LENGTH = 150  # Maximum summary length
    DEFAULT_COMPRESSION_RATIO = 0.3  # Default compression ratio
    
    # Chunking settings
    CHUNK_SIZE_TOKENS = 800  # Max tokens per chunk
    CHUNK_OVERLAP = 50  # Token overlap between chunks
    
    # Performance settings
    USE_GPU = False  # Set to True if GPU available
    BATCH_SIZE = 1  # For batch processing
    MAX_CONCURRENT_REQUESTS = 5  # Max concurrent API requests
    
    # Timeout settings (seconds)
    MODEL_LOAD_TIMEOUT = 60
    INFERENCE_TIMEOUT = 300  # 5 minutes
    API_REQUEST_TIMEOUT = 30
    
    # Cache settings
    ENABLE_CACHE = True
    CACHE_MAX_SIZE = 100  # Max cached summaries
    CACHE_TTL = 3600  # Cache time-to-live in seconds (1 hour)


class APIConfig:
    """API Configuration"""
    
    # Request limits
    MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_TEXT_LENGTH = 1000000  # 1 million characters
    MIN_TEXT_LENGTH = 50  # Minimum characters for summarization
    
    # Rate limiting
    RATE_LIMIT_ENABLED = True
    RATE_LIMIT_REQUESTS = 100  # Requests per hour per IP
    RATE_LIMIT_WINDOW = 3600  # 1 hour in seconds
    
    # Security
    ALLOWED_FILE_TYPES = ['.txt', '.pdf', '.doc', '.docx', '.rtf']
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    # Response settings
    ENABLE_LOGGING = True
    LOG_LEVEL = logging.INFO
    LOG_FILE = "logs/api_requests.log"
    
    # Monitoring
    ENABLE_METRICS = True
    METRICS_PORT = 9090  # For Prometheus/metrics endpoint


class DatabaseConfig:
    """Database Configuration"""
    
    # SQLAlchemy settings
    SQLALCHEMY_DATABASE_URI = "sqlite:///book_summarizer.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'max_overflow': 20,
        'pool_timeout': 30,
        'pool_recycle': 3600,
    }
    
    # Summary storage
    STORE_SUMMARIES = True
    MAX_SUMMARY_HISTORY = 100  # Max summaries per user
    SUMMARY_RETENTION_DAYS = 30  # Days to keep summaries


class LoggingConfig:
    """Logging Configuration"""
    
    # Log levels
    LOG_LEVEL = logging.INFO
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
    
    # Log files
    APP_LOG_FILE = "logs/app.log"
    AI_LOG_FILE = "logs/ai_model.log"
    API_LOG_FILE = "logs/api.log"
    ERROR_LOG_FILE = "logs/error.log"
    
    # Log rotation
    LOG_ROTATION_SIZE = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 5  # Keep 5 backup files


class DevelopmentConfig(AIConfig, APIConfig, DatabaseConfig, LoggingConfig):
    """Development Configuration"""
    DEBUG = True
    TESTING = False
    SECRET_KEY = "dev-secret-key-change-in-production"
    
    # Override some settings for development
    USE_GPU = False
    ENABLE_CACHE = True
    LOG_LEVEL = logging.DEBUG


class ProductionConfig(AIConfig, APIConfig, DatabaseConfig, LoggingConfig):
    """Production Configuration"""
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-in-production")
    
    # Override some settings for production
    USE_GPU = os.environ.get("USE_GPU", "false").lower() == "true"
    ENABLE_CACHE = True
    LOG_LEVEL = logging.INFO
    
    # Production-specific overrides
    MAX_CONCURRENT_REQUESTS = 10
    RATE_LIMIT_REQUESTS = 1000  # Higher limit for production


class TestingConfig(AIConfig, APIConfig, DatabaseConfig, LoggingConfig):
    """Testing Configuration"""
    DEBUG = True
    TESTING = True
    SECRET_KEY = "test-secret-key"
    
    # Testing-specific overrides
    USE_GPU = False
    ENABLE_CACHE = False
    LOG_LEVEL = logging.WARNING
    
    # Use in-memory database for testing
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    
    # Faster processing for tests
    MODEL_NAME = "sshleifer/distilbart-cnn-6-6"  # Smaller model
    INFERENCE_TIMEOUT = 30  # 30 seconds for tests


def get_config(config_name: str = "development") -> Dict[str, Any]:
    """
    Get configuration based on environment.
    
    Args:
        config_name: Name of configuration ('development', 'production', 'testing')
        
    Returns:
        Dictionary with configuration settings
    """
    configs = {
        "development": DevelopmentConfig,
        "production": ProductionConfig,
        "testing": TestingConfig
    }
    
    config_class = configs.get(config_name.lower(), DevelopmentConfig)
    
    # Convert class to dictionary
    config_dict = {}
    for attr in dir(config_class):
        if not attr.startswith("__") and not callable(getattr(config_class, attr)):
            config_dict[attr] = getattr(config_class, attr)
    
    return config_dict


def setup_logging(config: Dict[str, Any]) -> None:
    """
    Setup logging based on configuration.
    
    Args:
        config: Configuration dictionary
    """
    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(config.get("APP_LOG_FILE", "logs/app.log"))
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Configure root logger
    logging.basicConfig(
        level=config.get("LOG_LEVEL", logging.INFO),
        format=config.get("LOG_FORMAT", '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
        datefmt=config.get("LOG_DATE_FORMAT", '%Y-%m-%d %H:%M:%S'),
        handlers=[
            logging.FileHandler(config.get("APP_LOG_FILE", "logs/app.log")),
            logging.StreamHandler()  # Also log to console
        ]
    )
    
    # Configure specific loggers
    ai_logger = logging.getLogger("ai_model")
    ai_handler = logging.FileHandler(config.get("AI_LOG_FILE", "logs/ai_model.log"))
    ai_handler.setFormatter(logging.Formatter(config.get("LOG_FORMAT")))
    ai_logger.addHandler(ai_handler)
    
    api_logger = logging.getLogger("api")
    api_handler = logging.FileHandler(config.get("API_LOG_FILE", "logs/api.log"))
    api_handler.setFormatter(logging.Formatter(config.get("LOG_FORMAT")))
    api_logger.addHandler(api_handler)
    
    # Error logger for critical errors
    error_logger = logging.getLogger("error")
    error_handler = logging.FileHandler(config.get("ERROR_LOG_FILE", "logs/error.log"))
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(config.get("LOG_FORMAT")))
    error_logger.addHandler(error_handler)


# Test the configuration
if __name__ == "__main__":
    print("=" * 60)
    print("Testing Configuration Module")
    print("=" * 60)
    
    # Test development config
    dev_config = get_config("development")
    print(f"1. Development Config:")
    print(f"   Model: {dev_config.get('MODEL_NAME')}")
    print(f"   Debug: {dev_config.get('DEBUG')}")
    print(f"   Log Level: {dev_config.get('LOG_LEVEL')}")
    
    # Test production config
    prod_config = get_config("production")
    print(f"\n2. Production Config:")
    print(f"   Model: {prod_config.get('MODEL_NAME')}")
    print(f"   Debug: {prod_config.get('DEBUG')}")
    print(f"   Rate Limit: {prod_config.get('RATE_LIMIT_REQUESTS')} requests/hour")
    
    # Test testing config
    test_config = get_config("testing")
    print(f"\n3. Testing Config:")
    print(f"   Model: {test_config.get('MODEL_NAME')}")
    print(f"   Testing: {test_config.get('TESTING')}")
    print(f"   Database: {test_config.get('SQLALCHEMY_DATABASE_URI')}")
    
    print("\n" + "=" * 60)
    print("✅ Configuration Module Test PASSED")
    print("=" * 60)