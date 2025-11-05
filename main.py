#!/usr/bin/env python3
"""
bw-tui: A curses-based terminal interface for Bitwarden CLI

A minimal console password manager that wraps the Bitwarden CLI
in a user-friendly terminal interface for browsing, copying passwords,
and searching your vault.
"""

import sys
import argparse
from bw_tui.app import BwTuiApp


def main():
    """Main entry point for bw-tui application."""
    parser = argparse.ArgumentParser(
        description="A curses-based terminal interface for Bitwarden CLI"
    )
    parser.add_argument(
        "--version",
        action="version",
        version="bw-tui 0.1.0"
    )
    
    args = parser.parse_args()  # Keep this for potential future use
    
    try:
        app = BwTuiApp()
        app.run()
    except KeyboardInterrupt:
        print("\nExiting bw-tui...")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        # Only show traceback if BW_DEBUG=1
        import os
        if os.environ.get('BW_DEBUG', '0') == '1':
            import traceback
            print("Debug traceback:")
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()