"""
Configuration manager for web-based API key and settings management.
Handles secure storage, validation, backup, and testing of configuration.
"""
import os
import re
import stat
from pathlib import Path
from typing import Dict, Tuple, List, Optional
from datetime import datetime
from dotenv import set_key, dotenv_values
import requests
import praw
from services.audit_logger import AuditLogger


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors or []


class ConfigManager:
    """Manage configuration settings with validation, backup, and testing."""
    
    # Configuration schema with validation rules
    CONFIG_SCHEMA = {
        'api_keys': {
            'OPENAI_API_KEY': {
                'pattern': r'^sk-[a-zA-Z0-9]{32,}$',
                'required': True,
                'masked': True,
                'description': 'OpenAI API Key'
            },
            'REDDIT_CLIENT_ID': {
                'pattern': r'^[a-zA-Z0-9_-]{14,}$',
                'required': True,
                'masked': False,
                'description': 'Reddit Client ID'
            },
            'REDDIT_CLIENT_SECRET': {
                'pattern': r'^[a-zA-Z0-9_-]{27,}$',
                'required': True,
                'masked': True,
                'description': 'Reddit Client Secret'
            },
            'REDDIT_USER_AGENT': {
                'pattern': r'^.{5,}$',
                'required': True,
                'masked': False,
                'description': 'Reddit User Agent'
            },
            'GUMROAD_ACCESS_TOKEN': {
                'pattern': r'^[a-zA-Z0-9_-]{32,}$',
                'required': True,
                'masked': True,
                'description': 'Gumroad Access Token'
            }
        },
        'toggles': {
            'OPENAI_ENABLED': {
                'type': 'bool',
                'default': True,
                'description': 'Enable/disable OpenAI API calls'
            },
            'REDDIT_ENABLED': {
                'type': 'bool',
                'default': True,
                'description': 'Enable/disable Reddit ingestion'
            },
            'GUMROAD_ENABLED': {
                'type': 'bool',
                'default': True,
                'description': 'Enable/disable Gumroad publishing'
            },
            'KILL_SWITCH': {
                'type': 'bool',
                'default': False,
                'description': 'Emergency stop for entire pipeline'
            }
        },
        'cost_limits': {
            'MAX_USD_PER_RUN': {
                'type': 'float',
                'min': 0.01,
                'max': 1000.0,
                'description': 'Maximum USD cost per run'
            },
            'MAX_USD_LIFETIME': {
                'type': 'float',
                'min': 1.0,
                'max': 10000.0,
                'description': 'Maximum lifetime USD cost'
            },
            'MAX_TOKENS_PER_RUN': {
                'type': 'int',
                'min': 1000,
                'max': 1000000,
                'description': 'Maximum tokens per run'
            }
        },
        'pipeline': {
            'REDDIT_SUBREDDITS': {
                'pattern': r'^[a-zA-Z0-9_,-]+$',
                'description': 'Comma-separated list of subreddits'
            },
            'REDDIT_MIN_SCORE': {
                'type': 'int',
                'min': 0,
                'max': 100000,
                'description': 'Minimum Reddit post score'
            },
            'REDDIT_POST_LIMIT': {
                'type': 'int',
                'min': 1,
                'max': 100,
                'description': 'Maximum posts to fetch per subreddit'
            }
        }
    }
    
    def __init__(self, env_path: str = '.env'):
        """Initialize ConfigManager.
        
        Args:
            env_path: Path to .env file
        """
        self.env_path = Path(env_path)
        self.backup_dir = Path('./config_backups')
        self.backup_dir.mkdir(exist_ok=True)
        self.audit_logger = AuditLogger()
        
        # Ensure .env file exists
        if not self.env_path.exists():
            self.env_path.touch()
        
        # Set secure permissions
        self._set_secure_permissions(self.env_path)
    
    def get_current_config(self) -> Dict:
        """Get current configuration with masked sensitive values.
        
        Returns:
            Dict with configuration organized by category
        """
        # Load current .env values
        env_values = dotenv_values(str(self.env_path))
        
        config = {
            'api_keys': {},
            'toggles': {},
            'cost_limits': {},
            'pipeline': {}
        }
        
        # Process each category
        for category, fields in self.CONFIG_SCHEMA.items():
            for key, schema in fields.items():
                value = env_values.get(key, schema.get('default', ''))
                
                if category == 'api_keys':
                    # Mask sensitive API keys
                    if schema.get('masked') and value:
                        display_value = self._mask_value(value)
                    else:
                        display_value = value
                    
                    config[category][key] = {
                        'value': display_value,
                        'description': schema.get('description', ''),
                        'required': schema.get('required', False),
                        'masked': schema.get('masked', False)
                    }
                
                elif category == 'toggles':
                    # Convert string to boolean
                    if isinstance(value, bool):
                        bool_value = value
                    elif isinstance(value, str):
                        bool_value = value.lower() in ('true', '1', 'yes')
                    else:
                        bool_value = schema.get('default', False)
                    
                    config[category][key] = {
                        'value': bool_value,
                        'description': schema.get('description', '')
                    }
                
                elif category in ('cost_limits', 'pipeline'):
                    # Keep numeric/string values
                    if 'type' in schema:
                        if schema['type'] == 'int':
                            typed_value = int(value) if value else schema.get('default', 0)
                        elif schema['type'] == 'float':
                            typed_value = float(value) if value else schema.get('default', 0.0)
                        else:
                            typed_value = value
                    else:
                        typed_value = value
                    
                    config[category][key] = {
                        'value': typed_value,
                        'description': schema.get('description', ''),
                        'min': schema.get('min'),
                        'max': schema.get('max')
                    }
        
        return config
    
    def update_config(self, updates: Dict, user_ip: str = None) -> Tuple[bool, List[str]]:
        """Update configuration with validation and backup.
        
        Args:
            updates: Dictionary of updates organized by category
            user_ip: IP address of user making changes
        
        Returns:
            Tuple of (success, errors_or_warnings)
        """
        errors = []
        
        try:
            # Validate all updates
            self._validate_updates(updates)
            
            # Create backup before making changes
            backup_path = self._create_backup()
            
            try:
                # Apply updates
                self._apply_updates(updates)
                
                # Log successful update (with masked values)
                masked_updates = self._mask_updates(updates)
                self.audit_logger.log(
                    action='config_updated',
                    post_id=None,
                    run_id=None,
                    details={
                        'updates': masked_updates,
                        'user_ip': user_ip,
                        'backup_path': str(backup_path),
                        'timestamp': datetime.now().isoformat()
                    }
                )
                
                # Rotate old backups
                self._rotate_backups()
                
                return True, ["Configuration updated successfully"]
                
            except Exception as e:
                # Rollback on failure
                self._restore_backup(backup_path)
                errors.append(f"Update failed, restored from backup: {str(e)}")
                return False, errors
                
        except ConfigValidationError as e:
            return False, e.errors
        except Exception as e:
            errors.append(f"Unexpected error: {str(e)}")
            return False, errors
    
    def test_api_key(self, service: str, api_key: str) -> Tuple[bool, str]:
        """Test API key validity with actual API calls.
        
        Args:
            service: Service name (OPENAI, REDDIT, GUMROAD)
            api_key: API key to test
        
        Returns:
            Tuple of (is_valid, message)
        """
        service = service.upper()
        
        try:
            if service == 'OPENAI':
                return self._test_openai_key(api_key)
            elif service == 'REDDIT':
                return self._test_reddit_key(api_key)
            elif service == 'GUMROAD':
                return self._test_gumroad_key(api_key)
            else:
                return False, f"Unknown service: {service}"
        except Exception as e:
            return False, f"Test failed: {str(e)}"
    
    def list_backups(self) -> List[Dict]:
        """List all available configuration backups.
        
        Returns:
            List of backup metadata dicts
        """
        backups = []
        
        for backup_file in sorted(self.backup_dir.glob('env_backup_*.txt'), reverse=True):
            stat_info = backup_file.stat()
            backups.append({
                'filename': backup_file.name,
                'path': str(backup_file),
                'created_at': datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                'size_bytes': stat_info.st_size
            })
        
        return backups
    
    def restore_backup(self, backup_filename: str, user_ip: str = None) -> Tuple[bool, str]:
        """Restore configuration from a backup file.
        
        Args:
            backup_filename: Name of backup file to restore
            user_ip: IP address of user making changes
        
        Returns:
            Tuple of (success, message)
        """
        backup_path = self.backup_dir / backup_filename
        
        if not backup_path.exists():
            return False, f"Backup file not found: {backup_filename}"
        
        try:
            # Create a backup of current state before restoring
            current_backup = self._create_backup()
            
            # Restore from backup
            self._restore_backup(backup_path)
            
            # Log restoration
            self.audit_logger.log(
                action='config_restored',
                post_id=None,
                run_id=None,
                details={
                    'restored_from': backup_filename,
                    'current_backup': str(current_backup),
                    'user_ip': user_ip,
                    'timestamp': datetime.now().isoformat()
                }
            )
            
            return True, f"Configuration restored from {backup_filename}"
            
        except Exception as e:
            return False, f"Restore failed: {str(e)}"
    
    def _validate_updates(self, updates: Dict):
        """Validate all update values.
        
        Args:
            updates: Dictionary of updates organized by category
        
        Raises:
            ConfigValidationError: If validation fails
        """
        errors = []
        
        for category, fields in updates.items():
            if category not in self.CONFIG_SCHEMA:
                errors.append(f"Unknown configuration category: {category}")
                continue
            
            schema_category = self.CONFIG_SCHEMA[category]
            
            for key, value in fields.items():
                if key not in schema_category:
                    errors.append(f"Unknown configuration key: {key}")
                    continue
                
                schema = schema_category[key]
                
                # Validate API keys
                if category == 'api_keys':
                    if schema.get('required') and not value:
                        errors.append(f"{key} is required")
                    elif value and 'pattern' in schema:
                        if not re.match(schema['pattern'], value):
                            errors.append(f"{key} format is invalid")
                
                # Validate toggles
                elif category == 'toggles':
                    if not isinstance(value, bool):
                        errors.append(f"{key} must be a boolean")
                
                # Validate numeric ranges
                elif category in ('cost_limits', 'pipeline'):
                    if 'type' in schema:
                        if schema['type'] == 'int':
                            if not isinstance(value, int):
                                errors.append(f"{key} must be an integer")
                            elif 'min' in schema and value < schema['min']:
                                errors.append(f"{key} must be >= {schema['min']}")
                            elif 'max' in schema and value > schema['max']:
                                errors.append(f"{key} must be <= {schema['max']}")
                        
                        elif schema['type'] == 'float':
                            if not isinstance(value, (int, float)):
                                errors.append(f"{key} must be a number")
                            elif 'min' in schema and value < schema['min']:
                                errors.append(f"{key} must be >= {schema['min']}")
                            elif 'max' in schema and value > schema['max']:
                                errors.append(f"{key} must be <= {schema['max']}")
                    
                    elif 'pattern' in schema:
                        if not re.match(schema['pattern'], str(value)):
                            errors.append(f"{key} format is invalid")
        
        if errors:
            raise ConfigValidationError("Validation failed", errors)
    
    def _create_backup(self) -> Path:
        """Create timestamped backup of current .env file.
        
        Returns:
            Path to backup file
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'env_backup_{timestamp}.txt'
        backup_path = self.backup_dir / backup_filename
        
        # Copy current .env to backup
        if self.env_path.exists():
            backup_path.write_text(self.env_path.read_text())
        
        # Set secure permissions (owner read/write only)
        self._set_secure_permissions(backup_path)
        
        # Log backup creation
        self.audit_logger.log(
            action='config_backup_created',
            post_id=None,
            run_id=None,
            details={
                'backup_path': str(backup_path),
                'timestamp': timestamp
            }
        )
        
        return backup_path
    
    def _restore_backup(self, backup_path: Path):
        """Restore .env from backup file.
        
        Args:
            backup_path: Path to backup file
        """
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_path}")
        
        # Read backup content
        backup_content = backup_path.read_text()
        
        # Write to .env atomically (write to temp, then rename)
        temp_path = self.env_path.parent / f'.env.tmp.{os.getpid()}'
        temp_path.write_text(backup_content)
        self._set_secure_permissions(temp_path)
        
        # Atomic rename
        temp_path.replace(self.env_path)
    
    def _apply_updates(self, updates: Dict):
        """Apply validated updates to .env file.
        
        Args:
            updates: Dictionary of updates organized by category
        """
        for category, fields in updates.items():
            for key, value in fields.items():
                # Convert booleans to string
                if isinstance(value, bool):
                    str_value = 'true' if value else 'false'
                else:
                    str_value = str(value)
                
                # Use python-dotenv's set_key for atomic writes
                set_key(str(self.env_path), key, str_value)
        
        # Ensure secure permissions after updates
        self._set_secure_permissions(self.env_path)
    
    def _rotate_backups(self, keep_count: int = 7):
        """Delete old backups, keeping only the most recent N.
        
        Args:
            keep_count: Number of backups to keep
        """
        backups = sorted(self.backup_dir.glob('env_backup_*.txt'), reverse=True)
        
        # Delete backups beyond keep_count
        for old_backup in backups[keep_count:]:
            old_backup.unlink()
    
    def _mask_value(self, value: str) -> str:
        """Mask sensitive values to show only first 3 and last 4 chars.
        
        Args:
            value: Value to mask
        
        Returns:
            Masked value
        """
        if not value or len(value) < 8:
            return '***'
        
        return f"{value[:3]}...{value[-4:]}"
    
    def _mask_updates(self, updates: Dict) -> Dict:
        """Mask sensitive values in updates dict.
        
        Args:
            updates: Dictionary of updates
        
        Returns:
            Dictionary with masked sensitive values
        """
        masked = {}
        
        for category, fields in updates.items():
            masked[category] = {}
            
            if category == 'api_keys':
                schema_category = self.CONFIG_SCHEMA[category]
                for key, value in fields.items():
                    if key in schema_category and schema_category[key].get('masked'):
                        masked[category][key] = self._mask_value(str(value))
                    else:
                        masked[category][key] = value
            else:
                masked[category] = fields.copy()
        
        return masked
    
    def _set_secure_permissions(self, file_path: Path):
        """Set file permissions to 0o600 (owner read/write only).
        
        Args:
            file_path: Path to file
        """
        os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR)
    
    def _test_openai_key(self, api_key: str) -> Tuple[bool, str]:
        """Test OpenAI API key.
        
        Args:
            api_key: OpenAI API key
        
        Returns:
            Tuple of (is_valid, message)
        """
        try:
            response = requests.get(
                'https://api.openai.com/v1/models',
                headers={'Authorization': f'Bearer {api_key}'},
                timeout=10
            )
            
            if response.status_code == 200:
                return True, "✓ OpenAI API key is valid"
            elif response.status_code == 401:
                return False, "✗ Invalid OpenAI API key"
            else:
                return False, f"✗ OpenAI API returned status {response.status_code}"
                
        except requests.exceptions.Timeout:
            return False, "✗ OpenAI API request timed out"
        except Exception as e:
            return False, f"✗ Error testing OpenAI key: {str(e)}"
    
    def _test_reddit_key(self, client_secret: str) -> Tuple[bool, str]:
        """Test Reddit API credentials.
        
        Note: Requires client_id from current config
        
        Args:
            client_secret: Reddit client secret
        
        Returns:
            Tuple of (is_valid, message)
        """
        try:
            # Load current config to get client_id and user_agent
            env_values = dotenv_values(str(self.env_path))
            client_id = env_values.get('REDDIT_CLIENT_ID')
            user_agent = env_values.get('REDDIT_USER_AGENT', 'Pi-Autopilot/2.0')
            
            if not client_id:
                return False, "✗ REDDIT_CLIENT_ID not configured"
            
            # Test authentication
            reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent
            )
            
            # Try to access user info (will fail if auth is invalid)
            _ = reddit.user.me()
            
            return True, "✓ Reddit API credentials are valid"
            
        except praw.exceptions.ResponseException as e:
            return False, f"✗ Invalid Reddit credentials: {str(e)}"
        except Exception as e:
            return False, f"✗ Error testing Reddit credentials: {str(e)}"
    
    def _test_gumroad_key(self, access_token: str) -> Tuple[bool, str]:
        """Test Gumroad API key.
        
        Args:
            access_token: Gumroad access token
        
        Returns:
            Tuple of (is_valid, message)
        """
        try:
            response = requests.get(
                'https://api.gumroad.com/v2/user',
                params={'access_token': access_token},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    return True, "✓ Gumroad access token is valid"
                else:
                    return False, "✗ Gumroad API returned error"
            elif response.status_code == 401:
                return False, "✗ Invalid Gumroad access token"
            else:
                return False, f"✗ Gumroad API returned status {response.status_code}"
                
        except requests.exceptions.Timeout:
            return False, "✗ Gumroad API request timed out"
        except Exception as e:
            return False, f"✗ Error testing Gumroad token: {str(e)}"
