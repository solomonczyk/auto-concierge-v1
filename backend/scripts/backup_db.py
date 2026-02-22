#!/usr/bin/env python3
"""
Database backup script for Auto Concierge V1
Usage: python scripts/backup_db.py

Environment variables:
    POSTGRES_SERVER - Database host
    POSTGRES_USER - Database user
    POSTGRES_PASSWORD - Database password
    POSTGRES_DB - Database name
    BACKUP_DIR - Directory to store backups (default: ./backups)
"""

import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path


def get_env_var(name: str, required: bool = True) -> str:
    """Get environment variable with optional requirement check"""
    value = os.getenv(name)
    if required and not value:
        print(f"Error: {name} environment variable is required")
        sys.exit(1)
    return value


def create_backup_dir(backup_dir: Path) -> None:
    """Create backup directory if it doesn't exist"""
    backup_dir.mkdir(parents=True, exist_ok=True)
    print(f"Backup directory: {backup_dir}")


def run_backup(
    host: str,
    user: str,
    password: str,
    db_name: str,
    backup_path: Path
) -> bool:
    """Run pg_dump to create database backup"""
    env = os.environ.copy()
    env["PGPASSWORD"] = password
    
    try:
        # Run pg_dump
        result = subprocess.run(
            [
                "pg_dump",
                "-h", host,
                "-U", user,
                "-Fc",  # Custom format (compressed)
                "-f", str(backup_path),
                db_name
            ],
            env=env,
            check=True,
            capture_output=True,
            text=True
        )
        print(f"Backup created successfully: {backup_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Backup failed: {e.stderr}")
        return False
    except FileNotFoundError:
        print("Error: pg_dump not found. Please install PostgreSQL client.")
        return False


def cleanup_old_backups(backup_dir: Path, keep_days: int = 7) -> None:
    """Remove backups older than keep_days"""
    if not backup_dir.exists():
        return
    
    now = datetime.now()
    removed_count = 0
    
    for backup_file in backup_dir.glob("*.dump"):
        # Get file modification time
        mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
        age_days = (now - mtime).days
        
        if age_days > keep_days:
            backup_file.unlink()
            removed_count += 1
            print(f"Removed old backup: {backup_file.name}")
    
    if removed_count > 0:
        print(f"Removed {removed_count} old backup(s)")


def main():
    """Main backup function"""
    print("=" * 50)
    print("Auto Concierge V1 - Database Backup")
    print("=" * 50)
    
    # Get environment variables
    host = get_env_var("POSTGRES_SERVER", required=True)
    user = get_env_var("POSTGRES_USER", required=True)
    password = get_env_var("POSTGRES_PASSWORD", required=True)
    db_name = get_env_var("POSTGRES_DB", required=True)
    backup_dir_path = get_env_var("BACKUP_DIR", required=False) or "./backups"
    
    # Create backup directory
    backup_dir = Path(backup_dir_path)
    create_backup_dir(backup_dir)
    
    # Generate backup filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"autoservice_backup_{timestamp}.dump"
    backup_path = backup_dir / backup_filename
    
    # Run backup
    print(f"\nStarting backup of database: {db_name}")
    success = run_backup(host, user, password, db_name, backup_path)
    
    if success:
        # Clean up old backups (keep last 7 days)
        print("\nCleaning up old backups...")
        cleanup_old_backups(backup_dir, keep_days=7)
        print("\nBackup completed successfully!")
        return 0
    else:
        print("\nBackup failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
