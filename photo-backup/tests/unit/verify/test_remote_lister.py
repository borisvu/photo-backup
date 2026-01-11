"""
Unit tests for the RemoteLister class.

Tests remote file listing using rclone lsjson.
"""

import json
from unittest.mock import MagicMock, patch

import pytest


class TestRemoteListerInstantiation:
    """Test RemoteLister instantiation."""

    def test_remote_lister_can_be_instantiated(self):
        """Test that RemoteLister can be instantiated."""
        from photo_backup.config.config import Config
        from photo_backup.credentials.manager import CredentialManager
        from photo_backup.verify import RemoteLister

        config = Config(test_mode=True)
        credential_manager = CredentialManager(config)

        lister = RemoteLister(config, credential_manager)

        assert lister is not None
        assert lister.config is config
        assert lister.credential_manager is credential_manager


class TestRemoteListerConfigGeneration:
    """Test RemoteLister rclone config generation."""

    def test_build_rclone_config_generates_valid_config(self):
        """Test that _build_rclone_config generates valid rclone config."""
        from photo_backup.config.config import Config
        from photo_backup.credentials.manager import CredentialManager
        from photo_backup.verify import RemoteLister

        config = Config(test_mode=True)
        credential_manager = CredentialManager(config)

        with patch.object(credential_manager, "get_credentials") as mock_creds:
            mock_creds.return_value = {
                "access_key": "test_access_key",
                "secret_key": "test_secret_key",
                "endpoint": "localhost:9000",
                "region": "us-east-1",
                "use_ssl": False,
            }

            lister = RemoteLister(config, credential_manager)
            config_content = lister._build_rclone_config()

            assert "[test]" in config_content
            assert "type = s3" in config_content
            assert "access_key_id = test_access_key" in config_content
            assert "secret_access_key = test_secret_key" in config_content
            assert "endpoint = http://localhost:9000" in config_content

    def test_build_rclone_config_adds_http_scheme_when_missing(self):
        """Test that config adds http:// when scheme is missing and use_ssl=False."""
        from photo_backup.config.config import Config
        from photo_backup.credentials.manager import CredentialManager
        from photo_backup.verify import RemoteLister

        config = Config(test_mode=True)
        credential_manager = CredentialManager(config)

        with patch.object(credential_manager, "get_credentials") as mock_creds:
            mock_creds.return_value = {
                "access_key": "key",
                "secret_key": "secret",
                "endpoint": "localhost:9000",  # No scheme
                "region": "us-east-1",
                "use_ssl": False,
            }

            lister = RemoteLister(config, credential_manager)
            config_content = lister._build_rclone_config()

            assert "endpoint = http://localhost:9000" in config_content

    def test_build_rclone_config_adds_https_scheme_when_ssl(self):
        """Test that config adds https:// when use_ssl=True."""
        from photo_backup.config.config import Config
        from photo_backup.credentials.manager import CredentialManager
        from photo_backup.verify import RemoteLister

        config = Config(test_mode=True)
        credential_manager = CredentialManager(config)

        with patch.object(credential_manager, "get_credentials") as mock_creds:
            mock_creds.return_value = {
                "access_key": "key",
                "secret_key": "secret",
                "endpoint": "s3.wasabisys.com",  # No scheme
                "region": "us-east-1",
                "use_ssl": True,
            }

            lister = RemoteLister(config, credential_manager)
            config_content = lister._build_rclone_config()

            assert "endpoint = https://s3.wasabisys.com" in config_content

    def test_build_rclone_config_preserves_existing_scheme(self):
        """Test that config preserves existing http/https scheme."""
        from photo_backup.config.config import Config
        from photo_backup.credentials.manager import CredentialManager
        from photo_backup.verify import RemoteLister

        config = Config(test_mode=True)
        credential_manager = CredentialManager(config)

        with patch.object(credential_manager, "get_credentials") as mock_creds:
            mock_creds.return_value = {
                "access_key": "key",
                "secret_key": "secret",
                "endpoint": "http://already-has-scheme:9000",
                "region": "us-east-1",
                "use_ssl": True,  # This should be ignored
            }

            lister = RemoteLister(config, credential_manager)
            config_content = lister._build_rclone_config()

            # Should preserve http:// even though use_ssl=True
            assert "endpoint = http://already-has-scheme:9000" in config_content


