#!/usr/bin/env python3
"""
Unit tests for authentication CLI commands.
"""

import subprocess
from unittest.mock import Mock, patch

import click
import pytest
from click.testing import CliRunner

from photo_backup.cli.auth_commands import _ensure_test_bucket
from photo_backup.main import main
from photo_backup.config.config import Config
from photo_backup.credentials import CredentialError, CredentialManager


class TestAuthCommands:
    """Test authentication CLI commands."""

    def test_test_auth_success_test_mode(self):
        """Test test-auth command success in test mode."""
        runner = CliRunner()
        
        # Mock credential manager
        mock_manager = Mock()
        mock_manager.get_credential_status.return_value = {
            "mode": "test",
            "has_credentials": True,
            "credential_info": {
                "endpoint": "localhost:9000",
                "bucket": "test-bucket",
                "region": "us-east-1",
                "use_ssl": False,
            },
            "validation": {"is_valid": True, "message": "Credentials valid"},
        }
        mock_manager.validate_credentials.return_value = (True, "S3 access successful")
        
        with patch("photo_backup.cli.auth_commands.CredentialManager", return_value=mock_manager), \
             patch("photo_backup.cli.auth_commands._ensure_test_bucket") as mock_ensure_bucket:
            
            result = runner.invoke(main, ["--test-mode", "test-auth"])
            
            # Should return success
            assert result.exit_code == 0
            
            # Should call credential manager methods
            mock_manager.get_credential_status.assert_called_once()
            mock_manager.validate_credentials.assert_called_once()
            
            # Should ensure test bucket in test mode
            mock_ensure_bucket.assert_called_once_with(mock_manager, mock_manager.logger)
            
            # Should show success messages
            assert "🎉 Authentication test completed successfully!" in result.output

    def test_test_auth_success_production_mode(self):
        """Test test-auth command success in production mode."""
        runner = CliRunner()
        
        # Mock credential manager
        mock_manager = Mock()
        mock_manager.get_credential_status.return_value = {
            "mode": "production",
            "has_credentials": True,
            "credential_info": {
                "endpoint": "s3.wasabisys.com",
                "bucket": "my-photo-backup-bucket",
                "region": "us-east-1",
                "use_ssl": True,
            },
            "validation": {"is_valid": True, "message": "Credentials valid"},
        }
        mock_manager.validate_credentials.return_value = (True, "S3 access successful")
        
        with patch("photo_backup.cli.auth_commands.CredentialManager", return_value=mock_manager), \
             patch("photo_backup.cli.auth_commands._ensure_test_bucket") as mock_ensure_bucket:
            
            result = runner.invoke(main, ["test-auth"])
            
            # Should return success
            assert result.exit_code == 0
            
            # Should call credential manager methods
            mock_manager.get_credential_status.assert_called_once()
            mock_manager.validate_credentials.assert_called_once()
            
            # Should NOT ensure test bucket in production mode
            mock_ensure_bucket.assert_not_called()
            
            # Should show success messages
            assert "🎉 Authentication test completed successfully!" in result.output

    def test_test_auth_failure_no_credentials(self):
        """Test test-auth command failure when no credentials available."""
        runner = CliRunner()
        
        # Mock credential manager
        mock_manager = Mock()
        mock_manager.get_credential_status.return_value = {
            "mode": "production",
            "has_credentials": False,
            "error": "No credentials found",
            "suggestion": "Set environment variables",
            "details": "Missing access key",
        }
        
        with patch("photo_backup.cli.auth_commands.CredentialManager", return_value=mock_manager):
            
            result = runner.invoke(main, ["test-auth"])
            
            # Should return failure
            assert result.exit_code == 1
            
            # Should show error messages
            assert "❌ Error: No credentials found" in result.output
            assert "💡 Suggestion: Set environment variables" in result.output
            assert "💥 Authentication test failed!" in result.output

    def test_test_auth_failure_invalid_credentials(self):
        """Test test-auth command failure when credentials are invalid."""
        runner = CliRunner()
        
        # Mock credential manager
        mock_manager = Mock()
        mock_manager.get_credential_status.return_value = {
            "mode": "production",
            "has_credentials": True,
            "credential_info": {
                "endpoint": "s3.wasabisys.com",
                "bucket": "my-photo-backup-bucket",
                "region": "us-east-1",
                "use_ssl": True,
            },
            "validation": {"is_valid": False, "message": "Access denied"},
        }
        mock_manager.validate_credentials.return_value = (False, "Invalid credentials")
        
        with patch("photo_backup.cli.auth_commands.CredentialManager", return_value=mock_manager):
            
            result = runner.invoke(main, ["test-auth"])
            
            # Should return failure
            assert result.exit_code == 1
            
            # Should show failure messages
            assert "❌ Credential validation: FAILED" in result.output
            assert "   Error: Access denied" in result.output
            assert "❌ S3 access test: FAILED" in result.output
            assert "   Invalid credentials" in result.output
            assert "💥 Authentication test failed!" in result.output

    def test_test_auth_verbose_mode(self):
        """Test test-auth command with verbose flag."""
        runner = CliRunner()
        
        # Mock credential manager
        mock_manager = Mock()
        mock_manager.get_credential_status.return_value = {
            "mode": "production",
            "has_credentials": True,
            "credential_info": {
                "endpoint": "s3.wasabisys.com",
                "bucket": "my-photo-backup-bucket",
                "region": "us-east-1",
                "use_ssl": True,
            },
            "validation": {"is_valid": True, "message": "Credentials valid"},
            "error": None,
            "suggestion": None,
            "details": None,
        }
        mock_manager.validate_credentials.return_value = (True, "S3 access successful")
        
        with patch("photo_backup.cli.auth_commands.CredentialManager", return_value=mock_manager):
            
            result = runner.invoke(main, ["test-auth", "--verbose"])
            
            # Should return success
            assert result.exit_code == 0
            
            # Should show verbose information
            assert "📊 Detailed Status:" in result.output

    def test_test_auth_exception_handling(self):
        """Test test-auth command exception handling."""
        runner = CliRunner()
        
        # Mock credential manager to raise exception
        with patch("photo_backup.cli.auth_commands.CredentialManager", side_effect=Exception("Test error")):
            
            result = runner.invoke(main, ["test-auth"])
            
            # Should return failure
            assert result.exit_code == 1
            
            # Should show error message
            assert "💥 Unexpected error: Test error" in result.output


