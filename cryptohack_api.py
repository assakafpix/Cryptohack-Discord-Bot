"""
CryptoHack API client module.
Handles fetching user data and challenges from CryptoHack.
"""

import aiohttp
from typing import Optional
from dataclasses import dataclass


CRYPTOHACK_API_BASE = "https://cryptohack.org/api"
CRYPTOHACK_USER_URL = "https://cryptohack.org/user/{username}/"


@dataclass
class SolvedChallenge:
    name: str
    category: str
    points: int
    solves: int
    date: str


@dataclass
class CryptoHackUser:
    username: str
    country: str
    score: int
    rank: int
    level: int
    first_bloods: int
    joined: str
    solved_challenges: list[SolvedChallenge]

    @property
    def profile_url(self) -> str:
        return CRYPTOHACK_USER_URL.format(username=self.username)


class CryptoHackAPIError(Exception):
    """Exception raised when API request fails."""
    pass


class UserNotFoundError(CryptoHackAPIError):
    """Exception raised when user is not found."""
    pass


async def fetch_user(username: str, session: Optional[aiohttp.ClientSession] = None) -> CryptoHackUser:
    """
    Fetch user data from CryptoHack API.

    Args:
        username: The CryptoHack username to fetch
        session: Optional aiohttp session to reuse

    Returns:
        CryptoHackUser object with user data

    Raises:
        UserNotFoundError: If the user doesn't exist
        CryptoHackAPIError: If the API request fails
    """
    url = f"{CRYPTOHACK_API_BASE}/user/{username}/"

    close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        close_session = True

    try:
        async with session.get(url) as response:
            if response.status != 200:
                raise CryptoHackAPIError(f"API returned status {response.status}")

            data = await response.json()

            # Check for error response
            if "code" in data and data.get("code") == 1001:
                raise UserNotFoundError(f"User '{username}' does not exist")

            if "username" not in data:
                raise CryptoHackAPIError("Invalid API response")

            # Parse solved challenges
            solved = []
            for challenge in data.get("solved_challenges", []):
                solved.append(SolvedChallenge(
                    name=challenge["name"],
                    category=challenge["category"],
                    points=challenge["points"],
                    solves=challenge["solves"],
                    date=challenge["date"]
                ))

            return CryptoHackUser(
                username=data["username"],
                country=data.get("country", ""),
                score=data.get("score", 0),
                rank=data.get("rank", 0),
                level=data.get("level", 0),
                first_bloods=data.get("first_bloods", 0),
                joined=data.get("joined", ""),
                solved_challenges=solved
            )

    except aiohttp.ClientError as e:
        raise CryptoHackAPIError(f"Failed to connect to CryptoHack API: {e}")
    finally:
        if close_session:
            await session.close()


async def search_user(term: str, session: Optional[aiohttp.ClientSession] = None) -> list[str]:
    """
    Search for users matching a term.

    Args:
        term: Search term
        session: Optional aiohttp session

    Returns:
        List of matching usernames
    """
    url = f"https://cryptohack.org/search_user/{term}.json"

    close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        close_session = True

    try:
        async with session.get(url) as response:
            if response.status != 200:
                return []
            data = await response.json()
            return data.get("users", [])
    except Exception:
        return []
    finally:
        if close_session:
            await session.close()