class TestRemoteListerJsonParsing:
    """Test RemoteLister JSON parsing."""

    def test_parse_lsjson_output_empty_string(self):
        """Test parsing empty output."""
        from photo_backup.config.config import Config
        from photo_backup.credentials.manager import CredentialManager
        from photo_backup.verify import RemoteLister

        config = Config(test_mode=True)
        credential_manager = CredentialManager(config)
        lister = RemoteLister(config, credential_manager)

        result = lister._parse_lsjson_output("")

        assert result == []

    def test_parse_lsjson_output_empty_array(self):
        """Test parsing empty JSON array."""
        from photo_backup.config.config import Config
        from photo_backup.credentials.manager import CredentialManager
        from photo_backup.verify import RemoteLister

        config = Config(test_mode=True)
        credential_manager = CredentialManager(config)
        lister = RemoteLister(config, credential_manager)

        result = lister._parse_lsjson_output("[]")

        assert result == []

    def test_parse_lsjson_output_single_file(self):
        """Test parsing single file in JSON output."""
        from photo_backup.config.config import Config
        from photo_backup.credentials.manager import CredentialManager
        from photo_backup.verify import RemoteLister

        config = Config(test_mode=True)
        credential_manager = CredentialManager(config)
        lister = RemoteLister(config, credential_manager)

        json_output = json.dumps(
            [
                {
                    "Path": "photos/2024/photo.jpg",
                    "Size": 1024,
                    "IsDir": False,
                    "ModTime": "2024-01-15T10:30:00Z",
                    "Hashes": {"MD5": "abc123def456"},
                }
            ]
        )

        result = lister._parse_lsjson_output(json_output)

        assert len(result) == 1
        assert result[0].path == "photos/2024/photo.jpg"
        assert result[0].size == 1024
        assert result[0].hash_md5 == "abc123def456"
        assert result[0].modified_time == "2024-01-15T10:30:00Z"

    def test_parse_lsjson_output_multiple_files(self):
        """Test parsing multiple files."""
        from photo_backup.config.config import Config
        from photo_backup.credentials.manager import CredentialManager
        from photo_backup.verify import RemoteLister

        config = Config(test_mode=True)
        credential_manager = CredentialManager(config)
        lister = RemoteLister(config, credential_manager)

        json_output = json.dumps(
            [
                {"Path": "file1.jpg", "Size": 100, "IsDir": False, "Hashes": {"MD5": "hash1"}},
                {"Path": "file2.jpg", "Size": 200, "IsDir": False, "Hashes": {"MD5": "hash2"}},
                {"Path": "file3.jpg", "Size": 300, "IsDir": False, "Hashes": {"MD5": "hash3"}},
            ]
        )

        result = lister._parse_lsjson_output(json_output)

        assert len(result) == 3
        assert result[0].path == "file1.jpg"
        assert result[1].path == "file2.jpg"
        assert result[2].path == "file3.jpg"

    def test_parse_lsjson_output_skips_directories(self):
        """Test that directories are skipped."""
        from photo_backup.config.config import Config
        from photo_backup.credentials.manager import CredentialManager
        from photo_backup.verify import RemoteLister

        config = Config(test_mode=True)
        credential_manager = CredentialManager(config)
        lister = RemoteLister(config, credential_manager)

        json_output = json.dumps(
            [
                {"Path": "photos", "IsDir": True, "Size": 0},
                {"Path": "photos/image.jpg", "IsDir": False, "Size": 1024, "Hashes": {"MD5": "abc"}},
            ]
        )

        result = lister._parse_lsjson_output(json_output)

        assert len(result) == 1
        assert result[0].path == "photos/image.jpg"

    def test_parse_lsjson_output_handles_lowercase_md5_key(self):
        """Test parsing with lowercase 'md5' hash key."""
        from photo_backup.config.config import Config
        from photo_backup.credentials.manager import CredentialManager
        from photo_backup.verify import RemoteLister

        config = Config(test_mode=True)
        credential_manager = CredentialManager(config)
        lister = RemoteLister(config, credential_manager)

        json_output = json.dumps(
            [
                {"Path": "file.jpg", "Size": 100, "IsDir": False, "Hashes": {"md5": "lowercase_hash"}},
            ]
        )

        result = lister._parse_lsjson_output(json_output)

        assert len(result) == 1
        assert result[0].hash_md5 == "lowercase_hash"

    def test_parse_lsjson_output_handles_missing_hash(self):
        """Test parsing file without hash."""
        from photo_backup.config.config import Config
        from photo_backup.credentials.manager import CredentialManager
        from photo_backup.verify import RemoteLister

        config = Config(test_mode=True)
        credential_manager = CredentialManager(config)
        lister = RemoteLister(config, credential_manager)

        json_output = json.dumps(
            [
                {"Path": "file.jpg", "Size": 100, "IsDir": False, "Hashes": {}},
            ]
        )

        result = lister._parse_lsjson_output(json_output)

        assert len(result) == 1
        assert result[0].hash_md5 is None

    def test_parse_lsjson_output_handles_no_hashes_key(self):
        """Test parsing file without Hashes key at all."""
        from photo_backup.config.config import Config
        from photo_backup.credentials.manager import CredentialManager
        from photo_backup.verify import RemoteLister

        config = Config(test_mode=True)
        credential_manager = CredentialManager(config)
        lister = RemoteLister(config, credential_manager)

        json_output = json.dumps(
            [
                {"Path": "file.jpg", "Size": 100, "IsDir": False},
            ]
        )

        result = lister._parse_lsjson_output(json_output)

        assert len(result) == 1
        assert result[0].hash_md5 is None

    def test_parse_lsjson_output_invalid_json(self):
        """Test parsing invalid JSON returns empty list."""
        from photo_backup.config.config import Config
        from photo_backup.credentials.manager import CredentialManager
        from photo_backup.verify import RemoteLister

        config = Config(test_mode=True)
        credential_manager = CredentialManager(config)
        lister = RemoteLister(config, credential_manager)

        result = lister._parse_lsjson_output("this is not valid json")

        assert result == []


