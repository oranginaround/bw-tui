"""
Main application class for bw-tui.

This module contains the main BwTuiApp class that handles the curses
interface and coordinates between the Bitwarden CLI wrapper and the UI.
"""

import curses
import sys
import logging
import os
from typing import Optional

from bw_tui.bitwarden import BitwardenCLI
from bw_tui.ui import MainWindow


class BwTuiApp:
    """Main application class for bw-tui."""
    
    def __init__(self):
        """Initialize the application."""
        self.bw_cli = None
        self.main_window: Optional[MainWindow] = None
        
        # Set up logging - only log to file if BW_DEBUG=1 is set
        debug_env = os.environ.get('BW_DEBUG', '0') == '1'
        if debug_env:
            logging.basicConfig(
                level=logging.DEBUG,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                filename='bw-tui.log'
            )
        
        self.logger = logging.getLogger(__name__)
    
    def run(self):
        """Run the main application loop."""
        try:
            # Initialize the Bitwarden CLI wrapper
            self.bw_cli = BitwardenCLI()
            
            # Check if Bitwarden CLI is available
            if not self.bw_cli.check_cli_available():
                print("Error: Bitwarden CLI is not available.")
                print("Please install it with: npm install -g @bitwarden/cli")
                sys.exit(1)
            
            # Check if user is logged in
            if not self.bw_cli.is_logged_in():
                print("Error: You are not logged in to Bitwarden.")
                print("Please run 'bw login' first.")
                sys.exit(1)
            
            # Initialize curses and run the UI
            curses.wrapper(self._run_ui)
            
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error("Application error: %s", e)
            raise
    
    def _run_ui(self, stdscr):
        """Run the curses UI.
        
        Args:
            stdscr: The main curses screen object
        """
        try:
            self.main_window = MainWindow(stdscr, self.bw_cli)
            self.main_window.run()
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error("UI error: %s", e)
            raise