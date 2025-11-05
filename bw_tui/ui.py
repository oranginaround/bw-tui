"""
User interface module for bw-tui.

This module contains the curses-based UI components for browsing
the Bitwarden vault, searching items, and copying passwords.
"""

import curses
import pyperclip
import logging
import time
import subprocess
from typing import List, Dict, Any

from bw_tui.bitwarden import BitwardenCLI


class ClipboardManager:
    """Cross-platform clipboard manager with multiple fallback methods."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def copy_to_clipboard(self, text: str) -> bool:
        """Copy text to clipboard using the best available method.
        
        Returns:
            True if successful, False otherwise
        """
        methods = [
            self._try_pyperclip,
            self._try_xclip,
            self._try_xsel,
            self._try_wl_copy,
            self._try_termux_clipboard,
        ]
        
        for method in methods:
            try:
                if method(text):
                    self.logger.debug("Successfully copied to clipboard using %s", method.__name__)
                    return True
            except (OSError, subprocess.SubprocessError, ValueError) as e:
                self.logger.debug("Clipboard method %s failed: %s", method.__name__, e)
                continue
        
        self.logger.warning("All clipboard methods failed")
        return False
    
    def _try_pyperclip(self, text: str) -> bool:
        """Try using pyperclip."""
        try:
            pyperclip.copy(text)
            return True
        except (OSError, pyperclip.PyperclipException):
            return False
    
    def _try_xclip(self, text: str) -> bool:
        """Try using xclip (X11 clipboard)."""
        try:
            process = subprocess.run(
                ['xclip', '-selection', 'clipboard'],
                input=text,
                text=True,
                check=True,
                capture_output=True
            )
            return process.returncode == 0
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _try_xsel(self, text: str) -> bool:
        """Try using xsel (X11 clipboard)."""
        try:
            process = subprocess.run(
                ['xsel', '--clipboard', '--input'],
                input=text,
                text=True,
                check=True,
                capture_output=True
            )
            return process.returncode == 0
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _try_wl_copy(self, text: str) -> bool:
        """Try using wl-copy (Wayland clipboard)."""
        try:
            process = subprocess.run(
                ['wl-copy'],
                input=text,
                text=True,
                check=True,
                capture_output=True
            )
            return process.returncode == 0
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _try_termux_clipboard(self, text: str) -> bool:
        """Try using termux-clipboard (for Termux/Android)."""
        try:
            process = subprocess.run(
                ['termux-clipboard-set'],
                input=text,
                text=True,
                check=True,
                capture_output=True
            )
            return process.returncode == 0
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False


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
        self.clipboard = ClipboardManager()
        
        # UI state
        self.items: List[Dict[str, Any]] = []
        self.filtered_items: List[Dict[str, Any]] = []
        self.current_selection = 0
        self.search_query = ""
        self.mode = "browse"  # browse, search, unlock
        self.status_message = ""  # Temporary status message
        self.status_color = 0     # Color pair for status message
        self.status_message_time = 0  # Timestamp when message was set
        
        # Window dimensions
        self.height, self.width = stdscr.getmaxyx()
        
        # Initialize curses
        self._init_curses()
        
        # Create windows
        self._create_windows()
    
    def _init_curses(self):
        """Initialize curses settings."""
        curses.curs_set(0)  # Hide cursor
        curses.cbreak()     # Disable line buffering
        curses.noecho()     # Don't echo input
        self.stdscr.keypad(True)  # Enable special keys
        self.stdscr.nodelay(True)  # Non-blocking input
        self.stdscr.timeout(50)    # 50ms timeout for better responsiveness
        
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
        
        # Disable non-blocking input for password entry
        self.stdscr.nodelay(False)
        self.stdscr.timeout(-1)  # Blocking input
        
        try:
            # Draw initial screen
            self._draw_unlock_screen(password)
            
            while True:
                try:
                    ch = self.stdscr.getch()
                    self.logger.debug("Received key code: %d", ch)
                    
                    old_password = password
                    
                    if ch == curses.KEY_ENTER or ch == 10 or ch == 13:
                        # Try to unlock
                        self.logger.debug("Attempting to unlock vault with provided password")
                        session_key = self.bw_cli.unlock(password)
                        if session_key:
                            self.logger.debug("Unlock successful")
                            self.mode = "browse"
                            # Session key is now managed by the CLI wrapper
                            return True
                        else:
                            # Show error and try again
                            self.logger.debug("Unlock failed, invalid password")
                            password = ""
                            self._show_status("Invalid password. Try again.", error=True)
                            
                    elif ch == 27:  # ESC
                        self.logger.debug("User cancelled unlock process")
                        return False
                        
                    elif ch == curses.KEY_BACKSPACE or ch == 127 or ch == 8:
                        if password:
                            password = password[:-1]
                            self.logger.debug("Backspace pressed, password length now: %d", len(password))
                        
                    elif ch >= 32 and ch <= 126:  # Printable characters
                        password += chr(ch)
                        self.logger.debug("Added character, password length now: %d", len(password))
                        
                    # Handle other special keys (ignore them)
                    elif ch != -1:
                        self.logger.debug("Ignoring special key: %d", ch)
                    
                    # Only redraw if password changed
                    if password != old_password:
                        self._draw_unlock_screen(password)
                        
                except (KeyboardInterrupt, EOFError) as e:
                    self.logger.error("Input handling interrupted: %s", e)
                    return False
        finally:
            # Re-enable non-blocking input for main interface
            self.stdscr.nodelay(True)
            self.stdscr.timeout(50)
    
    def _draw_unlock_screen(self, password: str):
        """Draw the unlock screen.
        
        Args:
            password: Current password input (masked)
        """
        self.stdscr.clear()
        
        # Title
        title = "🔐 bw-tui - Unlock Vault"
        self.stdscr.addstr(2, (self.width - len(title)) // 2, title, curses.A_BOLD)
        
        # Calculate box dimensions
        box_width = 50
        box_height = 8
        box_x = (self.width - box_width) // 2
        box_y = (self.height - box_height) // 2
        
        # Draw box border (with fallback for terminals that don't support ACS)
        try:
            ul_char = curses.ACS_ULCORNER
            ur_char = curses.ACS_URCORNER
            ll_char = curses.ACS_LLCORNER
            lr_char = curses.ACS_LRCORNER
            h_char = curses.ACS_HLINE
            v_char = curses.ACS_VLINE
        except (AttributeError, ValueError):
            # Fallback to ASCII characters for terminals that don't support ACS
            ul_char = '+'
            ur_char = '+'
            ll_char = '+'
            lr_char = '+'
            h_char = '-'
            v_char = '|'
        
        for i in range(box_height):
            for j in range(box_width):
                x = box_x + j
                y = box_y + i
                
                if i == 0 and j == 0:
                    self.stdscr.addch(y, x, ul_char)
                elif i == 0 and j == box_width - 1:
                    self.stdscr.addch(y, x, ur_char)
                elif i == box_height - 1 and j == 0:
                    self.stdscr.addch(y, x, ll_char)
                elif i == box_height - 1 and j == box_width - 1:
                    self.stdscr.addch(y, x, lr_char)
                elif i == 0 or i == box_height - 1:
                    self.stdscr.addch(y, x, h_char)
                elif j == 0 or j == box_width - 1:
                    self.stdscr.addch(y, x, v_char)
        
        # Box title
        box_title = " Enter Master Password "
        title_x = box_x + (box_width - len(box_title)) // 2
        self.stdscr.addstr(box_y + 1, title_x, box_title, curses.A_BOLD)
        
        # Password prompt and input
        prompt = "Password:"
        prompt_x = box_x + 4
        prompt_y = box_y + 3
        self.stdscr.addstr(prompt_y, prompt_x, prompt, curses.A_BOLD)
        
        # Password input field (with background)
        input_width = 30
        input_x = box_x + 4 + len(prompt) + 1
        input_bg = " " * input_width
        self.stdscr.addstr(prompt_y, input_x, input_bg, curses.A_REVERSE)
        
        # Password mask
        mask = "*" * len(password)
        if len(mask) > input_width - 2:
            mask = mask[:input_width - 2]
        mask_x = input_x + 1
        self.stdscr.addstr(prompt_y, mask_x, mask, curses.A_REVERSE | curses.A_BOLD)
        
        # Instructions
        instructions = "ENTER to unlock • ESC to exit"
        instr_x = box_x + (box_width - len(instructions)) // 2
        self.stdscr.addstr(box_y + 5, instr_x, instructions, curses.A_DIM)
        
        self.stdscr.refresh()
    
    def _load_items(self):
        """Load items from the vault."""
        self.logger.debug("Loading items from vault...")
        self.items = self.bw_cli.get_items()
        self.logger.debug("Loaded %d items from vault", len(self.items))
        self.filtered_items = self.items.copy()
        self.current_selection = 0
        self.logger.debug("Filtered items count: %d", len(self.filtered_items))
        
        # Log some sample item names for debugging
        for i, item in enumerate(self.items[:3]):
            name = item.get("name", "Unknown")
            self.logger.debug("Item %d: %s", i+1, name)


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
        # Clear expired status messages (after 3 seconds)
        if self.status_message and time.time() - self.status_message_time > 3:
            self.status_message = ""
            self.status_color = 0
            self.status_message_time = 0
        
        self.status_win.clear()
        
        # Show status message if present
        if self.status_message:
            try:
                self.status_win.addstr(0, 0, self.status_message, curses.color_pair(self.status_color))
            except curses.error:
                # Handle case where message is too long
                pass
        else:
            # Show help text
            if self.mode == "browse":
                help_text = "q:quit | s:search | /:search | c:copy | ENTER:copy | ESC:clear search | l:lock"
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
        
        # With nodelay enabled, getch() returns -1 if no input available
        if ch == -1:
            return  # No input available, nothing to do
        
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
        
        elif ch == ord('l'):  # Lock vault
            self.logger.debug("Locking vault via UI command")
            if self.bw_cli.lock():
                self.logger.debug("Vault locked successfully")
                self.status_message = "Vault locked successfully - exiting"
                self.status_color = 2  # Green
                self.status_message_time = time.time()
                # Exit after successful lock
                raise KeyboardInterrupt
            else:
                self.logger.error("Failed to lock vault")
                self.status_message = "Failed to lock vault"
                self.status_color = 3  # Red
                self.status_message_time = time.time()
        
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
            if self.clipboard.copy_to_clipboard(password):
                self._show_status("Password copied for: %s" % item.get('name', 'Unknown'))
            else:
                self.logger.error("Failed to copy to clipboard using any method")
                self._show_status("Failed to copy password to clipboard", error=True)
        else:
            self._show_status("No password found for this item", error=True)