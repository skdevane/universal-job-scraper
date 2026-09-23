"""
Launcher for AI Job Scraper.
Spawns scraper.py in an interactive Windows process so the headed browser
appears on screen. Monitors scraper_output.log and prints progress here.
"""
import subprocess
import sys
import time
import os
import argparse
from pathlib import Path

def launch_scraper(url: str, company: str):
    log_path = Path("scraper_output.log")

    # Clear previous log
    if log_path.exists():
        log_path.unlink()

    # Build args
    python  = sys.executable
    script  = str(Path(__file__).parent / "scraper.py")
    cmd     = f'"{python}" "{script}" --url "{url}" --company "{company}"'

    print(f"\n  >> Launching scraper for: {company}")
    print(f"  >> URL: {url}")
    print(f"  >> Browser will open on your screen shortly...\n")

    # DETACHED_PROCESS + CREATE_NEW_CONSOLE = launches in a real visible desktop window
    DETACHED_PROCESS    = 0x00000008
    CREATE_NEW_CONSOLE  = 0x00000010

    proc = subprocess.Popen(
        cmd,
        cwd=str(Path(__file__).parent),
        creationflags=CREATE_NEW_CONSOLE,
        shell=True,
    )

    print(f"  >> Scraper PID: {proc.pid} — monitoring scraper_output.log ...\n")

    # Tail the log file until SCRAPE_COMPLETE or NO_JOBS_FOUND
    seen_bytes = 0
    timeout    = 600   # 10 min max
    start      = time.time()

    while time.time() - start < timeout:
        time.sleep(2)

        if not log_path.exists():
            continue

        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(seen_bytes)
            new_text = f.read()
            seen_bytes = f.tell()

        if new_text:
            print(new_text, end="", flush=True)

        if "SCRAPE_COMPLETE" in new_text or "NO_JOBS_FOUND" in new_text:
            print("\n  >> Done. Scraper finished.")
            break

        # Check if process died unexpectedly
        if proc.poll() is not None and not log_path.exists():
            print("  >> ERROR: Scraper process exited unexpectedly.")
            break
    else:
        print("  >> TIMEOUT: Scraper took too long.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url",     required=True)
    parser.add_argument("--company", required=True)
    args = parser.parse_args()
    launch_scraper(args.url, args.company)