class TestRemoteListerListFiles:
    """Test RemoteLister.list_remote_files method."""

    def test_list_remote_files_calls_rclone(self):
        """Test that list_remote_files calls rclone with correct arguments."""
        from photo_backup.config.config import Config
        from photo_backup.credentials.manager import CredentialManager
        from photo_backup.verify import RemoteLister

        config = Config(test_mode=True)
        credential_manager = CredentialManager(config)

        with patch.object(credential_manager, "get_credentials") as mock_creds:
            mock_creds.return_value = {
                "access_key": "key",
                "secret_key": "secret",
                "endpoint": "localhost:9000",
                "region": "us-east-1",
                "use_ssl": False,
            }

            lister = RemoteLister(config, credential_manager)

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="[]",
                    stderr="",
                )

                lister.list_remote_files("test-bucket")

                # Verify rclone was called
                mock_run.assert_called_once()
                call_args = mock_run.call_args[0][0]

                assert "rclone" in call_args
                assert "lsjson" in call_args
                assert "--hash" in call_args
                assert "--recursive" in call_args
                assert "test:test-bucket" in call_args

    def test_list_remote_files_returns_parsed_files(self):
        """Test that list_remote_files returns parsed FileHash objects."""
        from photo_backup.config.config import Config
        from photo_backup.credentials.manager import CredentialManager
        from photo_backup.verify import RemoteLister

        config = Config(test_mode=True)
        credential_manager = CredentialManager(config)

        with patch.object(credential_manager, "get_credentials") as mock_creds:
            mock_creds.return_value = {
                "access_key": "key",
                "secret_key": "secret",
                "endpoint": "localhost:9000",
                "region": "us-east-1",
                "use_ssl": False,
            }

            lister = RemoteLister(config, credential_manager)

            json_output = json.dumps(
                [
                    {"Path": "photo.jpg", "Size": 1024, "IsDir": False, "Hashes": {"MD5": "abc123"}},
                ]
            )

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout=json_output,
                    stderr="",
                )

                result = lister.list_remote_files("test-bucket")

                assert len(result) == 1
                assert result[0].path == "photo.jpg"
                assert result[0].hash_md5 == "abc123"

    def test_list_remote_files_handles_empty_bucket(self):
        """Test that list_remote_files handles empty bucket gracefully."""
        from photo_backup.config.config import Config
        from photo_backup.credentials.manager import CredentialManager
        from photo_backup.verify import RemoteLister

        config = Config(test_mode=True)
        credential_manager = CredentialManager(config)

        with patch.object(credential_manager, "get_credentials") as mock_creds:
            mock_creds.return_value = {
                "access_key": "key",
                "secret_key": "secret",
                "endpoint": "localhost:9000",
                "region": "us-east-1",
                "use_ssl": False,
            }

            lister = RemoteLister(config, credential_manager)

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="[]",
                    stderr="",
                )

                result = lister.list_remote_files("empty-bucket")

                assert result == []

    def test_list_remote_files_handles_directory_not_found(self):
        """Test that list_remote_files handles 'directory not found' gracefully."""
        from photo_backup.config.config import Config
        from photo_backup.credentials.manager import CredentialManager
        from photo_backup.verify import RemoteLister

        config = Config(test_mode=True)
        credential_manager = CredentialManager(config)

        with patch.object(credential_manager, "get_credentials") as mock_creds:
            mock_creds.return_value = {
                "access_key": "key",
                "secret_key": "secret",
                "endpoint": "localhost:9000",
                "region": "us-east-1",
                "use_ssl": False,
            }

            lister = RemoteLister(config, credential_manager)

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=1,
                    stdout="",
                    stderr="directory not found: bucket/nonexistent",
                )

                # Should return empty list, not raise
                result = lister.list_remote_files("bucket/nonexistent")

                assert result == []

    def test_list_remote_files_raises_on_other_errors(self):
        """Test that list_remote_files raises RuntimeError on other errors."""
        from photo_backup.config.config import Config
        from photo_backup.credentials.manager import CredentialManager
        from photo_backup.verify import RemoteLister

        config = Config(test_mode=True)
        credential_manager = CredentialManager(config)

        with patch.object(credential_manager, "get_credentials") as mock_creds:
            mock_creds.return_value = {
                "access_key": "key",
                "secret_key": "secret",
                "endpoint": "localhost:9000",
                "region": "us-east-1",
                "use_ssl": False,
            }

            lister = RemoteLister(config, credential_manager)

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=1,
                    stdout="",
                    stderr="Access Denied",
                )

                with pytest.raises(RuntimeError, match="rclone lsjson failed"):
                    lister.list_remote_files("test-bucket")

    def test_list_remote_files_handles_timeout(self):
        """Test that list_remote_files handles timeout."""
        import subprocess

        from photo_backup.config.config import Config
        from photo_backup.credentials.manager import CredentialManager
        from photo_backup.verify import RemoteLister

        config = Config(test_mode=True)
        credential_manager = CredentialManager(config)

        with patch.object(credential_manager, "get_credentials") as mock_creds:
            mock_creds.return_value = {
                "access_key": "key",
                "secret_key": "secret",
                "endpoint": "localhost:9000",
                "region": "us-east-1",
                "use_ssl": False,
            }

            lister = RemoteLister(config, credential_manager)

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired(cmd="rclone", timeout=300)

                with pytest.raises(RuntimeError, match="timed out"):
                    lister.list_remote_files("test-bucket")
