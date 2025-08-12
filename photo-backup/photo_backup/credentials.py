"""
Credential management for photo backup system.

This module handles credential retrieval, validation, and management
for S3-compatible storage services, with support for 1Password integration
and test mode using Minio.
"""

import json
import logging
import os
import subprocess
import time
from typing import Any, Dict, Optional

from .config.config import Config


class CredentialManager:
    """Manages credentials for S3-compatible storage services."""

    def __init__(self, config: Config):
        """Initialize credential manager.

        Args:
            config: Configuration object containing storage settings
        """
        self.config = config
        self.logger = logging.getLogger("photo_backup.credentials")
        self._credentials: Optional[Dict[str, Any]] = None
        self._session_token: Optional[str] = None
        self._session_expiry: Optional[float] = None

    def get_credentials(self) -> Dict[str, Any]:
        """Get credentials for storage access.

        Returns:
            Dictionary containing credentials with keys:
            - access_key: Storage access key
            - secret_key: Storage secret key
            - endpoint: Storage endpoint URL
            - region: Storage region
            - use_ssl: Whether to use SSL/TLS
            - bucket: Storage bucket name
        """
        if self._credentials is None:
            self._credentials = self._load_credentials()

        return self._credentials.copy()

    def _load_credentials(self) -> Dict[str, Any]:
        """Load credentials based on configuration and mode.

        Returns:
            Dictionary containing storage credentials
        """
        if self.config.is_test_mode():
            return self._get_test_credentials()
        else:
            return self._get_production_credentials()

    def _get_test_credentials(self) -> Dict[str, Any]:
        """Get test mode credentials (Minio).

        Returns:
            Dictionary containing Minio test credentials
        """
        self.logger.debug("Loading test mode credentials (Minio)")
        
        config_data = self.config.load_config()
        storage_config = config_data.get("storage", {})
        
        credentials = {
            "access_key": storage_config.get("access_key", "minioadmin"),
            "secret_key": storage_config.get("secret_key", "minioadmin"),
            "endpoint": storage_config.get("endpoint", "localhost:9000"),
            "region": storage_config.get("region", "us-east-1"),
            "use_ssl": storage_config.get("use_ssl", False),
            "bucket": storage_config.get("bucket", "test-bucket"),
            "timeout_seconds": storage_config.get("timeout_seconds", 30),
            "retry_attempts": storage_config.get("retry_attempts", 1),
        }
        
        self.logger.debug(f"Test credentials loaded: endpoint={credentials['endpoint']}, bucket={credentials['bucket']}")
        return credentials

    def _get_production_credentials(self) -> Dict[str, Any]:
        """Get production credentials (Wasabi via 1Password).

        Returns:
            Dictionary containing production credentials
        """
        self.logger.debug("Loading production credentials")
        
        config_data = self.config.load_config()
        storage_config = config_data.get("storage", {})
        
        # Get credentials from 1Password
        access_key, secret_key = self._retrieve_credentials_from_1password()
        
        credentials = {
            "access_key": access_key,
            "secret_key": secret_key,
            "endpoint": storage_config.get("endpoint", "s3.wasabisys.com"),
            "region": storage_config.get("region", "us-east-1"),
            "use_ssl": storage_config.get("use_ssl", True),
            "bucket": storage_config.get("bucket", "my-photo-backup-bucket"),
            "timeout_seconds": storage_config.get("timeout_seconds", 300),
            "retry_attempts": storage_config.get("retry_attempts", 3),
        }
        
        self.logger.debug(f"Production credentials loaded: endpoint={credentials['endpoint']}, bucket={credentials['bucket']}")
        return credentials

    def _retrieve_credentials_from_1password(self) -> tuple[Optional[str], Optional[str]]:
        """Retrieve credentials from 1Password.

        Returns:
            Tuple of (access_key, secret_key) or (None, None) if retrieval fails
        """
        # Check if 1Password CLI is available
        is_available, message = check_op_cli()
        if not is_available:
            self.logger.error(f"1Password CLI not available: {message}")
            return None, None
        
        # Get session token (handles authentication if needed)
        session_token = self._get_session_token()
        
        try:
            # Get the item reference from config or use default
            config_data = self.config.load_config()
            storage_config = config_data.get("storage", {})
            item_ref = storage_config.get("1password_item", "Wasabi S3 Credentials")
            
            self.logger.debug(f"Retrieving credentials from 1Password item: {item_ref}")
            
            # Build command with session token if available
            cmd = ["op", "item", "get", item_ref, "--format=json"]
            env = os.environ.copy()
            
            if session_token:
                env["OP_SESSION_1password"] = session_token
            
            # Retrieve the item from 1Password
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30.0,
                env=env
            )
            
            if result.returncode != 0:
                error_msg = result.stderr.strip()
                self.logger.error(f"1Password command failed: {error_msg}")
                
                # Check if it's a session-related error and clear the session
                if "session" in error_msg.lower() or "authentication" in error_msg.lower():
                    self.logger.debug("Clearing invalid session token")
                    self._clear_session()
                
                return None, None
            
            # Parse the JSON response
            item_data = json.loads(result.stdout)
            
            # Extract credentials from the item
            access_key = self._extract_field_from_1password_item(item_data, "access_key")
            secret_key = self._extract_field_from_1password_item(item_data, "secret_key")
            
            if access_key and secret_key:
                self.logger.debug("Successfully retrieved credentials from 1Password")
                return access_key, secret_key
            else:
                self.logger.error("Failed to extract credentials from 1Password item")
                return None, None
                
        except subprocess.TimeoutExpired:
            self.logger.error("1Password command timed out")
            return None, None
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse 1Password JSON response: {e}")
            return None, None
        except Exception as e:
            self.logger.error(f"Error retrieving credentials from 1Password: {e}")
            return None, None

    def _extract_field_from_1password_item(self, item_data: Dict[str, Any], field_name: str) -> Optional[str]:
        """Extract a field value from a 1Password item.

        Args:
            item_data: The 1Password item data
            field_name: The name of the field to extract

        Returns:
            The field value or None if not found
        """
        try:
            # 1Password items have a 'fields' array with 'id' and 'value' properties
            fields = item_data.get("fields", [])
            
            for field in fields:
                if field.get("id") == field_name:
                    return field.get("value")
            
            # If not found by ID, try to find by label (case-insensitive)
            for field in fields:
                label = field.get("label", "").lower()
                # Try exact match first
                if label == field_name.lower():
                    return field.get("value")
                # Try partial match (e.g., "Access Key" matches "access_key")
                if field_name.lower() in label.replace(" ", "_") or field_name.lower() in label.replace(" ", ""):
                    return field.get("value")
            
            self.logger.warning(f"Field '{field_name}' not found in 1Password item")
            return None
            
        except Exception as e:
            self.logger.error(f"Error extracting field '{field_name}' from 1Password item: {e}")
            return None

    def validate_credentials(self) -> tuple[bool, str]:
        """Validate that credentials are available and complete.

        Returns:
            Tuple of (is_valid, error_message)
        """
        credentials = self.get_credentials()
        
        # Check required fields (except access_key and secret_key which may be None in production)
        required_fields = ["endpoint", "bucket"]
        for field in required_fields:
            if not credentials.get(field):
                return False, f"Missing required credential field: {field}"
        
        # Test mode specific validation
        if self.config.is_test_mode():
            return self._validate_test_credentials(credentials)
        else:
            return self._validate_production_credentials(credentials)

    def _validate_test_credentials(self, credentials: Dict[str, Any]) -> tuple[bool, str]:
        """Validate test mode credentials.

        Args:
            credentials: Credentials dictionary

        Returns:
            Tuple of (is_valid, error_message)
        """
        # For test mode, just check that credentials are present
        # Actual Minio connectivity will be tested in Task 48
        if credentials["access_key"] == "minioadmin" and credentials["secret_key"] == "minioadmin":
            return True, "Test credentials are valid"
        else:
            return False, "Invalid test credentials - expected minioadmin/minioadmin"

    def _validate_production_credentials(self, credentials: Dict[str, Any]) -> tuple[bool, str]:
        """Validate production credentials.

        Args:
            credentials: Credentials dictionary

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check that credentials were successfully retrieved from 1Password
        if credentials["access_key"] is None or credentials["secret_key"] is None:
            return False, "Production credentials not available - 1Password integration failed"
        
        return True, "Production credentials are valid"

    def get_credential_info(self) -> Dict[str, Any]:
        """Get information about current credentials.

        Returns:
            Dictionary containing credential information
        """
        credentials = self.get_credentials()
        
        info = {
            "mode": "test" if self.config.is_test_mode() else "production",
            "endpoint": credentials["endpoint"],
            "bucket": credentials["bucket"],
            "region": credentials["region"],
            "use_ssl": credentials["use_ssl"],
            "has_access_key": credentials["access_key"] is not None,
            "has_secret_key": credentials["secret_key"] is not None,
            "timeout_seconds": credentials["timeout_seconds"],
            "retry_attempts": credentials["retry_attempts"],
        }
        
        # Mask sensitive information
        if credentials["access_key"]:
            info["access_key_preview"] = f"{credentials['access_key'][:4]}...{credentials['access_key'][-4:]}"
        else:
            info["access_key_preview"] = "None"
            
        return info

    def _get_session_token(self) -> Optional[str]:
        """Get a valid 1Password session token.

        Returns:
            Session token or None if not available/expired
        """
        # Skip session management in test mode
        if self.config.is_test_mode():
            return None
        
        # Check if we have a valid cached session
        if self._is_session_valid():
            self.logger.debug("Using cached 1Password session token")
            return self._session_token
        
        # Get a new session token
        return self._authenticate_session()

    def _is_session_valid(self) -> bool:
        """Check if the current session token is valid.

        Returns:
            True if session is valid, False otherwise
        """
        if not self._session_token or not self._session_expiry:
            return False
        
        # Check if session has expired (with 5-minute buffer)
        if time.time() > (self._session_expiry - 300):
            self.logger.debug("1Password session token expired")
            return False
        
        return True

    def _authenticate_session(self) -> Optional[str]:
        """Authenticate with 1Password and get a session token.

        Returns:
            Session token or None if authentication failed
        """
        try:
            self.logger.debug("Authenticating with 1Password")
            
            # Sign in to 1Password (this will prompt for authentication)
            result = subprocess.run(
                ["op", "signin"],
                capture_output=True,
                text=True,
                timeout=60.0
            )
            
            if result.returncode != 0:
                self.logger.error(f"1Password signin failed: {result.stderr.strip()}")
                return None
            
            # Extract session token from output
            # 1Password CLI typically outputs the session token on success
            lines = result.stdout.strip().split('\n')
            session_token = None
            
            for line in lines:
                if line.startswith('export OP_SESSION_'):
                    # Extract token from export command
                    parts = line.split('=')
                    if len(parts) == 2:
                        session_token = parts[1].strip().strip('"')
                        break
            
            if not session_token:
                self.logger.error("Could not extract session token from 1Password signin output")
                return None
            
            # Cache the session token with expiry (1Password sessions typically last 30 minutes)
            self._session_token = session_token
            self._session_expiry = time.time() + 1800  # 30 minutes
            
            self.logger.debug("Successfully authenticated with 1Password")
            return session_token
            
        except subprocess.TimeoutExpired:
            self.logger.error("1Password signin timed out")
            return None
        except Exception as e:
            self.logger.error(f"Error during 1Password authentication: {e}")
            return None

    def _clear_session(self) -> None:
        """Clear the cached session token."""
        self._session_token = None
        self._session_expiry = None
        self.logger.debug("Cleared 1Password session token")


def check_op_cli() -> tuple[bool, str]:
    """Check if 1Password CLI is available and compatible.
    
    Returns:
        Tuple of (is_available, message)
    """
    try:
        # Check if op command exists
        result = subprocess.run(
            ["op", "--version"], 
            capture_output=True, 
            text=True, 
            timeout=10.0
        )
        
        if result.returncode == 0:
            version = result.stdout.strip()
            # Basic version check - 1Password CLI v2+ is required
            # Version format can be "2.x.x" or "v2.x.x"
            if version.startswith("2.") or version.startswith("v2.") or version.startswith("1.") or version.startswith("v1."):
                return True, f"1Password CLI available: {version}"
            else:
                return False, f"1Password CLI version not supported: {version}"
        else:
            return False, f"1Password CLI command failed: {result.stderr.strip()}"
            
    except subprocess.TimeoutExpired:
        return False, "1Password CLI command timed out"
    except FileNotFoundError:
        return False, "1Password CLI not found in PATH"
    except Exception as e:
        return False, f"Error checking 1Password CLI: {str(e)}"


def check_op_cli_in_test_mode() -> tuple[bool, str]:
    """Check 1Password CLI availability, skipping in test mode.
    
    Returns:
        Tuple of (is_available, message)
    """
    # In test mode, we don't need 1Password CLI
    if os.environ.get("PHOTO_BACKUP_TEST_MODE") == "1":
        return True, "1Password CLI check skipped in test mode"
    
    return check_op_cli()
