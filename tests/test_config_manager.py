"""Tests for ConfigManager service."""
import pytest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from services.config_manager import ConfigManager, ConfigValidationError


@pytest.fixture
def temp_env_file():
    """Create a temporary .env file for testing."""
    temp_dir = tempfile.mkdtemp()
    env_path = os.path.join(temp_dir, '.env')
    
    # Create a basic .env file
    with open(env_path, 'w') as f:
        f.write("""
OPENAI_API_KEY=sk-test1234567890abcdefghijklmnopqrstuv
REDDIT_CLIENT_ID=test_client_id_12345
REDDIT_CLIENT_SECRET=test_client_secret_1234567890
REDDIT_USER_AGENT=Test-Agent/1.0
GUMROAD_ACCESS_TOKEN=test_gumroad_token_1234567890abcdef

OPENAI_ENABLED=true
REDDIT_ENABLED=true
GUMROAD_ENABLED=true
KILL_SWITCH=false

MAX_USD_PER_RUN=5.0
MAX_USD_LIFETIME=100.0
MAX_TOKENS_PER_RUN=50000

REDDIT_SUBREDDITS=Entrepreneur,SaaS,startups
REDDIT_MIN_SCORE=10
REDDIT_POST_LIMIT=25
""")
    
    yield env_path, temp_dir
    
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def config_manager(temp_env_file):
    """Create a ConfigManager instance with temp files."""
    env_path, temp_dir = temp_env_file
    backup_dir = os.path.join(temp_dir, 'backups')
    
    with patch('services.config_manager.AuditLogger'):
        manager = ConfigManager(env_path=env_path, backup_dir=backup_dir)
        yield manager


@pytest.mark.unit
def test_get_current_config(config_manager):
    """Test retrieving current configuration."""
    config = config_manager.get_current_config()
    
    assert 'api_keys' in config
    assert 'toggles' in config
    assert 'cost_limits' in config
    assert 'pipeline' in config
    
    # Check that API key is masked
    assert config['api_keys']['OPENAI_API_KEY'].startswith('sk-')
    assert '***' in config['api_keys']['OPENAI_API_KEY']


@pytest.mark.unit
def test_mask_value(config_manager):
    """Test value masking."""
    masked = config_manager._mask_value('sk-1234567890abcdefghijklmnopqrst')
    assert masked.startswith('sk-')
    assert masked.endswith('rst')
    assert '***' in masked
    
    # Short values
    masked_short = config_manager._mask_value('short')
    assert masked_short == '***'


@pytest.mark.unit
def test_validate_updates_valid(config_manager):
    """Test validation of valid updates."""
    updates = {
        'toggles': {
            'OPENAI_ENABLED': True,
            'KILL_SWITCH': False
        },
        'cost_limits': {
            'MAX_USD_PER_RUN': 10.0,
            'MAX_TOKENS_PER_RUN': 75000
        }
    }
    
    errors = config_manager._validate_updates(updates)
    assert len(errors) == 0


@pytest.mark.unit
def test_validate_updates_invalid(config_manager):
    """Test validation of invalid updates."""
    updates = {
        'cost_limits': {
            'MAX_USD_PER_RUN': -1.0,  # Invalid: too low
            'MAX_TOKENS_PER_RUN': 2000000  # Invalid: too high
        },
        'pipeline': {
            'REDDIT_MIN_SCORE': -5  # Invalid: negative
        }
    }
    
    errors = config_manager._validate_updates(updates)
    assert len(errors) > 0


@pytest.mark.unit
def test_validate_updates_invalid_pattern(config_manager):
    """Test validation of invalid API key patterns."""
    updates = {
        'api_keys': {
            'OPENAI_API_KEY': 'invalid-key'  # Invalid pattern
        }
    }
    
    errors = config_manager._validate_updates(updates)
    assert len(errors) > 0
    assert any('Invalid format' in error for error in errors)


@pytest.mark.unit
def test_create_backup(config_manager):
    """Test backup creation."""
    backup_path = config_manager._create_backup()
    
    assert backup_path.exists()
    assert backup_path.name.startswith('env_backup_')
    assert backup_path.suffix == '.txt'
    
    # Check file permissions
    stat = os.stat(backup_path)
    assert oct(stat.st_mode)[-3:] == '600'


@pytest.mark.unit
def test_list_backups(config_manager):
    """Test listing backups."""
    import time
    # Create a few backups with small delays to ensure different timestamps
    initial_count = len(config_manager.list_backups())
    
    config_manager._cleanup_old_backups = lambda keep=7: None  # Disable cleanup for this test
    
    config_manager._create_backup()
    time.sleep(0.1)
    config_manager._create_backup()
    time.sleep(0.1)
    
    backups = config_manager.list_backups()
    assert len(backups) >= initial_count + 2
    
    for backup in backups:
        assert 'filename' in backup
        assert 'timestamp' in backup
        assert 'size' in backup


