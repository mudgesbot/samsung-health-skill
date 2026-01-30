"""Data synchronization from Google Drive."""

import hashlib
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from rich.console import Console

from .config import get_config

console = Console()


def get_file_hash(path: Path) -> str:
    """Calculate MD5 hash of a file."""
    hasher = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def download_health_data(force: bool = False) -> bool:
    """Download Health Connect data from Google Drive.

    Args:
        force: Force download even if cached version exists

    Returns:
        True if new data was downloaded, False if using cached version
    """
    config = get_config()
    config.ensure_dirs()

    folder_id = config.get("google_drive.folder_id")
    account = config.get("google_drive.account")
    file_name = config.get("google_drive.file_name", "Health Connect.zip")

    cache_zip = config.cache_dir / "health_connect.zip"
    cache_hash_file = config.cache_dir / "health_connect.md5"

    # Download to temp location first
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_zip = Path(tmpdir) / "download.zip"

        console.print(f"[blue]📥 Downloading from Google Drive...[/blue]")

        # Use gog CLI to download
        # First, list files in the folder to get the file ID
        result = subprocess.run(
            [
                "gog",
                "drive",
                "ls",
                "--folder-id",
                folder_id,
                "--account",
                account,
                "--json",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            console.print(f"[red]Failed to list Google Drive folder: {result.stderr}[/red]")
            return False

        # Parse JSON output to find the file
        import json

        try:
            files = json.loads(result.stdout)
        except json.JSONDecodeError:
            console.print(f"[red]Failed to parse Google Drive response[/red]")
            return False

        # Find the Health Connect zip file
        file_id = None
        for f in files:
            if f.get("name") == file_name:
                file_id = f.get("id")
                break

        if not file_id:
            console.print(f"[red]File '{file_name}' not found in Google Drive folder[/red]")
            return False

        # Download the file
        result = subprocess.run(
            [
                "gog",
                "drive",
                "download",
                file_id,
                "--output",
                str(tmp_zip),
                "--account",
                account,
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            console.print(f"[red]Failed to download file: {result.stderr}[/red]")
            return False

        if not tmp_zip.exists():
            console.print(f"[red]Download failed - file not created[/red]")
            return False

        # Check if file changed
        new_hash = get_file_hash(tmp_zip)

        if not force and cache_hash_file.exists():
            old_hash = cache_hash_file.read_text().strip()
            if old_hash == new_hash:
                console.print("[yellow]✓ Data unchanged since last sync[/yellow]")
                return False

        # Copy to cache
        shutil.copy2(tmp_zip, cache_zip)
        cache_hash_file.write_text(new_hash)
        console.print(f"[green]✓ Downloaded new data ({tmp_zip.stat().st_size / 1024 / 1024:.1f} MB)[/green]")

        # Extract database
        return extract_database(cache_zip)


def extract_database(zip_path: Path) -> bool:
    """Extract the database from the zip file.

    Args:
        zip_path: Path to the downloaded zip file

    Returns:
        True if extraction successful
    """
    config = get_config()
    db_path = config.db_path

    console.print("[blue]📦 Extracting database...[/blue]")

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            # Find the database file
            db_name = None
            for name in zf.namelist():
                if name.endswith(".db") or "health_connect" in name.lower():
                    db_name = name
                    break

            if not db_name:
                console.print("[red]No database file found in archive[/red]")
                return False

            # Extract to data directory
            with zf.open(db_name) as src:
                with open(db_path, "wb") as dst:
                    dst.write(src.read())

        console.print(f"[green]✓ Database extracted to {db_path}[/green]")
        return True

    except zipfile.BadZipFile:
        console.print("[red]Invalid zip file[/red]")
        return False
    except Exception as e:
        console.print(f"[red]Extraction failed: {e}[/red]")
        return False


def sync_data(force: bool = False) -> bool:
    """Perform full data sync.

    Args:
        force: Force re-download even if cached

    Returns:
        True if sync successful
    """
    config = get_config()

    # Check if gog CLI is available
    result = subprocess.run(["which", "gog"], capture_output=True)
    if result.returncode != 0:
        console.print("[red]Error: 'gog' CLI not found. Please install it first.[/red]")
        return False

    console.print(f"[bold]🔄 Syncing Samsung Health data...[/bold]")
    console.print(f"   Folder: {config.get('google_drive.folder_id')}")
    console.print(f"   Account: {config.get('google_drive.account')}")
    console.print()

    return download_health_data(force=force)


def get_last_sync_time() -> datetime | None:
    """Get the timestamp of the last successful sync."""
    config = get_config()
    db_path = config.db_path

    if db_path.exists():
        return datetime.fromtimestamp(db_path.stat().st_mtime)
    return None
