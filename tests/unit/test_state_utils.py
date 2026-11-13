import os

import pytest

from photo_backup.state_utils import get_state_directories, load_json_state, save_json_state


class TestGetStateDirectories:
    """Test cases for get_state_directories function."""

    @pytest.mark.unit
    def test_get_state_directories_test_mode(self, tmp_path, monkeypatch):
        # Patch /tmp to a temp dir to avoid polluting real /tmp
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        # Patch base dir to use a subdir of tmp_path
        monkeypatch.setattr(
            "photo_backup.state_utils.os.path.expanduser",
            lambda path: str(tmp_path / "Library/Application Support/photo-backup") if path.startswith("~") else path,
        )
        # Test test_mode
        dirs = get_state_directories(test_mode=True)
        assert dirs["base"].startswith("/tmp/photo-backup-test")
        for sub in ["state", "config", "temp"]:
            assert sub in dirs
            assert os.path.isdir(dirs[sub])
            # Check permissions (should be 0o755)
            mode = os.stat(dirs[sub]).st_mode & 0o777
            assert mode == 0o755

    @pytest.mark.unit
    def test_get_state_directories_normal_mode(self, tmp_path, monkeypatch):
        # Patch expanduser to use tmp_path for home
        monkeypatch.setattr(
            "photo_backup.state_utils.os.path.expanduser",
            lambda path: str(tmp_path / "Library/Application Support/photo-backup") if path.startswith("~") else path,
        )
        dirs = get_state_directories(test_mode=False)
        assert "base" in dirs and "state" in dirs and "config" in dirs and "temp" in dirs
        for sub in ["base", "state", "config", "temp"]:
            assert os.path.isdir(dirs[sub])
            mode = os.stat(dirs[sub]).st_mode & 0o777
            assert mode == 0o755

    @pytest.mark.unit
    def test_get_state_directories_error(self, monkeypatch):
        # Simulate ensure_directory failure
        monkeypatch.setattr("photo_backup.state_utils.ensure_directory", lambda path: (False, "fail"))
        with pytest.raises(RuntimeError):
            get_state_directories(test_mode=True)


class TestJsonStateHelpers:
    """Test cases for save_json_state and load_json_state functions."""

    @pytest.mark.unit
    def test_save_and_load_json_state(self, tmp_path, monkeypatch):
        # Patch expanduser to use tmp_path for home
        monkeypatch.setattr(
            "photo_backup.state_utils.os.path.expanduser",
            lambda path: str(tmp_path / "Library/Application Support/photo-backup") if path.startswith("~") else path,
        )
        data = {"foo": 123, "bar": [1, 2, 3]}
        filename = "test_state.json"
        # Save
        success, error = save_json_state(data, filename, test_mode=False)
        assert success is True
        assert error is None
        # Load
        loaded, error = load_json_state(filename, test_mode=False)
        assert error is None
        assert loaded == data

    @pytest.mark.unit
    def test_load_json_state_file_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "photo_backup.state_utils.os.path.expanduser",
            lambda path: str(tmp_path / "Library/Application Support/photo-backup") if path.startswith("~") else path,
        )
        loaded, error = load_json_state("does_not_exist.json", test_mode=False)
        assert loaded is None
        assert "does not exist" in error

    @pytest.mark.unit
    def test_save_json_state_error(self, monkeypatch):
        # Simulate get_state_directories failure
        monkeypatch.setattr(
            "photo_backup.state_utils.get_state_directories",
            lambda test_mode: (_ for _ in ()).throw(RuntimeError("fail")),
        )
        success, error = save_json_state({}, "file.json", test_mode=False)
        assert success is False
        assert "Error saving JSON state" in error

    @pytest.mark.unit
    def test_load_json_state_error(self, monkeypatch):
        # Simulate get_state_directories failure
        monkeypatch.setattr(
            "photo_backup.state_utils.get_state_directories",
            lambda test_mode: (_ for _ in ()).throw(RuntimeError("fail")),
        )
        loaded, error = load_json_state("file.json", test_mode=False)
        assert loaded is None
        assert "Error loading JSON state" in error
