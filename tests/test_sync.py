"""Tests for sync module."""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess

import pytest

from shealth.sync import (
    get_file_hash,
    get_last_sync_time,
    sync_data,
    download_health_data,
    extract_database,
)


class TestFileHash:
    """Test file hashing functionality."""

    def test_hash_consistent(self):
        """Test that same content produces same hash."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("test content")
            f.flush()
            path = Path(f.name)

        hash1 = get_file_hash(path)
        hash2 = get_file_hash(path)
        
        assert hash1 == hash2
        assert len(hash1) == 32  # MD5 hex length
        path.unlink()

    def test_hash_different_content(self):
        """Test that different content produces different hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path1 = Path(tmpdir) / "file1.txt"
            path2 = Path(tmpdir) / "file2.txt"
            
            path1.write_text("content A")
            path2.write_text("content B")
            
            assert get_file_hash(path1) != get_file_hash(path2)


class TestLastSyncTime:
    """Test last sync time detection."""

    def test_no_db_returns_none(self):
        """Test that missing database returns None."""
        with patch("shealth.sync.get_config") as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.db_path = Path("/nonexistent/path/db.sqlite")
            mock_config.return_value = mock_cfg
            
            result = get_last_sync_time()
            assert result is None

    def test_existing_db_returns_mtime(self):
        """Test that existing database returns modification time."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            db_path = Path(f.name)

        with patch("shealth.sync.get_config") as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.db_path = db_path
            mock_config.return_value = mock_cfg
            
            result = get_last_sync_time()
            assert result is not None
            assert isinstance(result, datetime)
        
        db_path.unlink()


class TestSyncData:
    """Test main sync functionality."""

    def test_sync_missing_config(self):
        """Test sync fails gracefully with missing config."""
        with patch("shealth.sync.get_config") as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.get.return_value = ""  # Empty folder_id and account
            mock_config.return_value = mock_cfg
            
            result = sync_data()
            assert result is False

    def test_sync_missing_gog(self):
        """Test sync fails gracefully when gog CLI is missing."""
        with patch("shealth.sync.get_config") as mock_config, \
             patch("subprocess.run") as mock_run:
            
            mock_cfg = MagicMock()
            mock_cfg.get.side_effect = lambda key, default=None: {
                "google_drive.folder_id": "test_id",
                "google_drive.account": "test@example.com",
            }.get(key, default)
            mock_config.return_value = mock_cfg
            
            # Simulate gog not found
            mock_run.return_value = MagicMock(returncode=1)
            
            result = sync_data()
            assert result is False


class TestExtractDatabase:
    """Test database extraction from zip."""

    def test_extract_valid_zip(self):
        """Test extraction from valid zip file."""
        import zipfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test zip with a db file
            zip_path = Path(tmpdir) / "test.zip"
            db_content = b"SQLite format 3\x00"  # Fake SQLite header
            
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("health_connect_export.db", db_content)
            
            # Mock config to use temp directory
            with patch("shealth.sync.get_config") as mock_config:
                mock_cfg = MagicMock()
                mock_cfg.db_path = Path(tmpdir) / "extracted.db"
                mock_config.return_value = mock_cfg
                
                result = extract_database(zip_path)
                
                assert result is True
                assert mock_cfg.db_path.exists()
                assert mock_cfg.db_path.read_bytes() == db_content

    def test_extract_no_db_in_zip(self):
        """Test extraction fails when no db file in zip."""
        import zipfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "test.zip"
            
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("random_file.txt", "not a database")
            
            with patch("shealth.sync.get_config") as mock_config:
                mock_cfg = MagicMock()
                mock_cfg.db_path = Path(tmpdir) / "extracted.db"
                mock_config.return_value = mock_cfg
                
                result = extract_database(zip_path)
                assert result is False

    def test_extract_invalid_zip(self):
        """Test extraction fails for invalid zip file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_zip = Path(tmpdir) / "bad.zip"
            bad_zip.write_text("not a zip file")
            
            with patch("shealth.sync.get_config") as mock_config:
                mock_cfg = MagicMock()
                mock_cfg.db_path = Path(tmpdir) / "extracted.db"
                mock_config.return_value = mock_cfg
                
                result = extract_database(bad_zip)
                assert result is False
