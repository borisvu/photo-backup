"""
Unit tests for credential management functionality.
"""

import pytest
from unittest.mock import Mock, patch

from photo_backup.credentials import CredentialManager
from photo_backup.config.config import Config


class TestCredentialManager:
    """Test CredentialManager functionality."""

    def test_credential_manager_initialization(self):
        """Test CredentialManager initialization."""
        config = Config(test_mode=True)
        manager = CredentialManager(config)
        
        assert manager.config == config
        assert manager.logger.name == "photo_backup.credentials"
        assert manager._credentials is None

    def test_get_test_credentials(self):
        """Test getting test mode credentials."""
        config = Config(test_mode=True)
        manager = CredentialManager(config)
        
        credentials = manager.get_credentials()
        
        assert credentials["access_key"] == "minioadmin"
        assert credentials["secret_key"] == "minioadmin"
        assert credentials["endpoint"] == "localhost:9000"
        assert credentials["region"] == "us-east-1"
        assert credentials["use_ssl"] is False
        assert credentials["bucket"] == "test-bucket"
        assert credentials["timeout_seconds"] == 30
        assert credentials["retry_attempts"] == 1

    def test_get_production_credentials(self):
        """Test getting production credentials."""
        config = Config(test_mode=False)
        manager = CredentialManager(config)
        
        credentials = manager.get_credentials()
        
        assert credentials["access_key"] is None  # Will be retrieved from 1Password
        assert credentials["secret_key"] is None  # Will be retrieved from 1Password
        assert credentials["endpoint"] == "s3.wasabisys.com"
        assert credentials["region"] == "us-east-1"
        assert credentials["use_ssl"] is True
        assert credentials["bucket"] == "my-photo-backup-bucket"
        assert credentials["timeout_seconds"] == 300
        assert credentials["retry_attempts"] == 3

    def test_credentials_caching(self):
        """Test that credentials are cached after first load."""
        config = Config(test_mode=True)
        manager = CredentialManager(config)
        
        # First call should load credentials
        credentials1 = manager.get_credentials()
        assert manager._credentials is not None
        
        # Second call should return cached credentials
        credentials2 = manager.get_credentials()
        assert credentials1 == credentials2

    def test_credentials_return_copy(self):
        """Test that get_credentials returns a copy, not the original."""
        config = Config(test_mode=True)
        manager = CredentialManager(config)
        
        credentials1 = manager.get_credentials()
        credentials2 = manager.get_credentials()
        
        # Modify the returned credentials
        credentials1["access_key"] = "modified"
        
        # The second call should not be affected
        assert credentials2["access_key"] == "minioadmin"

    def test_validate_test_credentials_success(self):
        """Test validation of valid test credentials."""
        config = Config(test_mode=True)
        manager = CredentialManager(config)
        
        is_valid, message = manager.validate_credentials()
        
        assert is_valid is True
        assert "Test credentials are valid" in message

    def test_validate_test_credentials_failure(self):
        """Test validation of invalid test credentials."""
        config = Config(test_mode=True)
        manager = CredentialManager(config)
        
        # Mock the credentials to be invalid
        with patch.object(manager, '_get_test_credentials') as mock_get:
            mock_get.return_value = {
                "access_key": "wrong",
                "secret_key": "wrong",
                "endpoint": "localhost:9000",
                "bucket": "test-bucket",
                "region": "us-east-1",
                "use_ssl": False,
                "timeout_seconds": 30,
                "retry_attempts": 1,
            }
            
            is_valid, message = manager.validate_credentials()
            
            assert is_valid is False
            assert "Invalid test credentials" in message

    def test_validate_production_credentials_not_implemented(self):
        """Test validation of production credentials (not yet implemented)."""
        config = Config(test_mode=False)
        manager = CredentialManager(config)
        
        # Mock the production credentials to have None values
        with patch.object(manager, '_get_production_credentials') as mock_get:
            mock_get.return_value = {
                "access_key": None,
                "secret_key": None,
                "endpoint": "s3.wasabisys.com",
                "bucket": "my-photo-backup-bucket",
                "region": "us-east-1",
                "use_ssl": True,
                "timeout_seconds": 300,
                "retry_attempts": 3,
            }
            
            is_valid, message = manager.validate_credentials()
            
            assert is_valid is False
            assert "1Password integration not yet implemented" in message

    def test_validate_credentials_missing_fields(self):
        """Test validation with missing credential fields."""
        config = Config(test_mode=True)
        manager = CredentialManager(config)
        
        # Mock credentials with missing fields
        with patch.object(manager, '_get_test_credentials') as mock_get:
            mock_get.return_value = {
                "access_key": "minioadmin",
                "secret_key": "minioadmin",
                # Missing endpoint and bucket
                "region": "us-east-1",
                "use_ssl": False,
                "timeout_seconds": 30,
                "retry_attempts": 1,
            }
            
            is_valid, message = manager.validate_credentials()
            
            assert is_valid is False
            assert "Missing required credential field" in message

    def test_get_credential_info_test_mode(self):
        """Test getting credential information in test mode."""
        config = Config(test_mode=True)
        manager = CredentialManager(config)
        
        info = manager.get_credential_info()
        
        assert info["mode"] == "test"
        assert info["endpoint"] == "localhost:9000"
        assert info["bucket"] == "test-bucket"
        assert info["region"] == "us-east-1"
        assert info["use_ssl"] is False
        assert info["has_access_key"] is True
        assert info["has_secret_key"] is True
        assert info["timeout_seconds"] == 30
        assert info["retry_attempts"] == 1
        assert info["access_key_preview"] == "mini...dmin"

    def test_get_credential_info_production_mode(self):
        """Test getting credential information in production mode."""
        config = Config(test_mode=False)
        manager = CredentialManager(config)
        
        info = manager.get_credential_info()
        
        assert info["mode"] == "production"
        assert info["endpoint"] == "s3.wasabisys.com"
        assert info["bucket"] == "my-photo-backup-bucket"
        assert info["region"] == "us-east-1"
        assert info["use_ssl"] is True
        assert info["has_access_key"] is False
        assert info["has_secret_key"] is False
        assert info["timeout_seconds"] == 300
        assert info["retry_attempts"] == 3
        assert info["access_key_preview"] == "None"

    def test_get_credential_info_masks_sensitive_data(self):
        """Test that credential info masks sensitive data."""
        config = Config(test_mode=True)
        manager = CredentialManager(config)
        
        info = manager.get_credential_info()
        
        # Should not contain full access key
        assert "minioadmin" not in str(info)
        # Should contain masked version
        assert "mini...dmin" in info["access_key_preview"]

    def test_credential_manager_with_custom_config(self):
        """Test CredentialManager with custom configuration values."""
        config = Config(test_mode=True)
        
        # Mock config to return custom storage settings
        with patch.object(config, 'load_config') as mock_load:
            mock_load.return_value = {
                "storage": {
                    "access_key": "custom-key",
                    "secret_key": "custom-secret",
                    "endpoint": "custom-endpoint:9000",
                    "region": "custom-region",
                    "use_ssl": True,
                    "bucket": "custom-bucket",
                    "timeout_seconds": 60,
                    "retry_attempts": 5,
                }
            }
            
            manager = CredentialManager(config)
            credentials = manager.get_credentials()
            
            assert credentials["access_key"] == "custom-key"
            assert credentials["secret_key"] == "custom-secret"
            assert credentials["endpoint"] == "custom-endpoint:9000"
            assert credentials["region"] == "custom-region"
            assert credentials["use_ssl"] is True
            assert credentials["bucket"] == "custom-bucket"
            assert credentials["timeout_seconds"] == 60
            assert credentials["retry_attempts"] == 5
