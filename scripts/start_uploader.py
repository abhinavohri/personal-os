"""Run the scan uploader on localhost for Tailscale Serve."""

import argparse
from pathlib import Path

import uvicorn
from dotenv import load_dotenv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env")
    uvicorn.run(
        "apps.uploader.main:app",
        app_dir=str(project_root),
        host="127.0.0.1",
        port=args.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