class TestEnsureTestBucket:
    """Test _ensure_test_bucket function."""

    def test_ensure_test_bucket_already_exists(self):
        """Test bucket creation when bucket already exists."""
        mock_manager = Mock()
        mock_manager.get_credentials.return_value = {
            "access_key": "minioadmin",
            "secret_key": "minioadmin",
            "endpoint": "localhost:9000",
            "bucket": "test-bucket",
            "region": "us-east-1",
            "use_ssl": False,
        }
        
        mock_logger = Mock()
        
        # Mock subprocess to simulate bucket already exists
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        
        with patch("subprocess.run", return_value=mock_result) as mock_run, \
             patch("click.echo") as mock_echo:
            
            _ensure_test_bucket(mock_manager, mock_logger)
            
            # Should call rclone ls to check if bucket exists
            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            assert "rclone" in cmd[0]
            assert "ls" in cmd[1]
            assert "minio:test-bucket" in cmd[2]
            
            # Should show success message
            mock_echo.assert_any_call("✅ Test bucket 'test-bucket' already exists")

    def test_ensure_test_bucket_create_new(self):
        """Test bucket creation when bucket doesn't exist."""
        mock_manager = Mock()
        mock_manager.get_credentials.return_value = {
            "access_key": "minioadmin",
            "secret_key": "minioadmin",
            "endpoint": "localhost:9000",
            "bucket": "test-bucket",
            "region": "us-east-1",
            "use_ssl": False,
        }
        
        mock_logger = Mock()
        
        # Mock subprocess to simulate bucket doesn't exist, then creation succeeds
        mock_ls_result = Mock()
        mock_ls_result.returncode = 1  # Bucket doesn't exist
        mock_ls_result.stderr = "not found"
        
        mock_mkdir_result = Mock()
        mock_mkdir_result.returncode = 0  # Creation succeeds
        mock_mkdir_result.stderr = ""
        
        with patch("subprocess.run", side_effect=[mock_ls_result, mock_mkdir_result]) as mock_run, \
             patch("click.echo") as mock_echo:
            
            _ensure_test_bucket(mock_manager, mock_logger)
            
            # Should call rclone twice (ls then mkdir)
            assert mock_run.call_count == 2
            
            # First call should be ls
            ls_cmd = mock_run.call_args_list[0][0][0]
            assert "ls" in ls_cmd[1]
            
            # Second call should be mkdir
            mkdir_cmd = mock_run.call_args_list[1][0][0]
            assert "mkdir" in mkdir_cmd[1]
            
            # Should show creation message
            mock_echo.assert_any_call("🪣 Creating test bucket 'test-bucket'...")
            mock_echo.assert_any_call("✅ Test bucket 'test-bucket' created successfully")

    def test_ensure_test_bucket_creation_fails(self):
        """Test bucket creation when creation fails."""
        mock_manager = Mock()
        mock_manager.get_credentials.return_value = {
            "access_key": "minioadmin",
            "secret_key": "minioadmin",
            "endpoint": "localhost:9000",
            "bucket": "test-bucket",
            "region": "us-east-1",
            "use_ssl": False,
        }
        
        mock_logger = Mock()
        
        # Mock subprocess to simulate bucket doesn't exist and creation fails
        mock_ls_result = Mock()
        mock_ls_result.returncode = 1  # Bucket doesn't exist
        mock_ls_result.stderr = "not found"
        
        mock_mkdir_result = Mock()
        mock_mkdir_result.returncode = 1  # Creation fails
        mock_mkdir_result.stderr = "Permission denied"
        
        with patch("subprocess.run", side_effect=[mock_ls_result, mock_mkdir_result]) as mock_run, \
             patch("click.echo") as mock_echo:
            
            _ensure_test_bucket(mock_manager, mock_logger)
            
            # Should show warning message
            mock_echo.assert_any_call("⚠️  Warning: Could not create test bucket 'test-bucket'")
            mock_echo.assert_any_call("   Error: Permission denied")

    def test_ensure_test_bucket_exception_handling(self):
        """Test bucket creation exception handling."""
        mock_manager = Mock()
        mock_manager.get_credentials.side_effect = Exception("Test error")
        
        mock_logger = Mock()
        
        with patch("click.echo") as mock_echo:
            
            _ensure_test_bucket(mock_manager, mock_logger)
            
            # Should show warning message
            mock_echo.assert_any_call("⚠️  Warning: Could not ensure test bucket exists: Test error")
