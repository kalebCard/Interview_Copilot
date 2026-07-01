
import sys

from copilot.check import run_check
from copilot.ui import run_app

def main() -> None:

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    if "--check" in sys.argv:
        run_check()
        return

    run_app()

if __name__ == "__main__":
    main()
