import os
import zipfile
from pathlib import Path

def build():
    root_dir = Path(__file__).parent
    addon_dir = root_dir / "anki_concursos"
    output_zip = root_dir / "anki_concursos.ankiaddon"
    
    if output_zip.exists():
        try:
            os.remove(output_zip)
        except Exception as e:
            print(f"Warning: Could not remove old package: {e}")
        
    # Exclusions
    exclude_dirs = {
        "__pycache__",
        ".pytest_cache",
        "tests",
        "docs",
        "user_files"
    }
    
    exclude_files = {
        ".git",
        ".gitignore",
        "anki_concursos.db",
        "auth.json",
        "anki_concursos.log"
    }
    
    print("Packaging Anki Concursos add-on...")
    
    count = 0
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file_path in addon_dir.rglob("*"):
            # Determine relative path from addon_dir
            rel_path = file_path.relative_to(addon_dir)
            
            # Check exclusions
            parts = rel_path.parts
            
            should_exclude = False
            for p in parts:
                if p in exclude_dirs or p.endswith(".pyc"):
                    should_exclude = True
                    break
            
            if file_path.name in exclude_files or file_path.suffix == ".pyc":
                should_exclude = True
                
            if should_exclude:
                continue
                
            if file_path.is_file():
                print(f"Adding: {rel_path}")
                zipf.write(file_path, arcname=rel_path)
                count += 1
                
    print(f"Created: {output_zip.name} successfully containing {count} files!")

if __name__ == "__main__":
    build()
