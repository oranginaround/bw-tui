"""
User interface module for bw-tui.

This module contains the curses-based UI components for browsing
the Bitwarden vault, searching items, and copying passwords.
"""

import curses
import pyperclip
import logging
from typing import List, Dict, Any, Optional

from bw_tui.bitwarden import BitwardenCLI


class MainWindow:
    """Main window for the bw-tui application."""
    
    def __init__(self, stdscr, bw_cli: BitwardenCLI):
        """Initialize the main window.
        
        Args:
            stdscr: The main curses screen object
            bw_cli: Bitwarden CLI wrapper instance
        """
        self.stdscr = stdscr
        self.bw_cli = bw_cli
        self.logger = logging.getLogger(__name__)
        
        # UI state
        self.items: List[Dict[str, Any]] = []
        self.filtered_items: List[Dict[str, Any]] = []
        self.current_selection = 0
        self.search_query = ""
        self.session_key: Optional[str] = None
        self.mode = "browse"  # browse, search, unlock
        
        # Window dimensions
        self.height, self.width = stdscr.getmaxyx()
        
        # Initialize curses
        self._init_curses()
        
        # Create windows
        self._create_windows()
    
    def _init_curses(self):
        """Initialize curses settings."""
        curses.curs_set(0)  # Hide cursor
        # Remove non-blocking input - we want blocking input
        # self.stdscr.nodelay(1)  # Non-blocking input
        # self.stdscr.timeout(100)  # 100ms timeout
        
        # Initialize colors
        curses.start_color()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)  # Selected
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Success
        curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)    # Error
        curses.init_pair(4, curses.COLOR_BLUE, curses.COLOR_BLACK)   # Info
    
    def _create_windows(self):
        """Create the UI windows."""
        # Header window
        self.header_win = curses.newwin(3, self.width, 0, 0)
        
        # Main content window
        self.main_win = curses.newwin(
            self.height - 5, self.width, 3, 0
        )
        
        # Status window
        self.status_win = curses.newwin(2, self.width, self.height - 2, 0)
    
    def run(self):
        """Run the main UI loop."""
        self.logger.debug("Starting UI main loop")
        
        # Check if vault is unlocked
        self.logger.debug("Checking if vault is unlocked...")
        if not self.bw_cli.is_unlocked():
            self.logger.debug("Vault is locked, requesting unlock")
            if not self._unlock_vault():
                self.logger.debug("Unlock failed or cancelled, exiting")
                return
        else:
            self.logger.debug("Vault is already unlocked")
        
        # Load initial items
        self.logger.debug("Loading initial items...")
        self._load_items()
        
        # Draw initial UI
        self._draw_ui()
        
        # Main loop - only redraw when there's input
        self.logger.debug("Entering main input loop")
        while True:
            self._handle_input()
    
    def _unlock_vault(self) -> bool:
        """Unlock the vault by prompting for password.
        
        Returns:
            True if successfully unlocked, False otherwise
        """
        self.logger.debug("Entering vault unlock mode")
        self.mode = "unlock"
        password = ""
        
        while True:
            self._draw_unlock_screen(password)
            
            ch = self.stdscr.getch()
            
            if ch == curses.KEY_ENTER or ch == 10:
                # Try to unlock
                self.logger.debug("Attempting to unlock vault with provided password")
                self.session_key = self.bw_cli.unlock(password)
                if self.session_key:
                    self.logger.debug(f"Unlock successful, session key received (length: {len(self.session_key)})")
                    self.mode = "browse"
                    return True
                else:
                    # Show error and try again
                    self.logger.debug("Unlock failed, invalid password")
                    password = ""
                    self._show_status("Invalid password. Try again.", error=True)
                    
            elif ch == 27:  # ESC
                self.logger.debug("User cancelled unlock process")
                return False
                
            elif ch == curses.KEY_BACKSPACE or ch == 127:
                password = password[:-1]
                
            elif ch >= 32 and ch <= 126:  # Printable characters
                password += chr(ch)
    
    def _draw_unlock_screen(self, password: str):
        """Draw the unlock screen.
        
        Args:
            password: Current password input (masked)
        """
        self.stdscr.clear()
        
        title = "bw-tui - Unlock Vault"
        self.stdscr.addstr(2, (self.width - len(title)) // 2, title, curses.A_BOLD)
        
        prompt = "Master Password: "
        mask = "*" * len(password)
        
        self.stdscr.addstr(self.height // 2, 5, prompt)
        self.stdscr.addstr(self.height // 2, 5 + len(prompt), mask)
        
        instructions = "Press ENTER to unlock, ESC to exit"
        self.stdscr.addstr(
            self.height - 3, 
            (self.width - len(instructions)) // 2, 
            instructions
        )
        
        self.stdscr.refresh()
    
    def _load_items(self):
        """Load items from the vault."""
        self.logger.debug("Loading items from vault...")
        self.items = self.bw_cli.get_items(self.session_key)
        self.logger.debug(f"Loaded {len(self.items)} items from vault")
        self.filtered_items = self.items.copy()
        self.current_selection = 0
        self.logger.debug(f"Filtered items count: {len(self.filtered_items)}")
        
        # Log some sample item names for debugging
        for i, item in enumerate(self.items[:3]):
            name = item.get("name", "Unknown")
            self.logger.debug(f"Item {i+1}: {name}")
    
    def _draw_ui(self):
        """Draw the main UI."""
        self._draw_header()
        self._draw_items()
        self._draw_status()
        
        self.stdscr.refresh()
    
    def _draw_header(self):
        """Draw the header window."""
        self.header_win.clear()
        self.header_win.box()
        
        title = "bw-tui - Bitwarden Terminal Interface"
        self.header_win.addstr(1, 2, title, curses.A_BOLD)
        
        if self.mode == "search":
            search_text = f"Search: {self.search_query}"
            self.header_win.addstr(1, self.width - len(search_text) - 2, search_text)
        
        self.header_win.refresh()
    
    def _draw_items(self):
        """Draw the items list."""
        self.main_win.clear()
        self.main_win.box()
        
        if not self.filtered_items:
            msg = "No items found" if self.search_query else "No items in vault"
            self.main_win.addstr(
                (self.height - 5) // 2, 
                (self.width - len(msg)) // 2, 
                msg
            )
        else:
            max_items = self.height - 7  # Account for borders and padding
            start_idx = max(0, self.current_selection - max_items // 2)
            end_idx = min(len(self.filtered_items), start_idx + max_items)
            
            for i, item in enumerate(self.filtered_items[start_idx:end_idx]):
                y = i + 1
                item_idx = start_idx + i
                
                # Format item display
                name = item.get("name", "Unknown")
                username = ""
                if item.get("login") and item["login"].get("username"):
                    username = f" ({item['login']['username']})"
                
                display_text = f"{name}{username}"
                
                # Truncate if too long
                max_width = self.width - 4
                if len(display_text) > max_width:
                    display_text = display_text[:max_width - 3] + "..."
                
                # Highlight selected item
                attrs = curses.color_pair(1) if item_idx == self.current_selection else 0
                
                self.main_win.addstr(y, 2, display_text, attrs)
        
        self.main_win.refresh()
    
    def _draw_status(self):
        """Draw the status window."""
        self.status_win.clear()
        
        # Show help text
        if self.mode == "browse":
            help_text = "q:quit | s:search | /:search | c:copy | ENTER:copy | ESC:clear search"
        elif self.mode == "search":
            help_text = "Type to search | ENTER:copy | ESC:clear search | q:quit"
        else:
            help_text = ""
        
        self.status_win.addstr(0, 0, help_text)
        
        # Show item count
        if self.filtered_items:
            count_text = f"Item {self.current_selection + 1} of {len(self.filtered_items)}"
            self.status_win.addstr(1, 0, count_text)
        
        self.status_win.refresh()
    
    def _show_status(self, message: str, error: bool = False):
        """Show a status message.
        
        Args:
            message: Message to display
            error: True if this is an error message
        """
        self.status_win.clear()
        color = curses.color_pair(3) if error else curses.color_pair(2)
        self.status_win.addstr(0, 0, message, color)
        self.status_win.refresh()
        curses.napms(2000)  # Show for 2 seconds
    
    def _handle_input(self):
        """Handle keyboard input."""
        ch = self.stdscr.getch()
        
        # Since we removed nodelay, getch() will block until input
        # So we don't need to check for -1 anymore
        
        redraw_needed = True  # Track if we need to redraw
        
        if ch == ord('q') and self.mode != "search":  # Quit only if not in search mode
            raise KeyboardInterrupt
        
        elif ch == 27:  # ESC - Clear search
            self.search_query = ""
            self.mode = "browse"
            self._filter_items()
        
        elif ch == ord('s') or ch == ord('/'):  # Start search
            self.mode = "search"
        
        elif ch == ord('c') or ch == curses.KEY_ENTER or ch == 10:  # Copy password
            self._copy_password()
        
        elif ch == curses.KEY_UP:
            if self.filtered_items:
                self.current_selection = max(0, self.current_selection - 1)
        
        elif ch == curses.KEY_DOWN:
            if self.filtered_items:
                self.current_selection = min(
                    len(self.filtered_items) - 1, 
                    self.current_selection + 1
                )
        
        elif self.mode == "search":
            if ch == curses.KEY_BACKSPACE or ch == 127:
                self.search_query = self.search_query[:-1]
                self._filter_items()
            elif ch >= 32 and ch <= 126:  # Printable characters (includes 'q')
                self.search_query += chr(ch)
                self._filter_items()
        else:
            redraw_needed = False  # No state change, no need to redraw
        
        # Only redraw if something changed
        if redraw_needed:
            self._draw_ui()
    
    def _filter_items(self):
        """Filter items based on search query."""
        if not self.search_query:
            self.filtered_items = self.items.copy()
        else:
            query_lower = self.search_query.lower()
            self.filtered_items = [
                item for item in self.items
                if (item.get("name", "") or "").lower().find(query_lower) != -1 or
                    (item.get("login") and 
                     (item["login"].get("username") or "").lower().find(query_lower) != -1)
            ]
        
        self.current_selection = 0
    
    def _copy_password(self):
        """Copy the selected item's password to clipboard."""
        if not self.filtered_items or self.current_selection >= len(self.filtered_items):
            return
        
        item = self.filtered_items[self.current_selection]
        
        if item.get("login") and item["login"].get("password"):
            password = item["login"]["password"]
            try:
                pyperclip.copy(password)
                self._show_status(f"Password copied for: {item.get('name', 'Unknown')}")
            except Exception:
                self._show_status("Failed to copy password to clipboard", error=True)
        else:
            self._show_status("No password found for this item", error=True)