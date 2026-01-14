"""Configuration Management Service for API Keys and Settings."""
import os
import re
import json
import shutil
import time
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv, set_key, get_key
import praw

from services.audit_logger import AuditLogger


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__(f"Configuration validation failed: {', '.join(errors)}")


class ConfigManager:
    """Manage .env file operations with validation, backup, and restore."""
    
    # Configuration field definitions
    CONFIG_FIELDS = {
        'api_keys': {
            'OPENAI_API_KEY': {
                'label': 'OpenAI API Key',
                'pattern': r'^sk-[a-zA-Z0-9_-]{32,}$',
                'required': True,
                'masked': True,
                'test_url': 'https://api.openai.com/v1/models',
            },
            'REDDIT_CLIENT_ID': {
                'label': 'Reddit Client ID',
                'pattern': r'^[a-zA-Z0-9_-]{14,}$',
                'required': True,
                'masked': False,
            },
            'REDDIT_CLIENT_SECRET': {
                'label': 'Reddit Client Secret',
                'pattern': r'^[a-zA-Z0-9_-]{27,}$',
                'required': True,
                'masked': True,
            },
            'REDDIT_USER_AGENT': {
                'label': 'Reddit User Agent',
                'pattern': r'^.{5,}$',
                'required': True,
                'masked': False,
            },
            'GUMROAD_ACCESS_TOKEN': {
                'label': 'Gumroad Access Token',
                'pattern': r'^[a-zA-Z0-9_-]{32,}$',
                'required': True,
                'masked': True,
            },
        },
        'toggles': {
            'OPENAI_ENABLED': {'label': 'Enable OpenAI', 'type': 'boolean', 'default': True},
            'REDDIT_ENABLED': {'label': 'Enable Reddit Ingestion', 'type': 'boolean', 'default': True},
            'GUMROAD_ENABLED': {'label': 'Enable Gumroad Publishing', 'type': 'boolean', 'default': True},
            'KILL_SWITCH': {
                'label': 'Kill Switch (Stop All Pipeline)',
                'type': 'boolean',
                'default': False,
                'warning': 'Enabling this will stop all pipeline execution!',
            },
        },
        'cost_limits': {
            'MAX_USD_PER_RUN': {'label': 'Max USD per Run', 'type': 'float', 'min': 0.01, 'max': 1000.0, 'default': 5.0},
            'MAX_USD_LIFETIME': {'label': 'Max USD Lifetime', 'type': 'float', 'min': 1.0, 'max': 10000.0, 'default': 100.0},
            'MAX_TOKENS_PER_RUN': {'label': 'Max Tokens per Run', 'type': 'integer', 'min': 1000, 'max': 1000000, 'default': 50000},
        },
        'pipeline': {
            'REDDIT_SUBREDDITS': {'label': 'Subreddits (comma-separated)', 'type': 'string', 'pattern': r'^[a-zA-Z0-9_,-]+$', 'default': 'Entrepreneur,SaaS,startups'},
            'REDDIT_MIN_SCORE': {'label': 'Minimum Reddit Score', 'type': 'integer', 'min': 0, 'max': 100000, 'default': 10},
            'REDDIT_POST_LIMIT': {'label': 'Posts per Run', 'type': 'integer', 'min': 1, 'max': 100, 'default': 25},
        },
    }
    
    def __init__(self, env_path: str = '.env', backup_dir: str = './config_backups'):
        """Initialize ConfigManager.
        
        Args:
            env_path: Path to .env file
            backup_dir: Directory for configuration backups
        """
        self.env_path = env_path
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        self.audit_logger = AuditLogger()
        
        # Ensure .env file exists
        if not os.path.exists(self.env_path):
            raise FileNotFoundError(f".env file not found at {self.env_path}")
        
        # Set secure permissions on .env file
        os.chmod(self.env_path, 0o600)
    
    def get_current_config(self) -> Dict[str, Any]:
        """Retrieve current configuration with masked sensitive values.
        
        Returns:
            Dictionary containing current configuration
        """
        load_dotenv(self.env_path, override=True)
        
        config = {}
        
        # Load all configuration sections
        for section_name, fields in self.CONFIG_FIELDS.items():
            config[section_name] = {}
            for field_name, field_meta in fields.items():
                value = os.getenv(field_name)
                
                if value is not None:
                    # Mask sensitive values
                    if field_meta.get('masked', False):
                        value = self._mask_value(value)
                    
                    # Convert types
                    field_type = field_meta.get('type', 'string')
                    if field_type == 'boolean':
                        value = value.lower() in ('true', '1', 'yes')
                    elif field_type == 'integer':
                        try:
                            value = int(value)
                        except ValueError:
                            value = field_meta.get('default', 0)
                    elif field_type == 'float':
                        try:
                            value = float(value)
                        except ValueError:
                            value = field_meta.get('default', 0.0)
                
                config[section_name][field_name] = value
        
        return config
    
    def update_config(self, updates: Dict[str, Dict[str, Any]], user_ip: str = 'unknown') -> Dict[str, Any]:
        """Validate and apply configuration updates with backup.
        
        Args:
            updates: Dictionary of updates grouped by section
            user_ip: IP address of user making changes
        
        Returns:
            Dictionary with success status and messages
        
        Raises:
            ConfigValidationError: If validation fails
        """
        # Validate all updates first
        errors = self._validate_updates(updates)
        if errors:
            raise ConfigValidationError(errors)
        
        # Create backup before making changes
        backup_path = self._create_backup()
        
        try:
            # Apply all updates
            self._apply_updates(updates)
            
            # Reload environment variables
            load_dotenv(self.env_path, override=True)
            
            # Log the configuration change
            self.audit_logger.log(
                action='config_updated',
                details={
                    'user_ip': user_ip,
                    'backup_created': str(backup_path),
                    'sections_updated': list(updates.keys()),
                    'timestamp': datetime.now().isoformat()
                }
            )
            
            return {
                'success': True,
                'message': 'Configuration updated successfully',
                'backup_created': str(backup_path),
                'warnings': []
            }
            
        except Exception as e:
            # Restore from backup on failure
            self._restore_backup(backup_path)
            
            self.audit_logger.log(
                action='error_occurred',
                details={
                    'error': str(e),
                    'user_ip': user_ip,
                    'operation': 'config_update',
                    'restored_from': str(backup_path)
                }
            )
            
            raise ConfigValidationError([f"Failed to update configuration: {str(e)}"])
    
    def test_api_key(self, service: str, api_key: str) -> Dict[str, Any]:
        """Test API key validity.
        
        Args:
            service: Service name (OPENAI, REDDIT, GUMROAD)
            api_key: API key to test
        
        Returns:
            Dictionary with test results
        """
        try:
            if service.upper() == 'OPENAI':
                success, message = self._test_openai_key(api_key)
            elif service.upper() == 'REDDIT':
                # For Reddit, need all three credentials
                return {'success': False, 'message': 'Reddit requires client_id, client_secret, and user_agent together'}
            elif service.upper() == 'GUMROAD':
                success, message = self._test_gumroad_key(api_key)
            else:
                return {'success': False, 'message': f'Unknown service: {service}'}
            
            self.audit_logger.log(
                action='config_test',
                details={
                    'service': service,
                    'success': success,
                    'message': message,
                    'timestamp': datetime.now().isoformat()
                }
            )
            
            return {'success': success, 'message': message}
            
        except Exception as e:
            return {'success': False, 'message': f'Test failed: {str(e)}'}
    
    def test_reddit_credentials(self, client_id: str, client_secret: str, user_agent: str) -> Dict[str, Any]:
        """Test Reddit credentials.
        
        Args:
            client_id: Reddit client ID
            client_secret: Reddit client secret
            user_agent: Reddit user agent
        
        Returns:
            Dictionary with test results
        """
        try:
            success, message = self._test_reddit_credentials(client_id, client_secret, user_agent)
            
            self.audit_logger.log(
                action='config_test',
                details={
                    'service': 'REDDIT',
                    'success': success,
                    'message': message,
                    'timestamp': datetime.now().isoformat()
                }
            )
            
            return {'success': success, 'message': message}
            
        except Exception as e:
            return {'success': False, 'message': f'Test failed: {str(e)}'}
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List all configuration backups.
        
        Returns:
            List of backup information dictionaries
        """
        backups = []
        
        for backup_file in sorted(self.backup_dir.glob('env_backup_*.txt'), reverse=True):
            stat = backup_file.stat()
            backups.append({
                'filename': backup_file.name,
                'timestamp': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'size': stat.st_size
            })
        
        return backups
    
    def restore_from_backup(self, backup_filename: str, user_ip: str = 'unknown') -> Dict[str, Any]:
        """Restore configuration from backup.
        
        Args:
            backup_filename: Name of backup file to restore
            user_ip: IP address of user performing restore
        
        Returns:
            Dictionary with restore results
        
        Raises:
            FileNotFoundError: If backup file not found
        """
        backup_path = self.backup_dir / backup_filename
        
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_filename}")
        
        # Create a backup of current state before restoring
        current_backup = self._create_backup()
        
        try:
            self._restore_backup(backup_path)
            
            self.audit_logger.log(
                action='config_restored',
                details={
                    'user_ip': user_ip,
                    'restored_from': backup_filename,
                    'current_backup': str(current_backup),
                    'timestamp': datetime.now().isoformat()
                }
            )
            
            return {
                'success': True,
                'message': f'Configuration restored from {backup_filename}',
                'current_backup': str(current_backup)
            }
            
        except Exception as e:
            self.audit_logger.log(
                action='error_occurred',
                details={
                    'error': str(e),
                    'user_ip': user_ip,
                    'operation': 'config_restore',
                    'attempted_restore': backup_filename
                }
            )
            
            raise ConfigValidationError([f"Failed to restore configuration: {str(e)}"])
    
    def _validate_updates(self, updates: Dict[str, Dict[str, Any]]) -> List[str]:
        """Validate all configuration updates.
        
        Args:
            updates: Dictionary of updates to validate
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        for section_name, section_updates in updates.items():
            if section_name not in self.CONFIG_FIELDS:
                errors.append(f"Unknown configuration section: {section_name}")
                continue
            
            field_definitions = self.CONFIG_FIELDS[section_name]
            
            for field_name, value in section_updates.items():
                if field_name not in field_definitions:
                    errors.append(f"Unknown field in {section_name}: {field_name}")
                    continue
                
                field_meta = field_definitions[field_name]
                
                # Validate based on field type
                field_type = field_meta.get('type', 'string')
                
                if field_type == 'boolean':
                    if not isinstance(value, bool) and value not in ['true', 'false', 'True', 'False']:
                        errors.append(f"{field_name}: Must be a boolean value")
                
                elif field_type == 'integer':
                    try:
                        int_value = int(value)
                        if 'min' in field_meta and int_value < field_meta['min']:
                            errors.append(f"{field_name}: Must be at least {field_meta['min']}")
                        if 'max' in field_meta and int_value > field_meta['max']:
                            errors.append(f"{field_name}: Must be at most {field_meta['max']}")
                    except (ValueError, TypeError):
                        errors.append(f"{field_name}: Must be an integer")
                
                elif field_type == 'float':
                    try:
                        float_value = float(value)
                        if 'min' in field_meta and float_value < field_meta['min']:
                            errors.append(f"{field_name}: Must be at least {field_meta['min']}")
                        if 'max' in field_meta and float_value > field_meta['max']:
                            errors.append(f"{field_name}: Must be at most {field_meta['max']}")
                    except (ValueError, TypeError):
                        errors.append(f"{field_name}: Must be a number")
                
                elif field_type == 'string' or section_name == 'api_keys':
                    # Pattern validation
                    if 'pattern' in field_meta:
                        if not re.match(field_meta['pattern'], str(value)):
                            errors.append(f"{field_name}: Invalid format")
                    
                    # Required validation
                    if field_meta.get('required', False) and not value:
                        errors.append(f"{field_name}: Required field cannot be empty")
        
        return errors
    
    def _create_backup(self) -> Path:
        """Create timestamped backup of .env file.
        
        Returns:
            Path to created backup file
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')  # Include microseconds
        backup_filename = f"env_backup_{timestamp}.txt"
        backup_path = self.backup_dir / backup_filename
        
        # Copy .env to backup with secure permissions
        shutil.copy2(self.env_path, backup_path)
        os.chmod(backup_path, 0o600)
        
        self.audit_logger.log(
            action='config_backup_created',
            details={
                'backup_path': str(backup_path),
                'timestamp': datetime.now().isoformat()
            }
        )
        
        # Clean up old backups (keep only last 7)
        self._cleanup_old_backups(keep=7)
        
        return backup_path
    
    def _restore_backup(self, backup_path: Path):
        """Restore configuration from backup file.
        
        Args:
            backup_path: Path to backup file
        """
        # Atomic restore: write to temp file then rename
        temp_path = f"{self.env_path}.tmp"
        
        shutil.copy2(backup_path, temp_path)
        os.chmod(temp_path, 0o600)
        
        # Atomic rename
        os.replace(temp_path, self.env_path)
        
        # Reload environment
        load_dotenv(self.env_path, override=True)
    
    def _apply_updates(self, updates: Dict[str, Dict[str, Any]]):
        """Apply validated updates to .env file.
        
        Args:
            updates: Dictionary of updates to apply
        """
        for section_name, section_updates in updates.items():
            for field_name, value in section_updates.items():
                # Convert boolean values to string
                if isinstance(value, bool):
                    value = 'true' if value else 'false'
                
                # Write to .env file
                set_key(self.env_path, field_name, str(value))
    
    def _mask_value(self, value: str) -> str:
        """Mask sensitive values (show first 3 and last 4 chars).
        
        Args:
            value: Value to mask
        
        Returns:
            Masked value
        """
        if not value or len(value) < 8:
            return '***'
        
        return f"{value[:3]}{'*' * (len(value) - 7)}{value[-4:]}"
    
    def _test_openai_key(self, api_key: str) -> tuple[bool, str]:
        """Test OpenAI API key.
        
        Args:
            api_key: OpenAI API key
        
        Returns:
            Tuple of (success, message)
        """
        try:
            response = requests.get(
                'https://api.openai.com/v1/models',
                headers={'Authorization': f'Bearer {api_key}'},
                timeout=10
            )
            
            if response.status_code == 200:
                return True, 'OpenAI API key is valid'
            elif response.status_code == 401:
                return False, 'Invalid OpenAI API key'
            else:
                return False, f'OpenAI API returned status {response.status_code}'
        
        except requests.RequestException as e:
            return False, f'Connection error: {str(e)}'
    
    def _test_reddit_credentials(self, client_id: str, client_secret: str, user_agent: str) -> tuple[bool, str]:
        """Test Reddit credentials.
        
        Args:
            client_id: Reddit client ID
            client_secret: Reddit client secret
            user_agent: Reddit user agent
        
        Returns:
            Tuple of (success, message)
        """
        try:
            reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent
            )
            
            # Try to access read-only API
            reddit.subreddit('test').hot(limit=1)
            
            return True, 'Reddit credentials are valid'
        
        except Exception as e:
            return False, f'Reddit authentication failed: {str(e)}'
    
    def _test_gumroad_key(self, api_key: str) -> tuple[bool, str]:
        """Test Gumroad API key.
        
        Args:
            api_key: Gumroad access token
        
        Returns:
            Tuple of (success, message)
        """
        try:
            response = requests.get(
                'https://api.gumroad.com/v2/user',
                params={'access_token': api_key},
                timeout=10
            )
            
            if response.status_code == 200:
                return True, 'Gumroad API key is valid'
            elif response.status_code == 401:
                return False, 'Invalid Gumroad API key'
            else:
                return False, f'Gumroad API returned status {response.status_code}'
        
        except requests.RequestException as e:
            return False, f'Connection error: {str(e)}'
    
    def _cleanup_old_backups(self, keep: int = 7):
        """Remove old backups, keeping only the most recent.
        
        Args:
            keep: Number of backups to keep
        """
        backups = sorted(self.backup_dir.glob('env_backup_*.txt'), reverse=True)
        
        for old_backup in backups[keep:]:
            old_backup.unlink()
