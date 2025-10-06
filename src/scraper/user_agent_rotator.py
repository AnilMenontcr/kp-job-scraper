"""
User Agent Rotator Module
~~~~~~~~~~~~~~~~~~~~~~~~~~

Rotates browser user agents to avoid detection.
"""

import random
from typing import List


class UserAgentRotator:
    """Rotates user agents for HTTP requests."""

    # Realistic user agents from major browsers
    DEFAULT_USER_AGENTS = [
        # Chrome on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        # Chrome on Mac
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        # Firefox on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
        # Firefox on Mac
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/119.0",
        # Safari on Mac
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        # Edge on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        # Chrome on Linux
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]

    def __init__(self, user_agents: List[str] = None):
        """
        Initialize user agent rotator.

        Args:
            user_agents: Custom list of user agents (uses defaults if None)
        """
        self.user_agents = user_agents or self.DEFAULT_USER_AGENTS
        self.current_index = 0

        if not self.user_agents:
            raise ValueError("User agent list cannot be empty")

    def get_next(self) -> str:
        """
        Get next user agent in rotation.

        Returns:
            User agent string
        """
        user_agent = self.user_agents[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.user_agents)
        return user_agent

    def get_random(self) -> str:
        """
        Get random user agent.

        Returns:
            Random user agent string
        """
        return random.choice(self.user_agents)

    def add_user_agent(self, user_agent: str) -> None:
        """
        Add a new user agent to the pool.

        Args:
            user_agent: User agent string to add
        """
        if user_agent and user_agent not in self.user_agents:
            self.user_agents.append(user_agent)

    def __len__(self) -> int:
        """Return number of user agents in pool."""
        return len(self.user_agents)

    def __repr__(self) -> str:
        """String representation."""
        return f"UserAgentRotator(count={len(self.user_agents)})"
