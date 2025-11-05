"""
Bitwarden CLI wrapper for bw-tui.

This module provides a Python interface to the Bitwarden CLI,
handling authentication, vault operations, and data parsing.
"""

import json
import subprocess
import shutil
import logging
import os
import time
from typing import List, Dict, Any, Optional, Tuple


class BitwardenCLI:
    """Wrapper for Bitwarden CLI operations."""
    
    SESSION_FILE = os.path.expanduser("~/.bw-tui-session.json")
    SESSION_TIMEOUT = 10 * 60  # 10 minutes in seconds
    
    def __init__(self):
        """Initialize the Bitwarden CLI wrapper."""
        self.logger = logging.getLogger(__name__)
        self.bw_path = self._find_bw_path()
        self._session_key: Optional[str] = None
        self._load_session()
    
    def _find_bw_path(self) -> str:
        """Find the path to the bw command.
        
        Returns:
            Path to bw command, or 'bw' if not found in specific locations
        """
        # Common locations for bw when installed via npm
        common_paths = [
            "/Users/orangemax/.nvm/versions/node/v23.6.0/bin/bw",
            "/usr/local/bin/bw",
            "/opt/homebrew/bin/bw"
        ]
        
        # First try shutil.which
        bw_path = shutil.which("bw")
        if bw_path:
            return bw_path
        
        # Then try common paths
        for path in common_paths:
            if os.path.exists(path):
                return path
        
        # Fallback to 'bw' and hope it's in PATH
        return "bw"
    
    def _load_session(self) -> None:
        """Load session from file if it exists and is valid."""
        try:
            if os.path.exists(self.SESSION_FILE):
                with open(self.SESSION_FILE, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                
                session_key = session_data.get('session_key')
                timestamp = session_data.get('timestamp', 0)
                
                # Check if session is still valid (less than 10 minutes old)
                current_time = time.time()
                if current_time - timestamp < self.SESSION_TIMEOUT and session_key:
                    self._session_key = session_key
                    self.logger.debug("Loaded valid session from file")
                else:
                    self.logger.debug("Session expired or invalid, will require login")
                    self._cleanup_session_file()
            else:
                self.logger.debug("No session file found")
        except (json.JSONDecodeError, KeyError, OSError) as e:
            self.logger.warning("Failed to load session file: %s", e)
            self._cleanup_session_file()
    
    def _save_session(self, session_key: str) -> None:
        """Save session to file."""
        try:
            session_data = {
                'session_key': session_key,
                'timestamp': time.time()
            }
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.SESSION_FILE), exist_ok=True)
            
            with open(self.SESSION_FILE, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2)
            
            self._session_key = session_key
            self.logger.debug("Session saved to file")
        except OSError as e:
            self.logger.warning("Failed to save session file: %s", e)
    
    def _cleanup_session_file(self) -> None:
        """Remove the session file."""
        try:
            if os.path.exists(self.SESSION_FILE):
                os.remove(self.SESSION_FILE)
                self.logger.debug("Session file cleaned up")
        except OSError as e:
            self.logger.warning("Failed to cleanup session file: %s", e)
    
    def get_session_key(self) -> Optional[str]:
        """Get the current valid session key."""
        return self._session_key
    
    def clear_session(self) -> None:
        """Clear the current session."""
        self._session_key = None
        self._cleanup_session_file()
    
    def lock_vault(self) -> bool:
        """Lock the vault and clear the session.
        
        Returns:
            True if successfully locked, False otherwise
        """
        try:
            # Try to lock the vault using the CLI
            result = subprocess.run(
                [self.bw_path, "lock"],
                capture_output=True,
                text=True,
                check=True,
                env=os.environ.copy()
            )
            self.logger.debug("Vault locked successfully")
            
            # Clear our stored session
            self.clear_session()
            
            return True
        except subprocess.CalledProcessError as e:
            self.logger.warning("Failed to lock vault via CLI: %s", e)
            # Even if CLI lock fails, clear our session
            self.clear_session()
            return True  # Still consider it successful since we cleared our session
        except Exception as e:
            self.logger.error("Error locking vault: %s", e)
            # Clear session anyway
            self.clear_session()
            return False
    
    def check_cli_available(self) -> bool:
        """Check if the Bitwarden CLI is available.
        
        Returns:
            True if the CLI is available, False otherwise
        """
        return os.path.exists(self.bw_path) if self.bw_path != "bw" else shutil.which("bw") is not None
    
    def is_logged_in(self) -> bool:
        """Check if the user is logged in to Bitwarden.
        
        Returns:
            True if logged in, False otherwise
        """
        try:
            self.logger.debug(f"Checking login status with command: {self.bw_path} status")
            result = subprocess.run(
                [self.bw_path, "status"],
                capture_output=True,
                text=True,
                check=True,
                env=os.environ.copy()  # Use full environment
            )
            status_data = json.loads(result.stdout)
            status = status_data.get("status")
            self.logger.debug(f"Login status: {status}")
            logged_in = status in ["unlocked", "locked"]
            self.logger.debug(f"Is logged in: {logged_in}")
            return logged_in
        except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as e:
            self.logger.error(f"Error checking login status: {e}")
            return False
    
    def is_unlocked(self) -> bool:
        """Check if the vault is unlocked.
        
        Returns:
            True if unlocked, False otherwise
        """
        # First check if we have a valid saved session
        if self._session_key:
            self.logger.debug("Using saved session key for unlock check")
            return True
        
        # Fall back to checking CLI status
        try:
            self.logger.debug("Checking unlock status with command: %s status", self.bw_path)
            result = subprocess.run(
                [self.bw_path, "status"],
                capture_output=True,
                text=True,
                check=True,
                env=os.environ.copy()  # Use full environment
            )
            status_data = json.loads(result.stdout)
            status = status_data.get("status")
            self.logger.debug("Vault status: %s", status)
            unlocked = status == "unlocked"
            self.logger.debug("Is unlocked: %s", unlocked)
            return unlocked
        except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as e:
            self.logger.error("Error checking unlock status: %s", e)
            return False
    
    def unlock(self, password: str) -> Optional[str]:
        """Unlock the vault with the master password.
        
        Args:
            password: The master password
            
        Returns:
            Session key if successful, None otherwise
        """
        try:
            self.logger.debug("Attempting to unlock vault with command: %s unlock", self.bw_path)
            result = subprocess.run(
                [self.bw_path, "unlock", password, "--raw"],
                capture_output=True,
                text=True,
                check=True,
                env=os.environ.copy()  # Use full environment
            )
            session_key = result.stdout.strip()
            self.logger.debug("Unlock successful, session key length: %d", len(session_key) if session_key else 0)
            
            # Save the session for future use
            if session_key:
                self._save_session(session_key)
            
            return session_key
        except subprocess.CalledProcessError as e:
            self.logger.error("Failed to unlock vault: %s", e)
            if e.stderr:
                self.logger.error("Error output: %s", e.stderr)
            return None
    
    def lock(self) -> bool:
        """Lock the vault.
        
        Returns:
            True if successfully locked, False otherwise
        """
        try:
            self.logger.debug("Locking vault")
            subprocess.run(
                [self.bw_path, "lock"],
                capture_output=True,
                text=True,
                check=True,
                env=os.environ.copy()  # Use full environment
            )
            self.logger.debug("Vault locked successfully")
            
            # Clear the session
            self.clear_session()
            
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error("Failed to lock vault: %s", e)
            if e.stderr:
                self.logger.error("Error output: %s", e.stderr)
            return False
    
    def sync(self, session_key: Optional[str] = None) -> bool:
        """Sync the vault with the server.
        
        Args:
            session_key: Optional session key for authentication
            
        Returns:
            True if sync was successful, False otherwise
        """
        try:
            cmd = [self.bw_path, "sync"]
            env = os.environ.copy()  # Copy current environment
            if session_key:
                env["BW_SESSION"] = session_key
            
            subprocess.run(cmd, env=env, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False
    
    def get_items(self, session_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all items from the vault.
        
        Args:
            session_key: Optional session key for authentication (uses stored session if None)
            
        Returns:
            List of vault items
        """
        try:
            cmd = [self.bw_path, "list", "items"]
            env = os.environ.copy()  # Copy current environment
            
            # Use provided session key or stored session key
            effective_session_key = session_key or self._session_key
            
            if effective_session_key:
                env["BW_SESSION"] = effective_session_key
                self.logger.debug("Getting items with session key (length: %d)", len(effective_session_key))
            else:
                self.logger.debug("Getting items without session key")
            
            self.logger.debug("Running command: %s", ' '.join(cmd))
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                check=True
            )
            
            items = json.loads(result.stdout)
            self.logger.debug("Successfully retrieved %d items from vault", len(items))
            
            # Log first few item names for debugging
            for i, item in enumerate(items[:3]):
                name = item.get("name", "Unknown")
                self.logger.debug("Item %d: %s", i+1, name)
            
            return items
        except subprocess.CalledProcessError as e:
            # If command fails, it might be because vault is locked
            self.logger.error("Failed to get items: %s", e)
            if hasattr(e, 'stderr') and e.stderr:
                self.logger.error("Error output: %s", e.stderr)
            if hasattr(e, 'stdout') and e.stdout:
                self.logger.debug("Command output: %s", e.stdout)
            return []
        except json.JSONDecodeError as e:
            self.logger.error("Failed to parse JSON response: %s", e)
            return []
    
    def search_items(self, query: str, session_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for items in the vault.
        
        Args:
            query: Search query
            session_key: Optional session key for authentication (uses stored session if None)
            
        Returns:
            List of matching vault items
        """
        try:
            cmd = [self.bw_path, "list", "items", "--search", query]
            env = os.environ.copy()  # Copy current environment
            
            # Use provided session key or stored session key
            effective_session_key = session_key or self._session_key
            
            if effective_session_key:
                env["BW_SESSION"] = effective_session_key
            
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                check=True
            )
            return json.loads(result.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            return []
    
    def get_item(self, item_id: str, session_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get a specific item by ID.
        
        Args:
            item_id: The item ID
            session_key: Optional session key for authentication (uses stored session if None)
            
        Returns:
            Item data if found, None otherwise
        """
        try:
            cmd = [self.bw_path, "get", "item", item_id]
            env = os.environ.copy()  # Copy current environment
            
            # Use provided session key or stored session key
            effective_session_key = session_key or self._session_key
            
            if effective_session_key:
                env["BW_SESSION"] = effective_session_key
            
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                check=True
            )
            return json.loads(result.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            return None