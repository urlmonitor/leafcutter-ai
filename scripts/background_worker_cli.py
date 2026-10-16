"""Repository-explicit entry point for the opt-in background worker."""

from background_worker.wsl_runtime import main

if __name__ == "__main__":
    raise SystemExit(main())
