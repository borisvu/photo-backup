"""
Unit tests for the RemoteLister class.

Tests remote file listing using `rclone lsf --format sp` (size + path only).
"""

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


def _make_lister():
    """Build a RemoteLister in test mode (parsing needs no credentials)."""
    from photo_backup.config.config import Config
    from photo_backup.credentials.manager import CredentialManager
    from photo_backup.verify import RemoteLister

    config = Config(test_mode=True)
    return RemoteLister(config, CredentialManager(config))


class TestRemoteListerLsfParsing:
    """Test RemoteLister parsing of `rclone lsf --format sp --separator '|'` output."""

    def test_parse_lsf_output_empty_string(self):
        """Test parsing empty output (empty bucket)."""
        lister = _make_lister()

        assert lister._parse_lsf_output("") == []

    def test_parse_lsf_output_blank_lines_only(self):
        """Test that blank lines are ignored."""
        lister = _make_lister()

        assert lister._parse_lsf_output("\n\n") == []

    def test_parse_lsf_output_single_file(self):
        """Test parsing a single size|path line; no hash or modtime is fetched."""
        lister = _make_lister()

        result = lister._parse_lsf_output("1024|photos/2024/photo.jpg\n")

        assert len(result) == 1
        assert result[0].path == "photos/2024/photo.jpg"
        assert result[0].size == 1024
        assert result[0].hash_md5 is None
        assert result[0].modified_time is None

    def test_parse_lsf_output_multiple_files(self):
        """Test parsing multiple lines preserves order, paths and sizes."""
        lister = _make_lister()

        output = "100|file1.jpg\n200|file2.jpg\n300|file3.jpg\n"

        result = lister._parse_lsf_output(output)

        assert [(f.path, f.size) for f in result] == [
            ("file1.jpg", 100),
            ("file2.jpg", 200),
            ("file3.jpg", 300),
        ]

    def test_parse_lsf_output_nested_paths(self):
        """Test that nested directory paths are kept as full relative paths."""
        lister = _make_lister()

        output = "1024|2024/01/IMG_0001.jpg\n2048|2024/02/trip/IMG_0002.heic\n"

        result = lister._parse_lsf_output(output)

        assert [f.path for f in result] == ["2024/01/IMG_0001.jpg", "2024/02/trip/IMG_0002.heic"]

    def test_parse_lsf_output_path_containing_separator(self):
        """Test that only the FIRST '|' splits size from path."""
        lister = _make_lister()

        result = lister._parse_lsf_output("512|albums/a|b/photo|1.jpg\n")

        assert len(result) == 1
        assert result[0].size == 512
        assert result[0].path == "albums/a|b/photo|1.jpg"

    def test_parse_lsf_output_zero_size_file(self):
        """Test that a zero-byte object is still listed."""
        lister = _make_lister()

        result = lister._parse_lsf_output("0|empty.txt\n")

        assert len(result) == 1
        assert result[0].size == 0

    def test_parse_lsf_output_skips_non_numeric_size(self):
        """Test that a line with a non-numeric size is skipped, others kept."""
        lister = _make_lister()

        output = "abc|bad.jpg\n100|good.jpg\n"

        result = lister._parse_lsf_output(output)

        assert [f.path for f in result] == ["good.jpg"]

    def test_parse_lsf_output_skips_malformed_lines(self):
        """Test that lines without a separator or without a path are skipped."""
        lister = _make_lister()

        output = "this is not lsf output\n123|\n100|good.jpg\n"

        result = lister._parse_lsf_output(output)

        assert [f.path for f in result] == ["good.jpg"]


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
                    stdout="",
                    stderr="",
                )

                lister.list_remote_files("test-bucket")

                # Verify rclone was called
                mock_run.assert_called_once()
                call_args = mock_run.call_args[0][0]

                assert call_args[:2] == ["rclone", "lsf"]
                assert "--files-only" in call_args
                assert "--recursive" in call_args
                assert "--fast-list" in call_args
                assert call_args[call_args.index("--format") + 1] == "sp"
                assert call_args[call_args.index("--separator") + 1] == "|"
                assert "test:test-bucket" in call_args
                assert "--config" in call_args
                # Per-object metadata flags trigger a HEAD per object on Wasabi
                assert "lsjson" not in call_args
                assert "--hash" not in call_args

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

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="1024|photo.jpg\n",
                    stderr="",
                )

                result = lister.list_remote_files("test-bucket")

                assert len(result) == 1
                assert result[0].path == "photo.jpg"
                assert result[0].size == 1024
                assert result[0].hash_md5 is None

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
                    stdout="",
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

                with pytest.raises(RuntimeError, match="rclone lsf failed: Access Denied"):
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
