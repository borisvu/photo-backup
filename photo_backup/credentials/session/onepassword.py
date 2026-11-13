"""
1Password session management for credential retrieval.
"""

import logging
import subprocess
import time

from ..exceptions import CredentialError


class OnePasswordSessionManager:
    """Manages 1Password CLI session tokens."""

    def __init__(self) -> None:
        """Initialize the 1Password session manager."""
        self.logger = logging.getLogger("photo_backup.credentials.onepassword.session")
        self._session_token: str | None = None
        self._session_expiry: float | None = None

    def get_session_token(self) -> str | None:
        """Get a valid 1Password session token.

        Returns:
            Session token or None if not available/expired
        """
        # Check if we have a valid cached session
        if self._is_session_valid():
            self.logger.debug("Using cached 1Password session token")
            return self._session_token

        # Get a new session token
        return self._authenticate_session()

    def _is_session_valid(self) -> bool:
        """Check if the current session token is valid.

        Returns:
            True if session is valid, False otherwise
        """
        if not self._session_token or not self._session_expiry:
            return False

        # Check if session has expired (with 5-minute buffer)
        if time.time() > (self._session_expiry - 300):
            self.logger.debug("1Password session token expired")
            return False

        return True

    def _authenticate_session(self) -> str | None:
        """Authenticate with 1Password and get a session token.

        Returns:
            Session token or None if authentication failed
        """
        try:
            self.logger.debug("Authenticating with 1Password")

            # Sign in to 1Password (this will prompt for authentication)
            result = subprocess.run(["op", "signin"], capture_output=True, text=True, timeout=60.0)

            if result.returncode != 0:
                error_msg = result.stderr.strip()
                self.logger.error(f"1Password signin failed: {error_msg}")

                # Provide specific suggestions based on error
                if "timeout" in error_msg.lower():
                    raise CredentialError(
                        "1Password authentication timed out", "Check network connectivity and try again", error_msg
                    )
                elif "not found" in error_msg.lower():
                    raise CredentialError(
                        "1Password CLI not found", "Install 1Password CLI and ensure 'op' command is in PATH", error_msg
                    )
                else:
                    raise CredentialError(
                        "1Password authentication failed", "Run 'op signin' manually to authenticate", error_msg
                    )

            # Extract session token from output
            # 1Password CLI typically outputs the session token on success
            lines = result.stdout.strip().split("\n")
            session_token = None

            for line in lines:
                if line.startswith("export OP_SESSION_"):
                    # Extract token from export command
                    parts = line.split("=")
                    if len(parts) == 2:
                        session_token = parts[1].strip().strip('"')
                        break

            if not session_token:
                raise CredentialError(
                    "Failed to extract session token from 1Password",
                    "Try running 'op signin' manually and check output format",
                    "No session token found in 1Password output",
                )

            # Set session expiry (30 minutes from now)
            self._session_token = session_token
            self._session_expiry = time.time() + 1800  # 30 minutes

            self.logger.debug("Successfully authenticated with 1Password")
            return session_token

        except CredentialError:
            # Re-raise credential errors as-is
            raise
        except subprocess.TimeoutExpired:
            raise CredentialError(
                "1Password authentication timed out",
                "Check network connectivity and try again",
                "Authentication exceeded 60-second timeout",
            ) from None
        except Exception as e:
            raise CredentialError(
                "Unexpected error during 1Password authentication",
                "Check 1Password CLI installation and try again",
                f"Error: {e}",
            ) from e

    def clear_session(self) -> None:
        """Clear the current session token."""
        self._session_token = None
        self._session_expiry = None
        self.logger.debug("Cleared 1Password session token")
