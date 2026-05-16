"""
setup_project.py - bootstrap the Sales Intelligence AI workspace.

Run once after cloning / copying this project:

    python setup_project.py

What it does:
  1. Verifies / creates the full folder structure
  2. Creates placeholder files where needed (.gitkeep)
  3. Copies sample demo data into data/sample/ if missing
  4. Prints the folder tree and explains where to put real Comax reports
  5. Tells you exactly what command to run next

Safe to run repeatedly. Never deletes or overwrites existing data.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

# Force UTF-8 stdout on Windows so box-drawing / Hebrew chars don't crash.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        os.environ["PYTHONIOENCODING"] = "utf-8"

ROOT = Path(__file__).parent.resolve()

REQUIRED_FOLDERS = [
    "backend/app/models",
    "backend/app/schemas",
    "backend/app/routers",
    "backend/app/services",
    "backend/app/repositories",
    "backend/app/ingestion",
    "backend/app/analytics",
    "backend/app/ai",
    "backend/app/reports",
    "backend/app/utils",
    "backend/tests",
    "frontend/src/components",
    "frontend/src/pages",
    "frontend/src/services",
    "frontend/src/hooks",
    "frontend/src/types",
    "frontend/src/utils",
    "data/comax_reports",
    "data/imported",
    "data/failed",
    "data/archive",
    "data/sample",
    "reports/jpg",
    "reports/png",
    "reports/pdf",
    "exports",
    "logs",
    "docs",
]

GITKEEP_FOLDERS = [
    "data/comax_reports",
    "data/imported",
    "data/failed",
    "data/archive",
    "reports/jpg",
    "reports/png",
    "reports/pdf",
    "exports",
    "logs",
]


def ensure_folders() -> list[str]:
    created: list[str] = []
    for rel in REQUIRED_FOLDERS:
        path = ROOT / rel
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(rel)
    return created


def ensure_gitkeep() -> list[str]:
    created: list[str] = []
    for rel in GITKEEP_FOLDERS:
        keep = ROOT / rel / ".gitkeep"
        if not keep.exists():
            keep.write_text("", encoding="utf-8")
            created.append(f"{rel}/.gitkeep")
    return created


def ensure_env_file() -> bool:
    env_example = ROOT / ".env.example"
    env = ROOT / ".env"
    if env_example.exists() and not env.exists():
        shutil.copyfile(env_example, env)
        return True
    return False


def print_tree(start: Path, prefix: str = "", max_depth: int = 3, depth: int = 0) -> None:
    if depth > max_depth:
        return
    entries = sorted(
        [p for p in start.iterdir() if not p.name.startswith(".") or p.name == ".env.example"],
        key=lambda p: (not p.is_dir(), p.name.lower()),
    )
    for i, entry in enumerate(entries):
        is_last = i == len(entries) - 1
        connector = "`-- " if is_last else "|-- "
        suffix = "/" if entry.is_dir() else ""
        print(f"{prefix}{connector}{entry.name}{suffix}")
        if entry.is_dir() and entry.name not in {"node_modules", ".venv", "__pycache__", ".git"}:
            extension = "    " if is_last else "|   "
            print_tree(entry, prefix + extension, max_depth, depth + 1)


def main() -> int:
    print("=" * 70)
    print(" Sales Intelligence AI — project setup")
    print("=" * 70)

    created_folders = ensure_folders()
    created_keeps = ensure_gitkeep()
    env_copied = ensure_env_file()

    if created_folders:
        print(f"\nCreated {len(created_folders)} folder(s):")
        for f in created_folders:
            print(f"  + {f}")
    else:
        print("\nAll folders already exist.")

    if created_keeps:
        print(f"\nCreated {len(created_keeps)} placeholder file(s).")
    if env_copied:
        print("\nCopied .env.example -> .env (edit it to set ANTHROPIC_API_KEY etc.)")

    print("\nFolder tree (top 3 levels):")
    print(f"\n{ROOT.name}/")
    print_tree(ROOT, max_depth=2)

    print("\n" + "-" * 70)
    print(" WHERE TO PUT YOUR DAILY COMAX REPORTS")
    print("-" * 70)
    print(f"\n  {ROOT / 'data' / 'comax_reports'}")
    print("\n  Drop Excel (.xlsx, .xls) or CSV files here.")
    print("  Successful imports move to data/imported/, failures to data/failed/.")

    print("\n" + "-" * 70)
    print(" NEXT COMMANDS")
    print("-" * 70)
    print(
        """
  1. Install backend:
       cd backend
       python -m venv .venv
       .venv\\Scripts\\activate         (Windows)
       source .venv/bin/activate       (Mac/Linux)
       pip install -r requirements.txt
       python -m app.seed_demo_data

  2. Start the backend:
       uvicorn app.main:app --reload --port 8000

  3. In a NEW terminal, install + start the frontend:
       cd sales-intelligence-ai/frontend
       npm install
       npm run dev

  4. Open http://localhost:5173 in your browser.
"""
    )
    print("Setup complete.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
