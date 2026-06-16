import logging
import shutil
from datetime import datetime
from pathlib import Path
from aqt import mw

logger = logging.getLogger("anki_concursos.sync.backup")

class BackupManager:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        
    def create_backup(self) -> Path:
        """Create a backup of the local SQLite DB and Anki collection."""
        if mw and mw.col:
            # Force Anki to create a backup / save point (doesn't backup add-on DBs though)
            mw.col.save()
            
        backup_dir = self.db_path.parent / "backups"
        backup_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"anki_concursos_{timestamp}.db.bak"
        
        if self.db_path.exists():
            shutil.copy2(self.db_path, backup_path)
            
        # Clean up old backups (keep last 5)
        backups = sorted(backup_dir.glob("*.db.bak"), key=lambda p: p.stat().st_mtime)
        if len(backups) > 5:
            for old_backup in backups[:-5]:
                try:
                    old_backup.unlink()
                except Exception:
                    pass
                    
        return backup_path

    def restore_backup(self, backup_path: Path) -> bool:
        """Restore the local SQLite DB from backup."""
        if not backup_path.exists():
            return False
            
        try:
            shutil.copy2(backup_path, self.db_path)
            return True
        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            return False
