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
from typing import List, Dict, Any, Optional


class BitwardenCLI:
    """Wrapper for Bitwarden CLI operations."""
    
    def __init__(self):
        """Initialize the Bitwarden CLI wrapper."""
        self.logger = logging.getLogger(__name__)
        self.bw_path = self._find_bw_path()
    
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
        try:
            self.logger.debug(f"Checking unlock status with command: {self.bw_path} status")
            result = subprocess.run(
                [self.bw_path, "status"],
                capture_output=True,
                text=True,
                check=True,
                env=os.environ.copy()  # Use full environment
            )
            status_data = json.loads(result.stdout)
            status = status_data.get("status")
            self.logger.debug(f"Vault status: {status}")
            unlocked = status == "unlocked"
            self.logger.debug(f"Is unlocked: {unlocked}")
            return unlocked
        except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as e:
            self.logger.error(f"Error checking unlock status: {e}")
            return False
    
    def unlock(self, password: str) -> Optional[str]:
        """Unlock the vault with the master password.
        
        Args:
            password: The master password
            
        Returns:
            Session key if successful, None otherwise
        """
        try:
            self.logger.debug(f"Attempting to unlock vault with command: {self.bw_path} unlock")
            result = subprocess.run(
                [self.bw_path, "unlock", password, "--raw"],
                capture_output=True,
                text=True,
                check=True,
                env=os.environ.copy()  # Use full environment
            )
            session_key = result.stdout.strip()
            self.logger.debug(f"Unlock successful, session key length: {len(session_key) if session_key else 0}")
            return session_key
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to unlock vault: {e}")
            if e.stderr:
                self.logger.error(f"Error output: {e.stderr}")
            return None
    
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
            session_key: Optional session key for authentication
            
        Returns:
            List of vault items
        """
        try:
            cmd = [self.bw_path, "list", "items"]
            env = os.environ.copy()  # Copy current environment
            if session_key:
                env["BW_SESSION"] = session_key
                self.logger.debug(f"Getting items with session key (length: {len(session_key)})")
            else:
                self.logger.debug("Getting items without session key")
            
            self.logger.debug(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                check=True
            )
            
            items = json.loads(result.stdout)
            self.logger.debug(f"Successfully retrieved {len(items)} items from vault")
            
            # Log first few item names for debugging
            for i, item in enumerate(items[:3]):
                name = item.get("name", "Unknown")
                self.logger.debug(f"Item {i+1}: {name}")
            
            return items
        except subprocess.CalledProcessError as e:
            # If command fails, it might be because vault is locked
            self.logger.error(f"Failed to get items: {e}")
            if hasattr(e, 'stderr') and e.stderr:
                self.logger.error(f"Error output: {e.stderr}")
            if hasattr(e, 'stdout') and e.stdout:
                self.logger.debug(f"Command output: {e.stdout}")
            return []
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON response: {e}")
            return []
    
    def search_items(self, query: str, session_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for items in the vault.
        
        Args:
            query: Search query
            session_key: Optional session key for authentication
            
        Returns:
            List of matching vault items
        """
        try:
            cmd = [self.bw_path, "list", "items", "--search", query]
            env = os.environ.copy()  # Copy current environment
            if session_key:
                env["BW_SESSION"] = session_key
            
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
            session_key: Optional session key for authentication
            
        Returns:
            Item data if found, None otherwise
        """
        try:
            cmd = [self.bw_path, "get", "item", item_id]
            env = os.environ.copy()  # Copy current environment
            if session_key:
                env["BW_SESSION"] = session_key
            
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