@pytest.mark.unit
def test_update_config_success(config_manager):
    """Test successful configuration update."""
    updates = {
        'toggles': {
            'OPENAI_ENABLED': False
        },
        'cost_limits': {
            'MAX_USD_PER_RUN': 7.5
        }
    }
    
    result = config_manager.update_config(updates, user_ip='127.0.0.1')
    
    assert result['success'] is True
    assert 'backup_created' in result
    
    # Verify the update was applied
    config = config_manager.get_current_config()
    assert config['toggles']['OPENAI_ENABLED'] is False
    assert config['cost_limits']['MAX_USD_PER_RUN'] == 7.5


@pytest.mark.unit
def test_update_config_validation_error(config_manager):
    """Test configuration update with validation errors."""
    updates = {
        'cost_limits': {
            'MAX_USD_PER_RUN': -10.0  # Invalid
        }
    }
    
    with pytest.raises(ConfigValidationError) as exc_info:
        config_manager.update_config(updates, user_ip='127.0.0.1')
    
    assert len(exc_info.value.errors) > 0


@pytest.mark.unit
def test_restore_backup(config_manager):
    """Test restoring from backup."""
    # Create initial backup
    original_backup = config_manager._create_backup()
    
    # Make changes
    updates = {
        'toggles': {
            'KILL_SWITCH': True
        }
    }
    config_manager.update_config(updates, user_ip='127.0.0.1')
    
    # Verify change was applied - reload env first
    from dotenv import load_dotenv
    load_dotenv(config_manager.env_path, override=True)
    config = config_manager.get_current_config()
    assert config['toggles']['KILL_SWITCH'] is True
    
    # Restore from original backup
    result = config_manager.restore_from_backup(original_backup.name, user_ip='127.0.0.1')
    
    assert result['success'] is True
    
    # Verify restoration - reload env again
    load_dotenv(config_manager.env_path, override=True)
    config = config_manager.get_current_config()
    assert config['toggles']['KILL_SWITCH'] is False


@pytest.mark.unit
def test_cleanup_old_backups(config_manager):
    """Test cleanup of old backups."""
    import time
    # Disable cleanup during creation
    original_cleanup = config_manager._cleanup_old_backups
    config_manager._cleanup_old_backups = lambda keep=7: None
    
    # Create more backups than the keep limit with delays
    for i in range(10):
        config_manager._create_backup()
        time.sleep(0.1)  # Small delay to ensure different timestamps
    
    # Re-enable cleanup and run it
    config_manager._cleanup_old_backups = original_cleanup
    config_manager._cleanup_old_backups(keep=7)
    
    backups = config_manager.list_backups()
    assert len(backups) == 7


@pytest.mark.unit
@patch('services.config_manager.requests.get')
def test_test_openai_key_valid(mock_get, config_manager):
    """Test OpenAI API key validation - valid key."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_get.return_value = mock_response
    
    success, message = config_manager._test_openai_key('sk-test123')
    
    assert success is True
    assert 'valid' in message.lower()


@pytest.mark.unit
@patch('services.config_manager.requests.get')
def test_test_openai_key_invalid(mock_get, config_manager):
    """Test OpenAI API key validation - invalid key."""
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_get.return_value = mock_response
    
    success, message = config_manager._test_openai_key('sk-invalid')
    
    assert success is False
    assert 'invalid' in message.lower()


@pytest.mark.unit
@patch('services.config_manager.requests.get')
def test_test_gumroad_key_valid(mock_get, config_manager):
    """Test Gumroad API key validation - valid key."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_get.return_value = mock_response
    
    success, message = config_manager._test_gumroad_key('test_token_123')
    
    assert success is True
    assert 'valid' in message.lower()


@pytest.mark.unit
@patch('services.config_manager.praw.Reddit')
def test_test_reddit_credentials_valid(mock_reddit, config_manager):
    """Test Reddit credentials validation - valid credentials."""
    mock_instance = MagicMock()
    mock_reddit.return_value = mock_instance
    
    success, message = config_manager._test_reddit_credentials(
        'client_id', 'client_secret', 'user_agent'
    )
    
    assert success is True
    assert 'valid' in message.lower()


@pytest.mark.unit
@patch('services.config_manager.praw.Reddit')
def test_test_reddit_credentials_invalid(mock_reddit, config_manager):
    """Test Reddit credentials validation - invalid credentials."""
    mock_reddit.side_effect = Exception("Authentication failed")
    
    success, message = config_manager._test_reddit_credentials(
        'bad_id', 'bad_secret', 'user_agent'
    )
    
    assert success is False
    assert 'failed' in message.lower()
