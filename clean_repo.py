#!/usr/bin/env python3
import argparse
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

REPO_ROOT = Path(__file__).resolve().parent

# Default cleanup patterns (non-destructive: we move to archive on --apply)
DEFAULT_PATTERNS = [
    # Logs
    "*.log",
    "logs/*.log",
    # Generated result folders
    "backtest_results/**/*",
    # Data caches
    "data/cache/**/*",
    # History/junk
    ".Rhistory",
]

# Optional patterns for images at the repo root that are likely generated plots
IMAGE_PATTERNS = [
    "tao*.png",
]

EXCLUDE_ALWAYS = {
    # Never move these
    ".git",
    ".gitignore",
    "requirements.txt",
    "README.md",
}


def find_matches(patterns: List[str]) -> List[Path]:
    matches: List[Path] = []
    for pattern in patterns:
        # Use glob with recursive patterns
        for p in REPO_ROOT.glob(pattern):
            # Normalize to files only; keep dirs separately only if empty
            if p.is_file():
                matches.append(p)
            elif p.is_dir():
                # capture empty directories to remove when applying
                if not any(p.iterdir()):
                    matches.append(p)
    # De-duplicate and keep within repo
    unique: List[Path] = []
    seen = set()
    for m in matches:
        try:
            rel = m.relative_to(REPO_ROOT)
        except ValueError:
            continue
        if str(rel) in EXCLUDE_ALWAYS:
            continue
        if m.exists() and m not in seen:
            unique.append(m)
            seen.add(m)
    return unique


def plan_cleanup(include_images: bool) -> List[Path]:
    patterns = list(DEFAULT_PATTERNS)
    if include_images:
        patterns.extend(IMAGE_PATTERNS)
    return find_matches(patterns)


def archive_path() -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return REPO_ROOT / "archive" / f"cleanup_{ts}"


def move_to_archive(paths: List[Path]) -> Tuple[int, int]:
    arch_root = archive_path()
    files_moved = 0
    dirs_removed = 0
    arch_root.mkdir(parents=True, exist_ok=True)

    for p in paths:
        rel = p.relative_to(REPO_ROOT)
        dest = arch_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if p.is_file():
            shutil.move(str(p), str(dest))
            files_moved += 1
        elif p.is_dir():
            # Try removing empty directories, otherwise move whole dir
            try:
                p.rmdir()
                dirs_removed += 1
            except OSError:
                shutil.move(str(p), str(dest))
                dirs_removed += 1
    return files_moved, dirs_removed


def main() -> None:
    parser = argparse.ArgumentParser(description="Repository cleanup utility (non-destructive by default)")
    parser.add_argument("--apply", action="store_true", help="Apply changes by moving items to an archive directory")
    parser.add_argument("--include-images", action="store_true", help="Include root-level generated images like tao*.png")
    parser.add_argument("--patterns", nargs="*", help="Additional glob patterns to include (space-separated)")

    args = parser.parse_args()

    candidates = plan_cleanup(include_images=args.include_images)
    if args.patterns:
        candidates.extend(find_matches(args.patterns))

    # Normalize and sort
    dedup = []
    seen = set()
    for c in candidates:
        if c.exists() and c not in seen:
            dedup.append(c)
            seen.add(c)
    dedup.sort(key=lambda p: (p.is_dir(), str(p)))

    if not dedup:
        print("No cleanup candidates found.")
        return

    print("Cleanup candidates (would be archived):")
    for p in dedup:
        rel = p.relative_to(REPO_ROOT)
        size = p.stat().st_size if p.is_file() else 0
        size_kb = f"{size/1024:.1f} KB" if size else "DIR"
        print(f" - {rel}  \t{size_kb}")

    if not args.apply:
        print("\nDry-run complete. Re-run with --apply to move items to archive/.")
        return

    files_moved, dirs_handled = move_to_archive(dedup)
    print(f"\nMoved {files_moved} files and handled {dirs_handled} directories to: {archive_path().relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()




