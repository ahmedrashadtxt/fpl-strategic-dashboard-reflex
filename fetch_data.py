"""Official FPL API Data Ingestion Entry Point for scheduled syncs."""
import sys
from pathlib import Path

# Ensure project root is in sys.path
root = Path(__file__).resolve().parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from fpl_strategic_dashboard_reflex.services.fetch_data import fetch_all_data


def main():
    fetch_all_data()


if __name__ == "__main__":
    main()
