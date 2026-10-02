"""Client for the Polar AccessLink API v3.

Docs: https://www.polar.com/accesslink-api/

Typical flow:
    client = PolarClient.from_env()
    url = client.authorization_url(state="...")      # 1. send the user here
    token = client.exchange_code(code)               # 2. on the redirect back
    client.register_user(token.access_token, member_id="user-42")  # once per user
    exercises = client.list_exercises(token.access_token)          # 3. read data

Tokens are not stored here; persist `access_token` and `user_id` yourself.
"""

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from xml.sax.saxutils import escape

import httpx

AUTH_URL = "https://flow.polar.com/oauth2/authorization"
TOKEN_URL = "https://polarremote.com/v2/oauth2/token"
API_BASE_URL = "https://www.polaraccesslink.com/v3"


class PolarError(Exception):
    """Raised when the Polar API returns an error status."""

    def __init__(self, status_code: int, message: str):
        super().__init__(f"Polar API error {status_code}: {message}")
        self.status_code = status_code


class PolarRateLimitError(PolarError):
    """HTTP 429: the 15 min or 24 h rate limit was exceeded."""


@dataclass
class PolarToken:
    access_token: str
    user_id: int  # Polar's x_user_id
    expires_in: int
    token_type: str = "bearer"


class PolarClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: Optional[str] = None,
        http: Optional[httpx.Client] = None,
        timeout: float = 15.0,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self._http = http or httpx.Client(timeout=timeout)

    @classmethod
    def from_env(cls) -> "PolarClient":
        """Build a client from POLAR_CLIENT_ID / _SECRET / _REDIRECT_URI."""
        try:
            return cls(
                client_id=os.environ["POLAR_CLIENT_ID"],
                client_secret=os.environ["POLAR_CLIENT_SECRET"],
                redirect_uri=os.environ.get("POLAR_REDIRECT_URI"),
            )
        except KeyError as exc:
            raise RuntimeError(f"Missing environment variable {exc.args[0]}") from exc

    def close(self) -> None:
        self._http.close()

    # --- OAuth2 -----------------------------------------------------------

    def authorization_url(self, state: Optional[str] = None) -> str:
        """URL to send the user to so they can grant access."""
        params = {"response_type": "code", "client_id": self.client_id}
        if self.redirect_uri:
            params["redirect_uri"] = self.redirect_uri
        if state:
            params["state"] = state
        return f"{AUTH_URL}?{urlencode(params)}"

    def exchange_code(self, code: str) -> PolarToken:
        """Trade the authorization code from the redirect for an access token."""
        data = {"grant_type": "authorization_code", "code": code}
        if self.redirect_uri:
            data["redirect_uri"] = self.redirect_uri
        response = self._http.post(
            TOKEN_URL,
            data=data,
            auth=(self.client_id, self.client_secret),
            headers={"Accept": "application/json;charset=UTF-8"},
        )
        body = self._check(response).json()
        return PolarToken(
            access_token=body["access_token"],
            user_id=int(body["x_user_id"]),
            expires_in=int(body.get("expires_in", 0)),
            token_type=body.get("token_type", "bearer"),
        )

    # --- Users ------------------------------------------------------------

    def register_user(self, access_token: str, member_id: str) -> Optional[Dict]:
        """Register the user with this client. Required once before data access.

        Returns the user object, or None if the user was already registered
        (HTTP 409).
        """
        xml = f"<register><member-id>{escape(member_id)}</member-id></register>"
        response = self._http.post(
            f"{API_BASE_URL}/users",
            content=xml,
            headers={
                **self._bearer(access_token),
                "Content-Type": "application/xml",
                "Accept": "application/json",
            },
        )
        if response.status_code == 409:
            return None
        return self._check(response).json()

    def get_user(self, access_token: str, user_id: int) -> Dict:
        return self._get_json(f"/users/{user_id}", access_token)

    def delete_user(self, access_token: str, user_id: int) -> None:
        """Remove the user's link to this client (revokes access)."""
        response = self._http.delete(
            f"{API_BASE_URL}/users/{user_id}", headers=self._bearer(access_token)
        )
        self._check(response)

    def get_physical_info(self, access_token: str) -> Dict:
        return self._get_json("/users/physical-info", access_token)

    # --- Exercises (training sessions, last 30 days in Flow) --------------

    def list_exercises(
        self,
        access_token: str,
        samples: bool = False,
        zones: bool = False,
        route: bool = False,
    ) -> List[Dict]:
        params = self._flags(samples=samples, zones=zones, route=route)
        return self._get_json("/exercises", access_token, params)

    def get_exercise(
        self,
        access_token: str,
        exercise_id: str,
        samples: bool = False,
        zones: bool = False,
        route: bool = False,
    ) -> Dict:
        params = self._flags(samples=samples, zones=zones, route=route)
        return self._get_json(f"/exercises/{exercise_id}", access_token, params)

    def get_exercise_fit(self, access_token: str, exercise_id: str) -> bytes:
        return self._get_raw(f"/exercises/{exercise_id}/fit", access_token, "*/*")

    def get_exercise_tcx(self, access_token: str, exercise_id: str) -> bytes:
        return self._get_raw(
            f"/exercises/{exercise_id}/tcx",
            access_token,
            "application/vnd.garmin.tcx+xml",
        )

    def get_exercise_gpx(self, access_token: str, exercise_id: str) -> bytes:
        return self._get_raw(
            f"/exercises/{exercise_id}/gpx", access_token, "application/gpx+xml"
        )

    # --- Daily activity, sleep, cardio load -------------------------------

    def list_activities(
        self,
        access_token: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        steps: bool = False,
        activity_zones: bool = False,
    ) -> List[Dict]:
        """Dates are YYYY-MM-DD. Defaults to the last 28 days (also the max range)."""
        params = self._flags(steps=steps, activity_zones=activity_zones)
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        return self._get_json("/users/activities", access_token, params)

    def get_activity(self, access_token: str, date: str) -> Dict:
        return self._get_json(f"/users/activities/{date}", access_token)

    def list_sleep(self, access_token: str) -> Dict:
        return self._get_json("/users/sleep", access_token)

    def get_sleep(self, access_token: str, date: str) -> Dict:
        return self._get_json(f"/users/sleep/{date}", access_token)

    def list_nightly_recharge(self, access_token: str) -> Dict:
        """Recovery data (ANS charge, HRV, breathing rate) for the last 28 days."""
        return self._get_json("/users/nightly-recharge", access_token)

    def get_nightly_recharge(self, access_token: str, date: str) -> Dict:
        return self._get_json(f"/users/nightly-recharge/{date}", access_token)

    def list_cardio_load(self, access_token: str) -> List[Dict]:
        return self._get_json("/users/cardio-load", access_token)

    # --- internals --------------------------------------------------------

    @staticmethod
    def _bearer(access_token: str) -> Dict[str, str]:
        return {"Authorization": f"Bearer {access_token}"}

    @staticmethod
    def _flags(**flags: bool) -> Dict[str, str]:
        return {name: "true" for name, enabled in flags.items() if enabled}

    def _get_json(
        self, path: str, access_token: str, params: Optional[Dict[str, Any]] = None
    ) -> Any:
        response = self._http.get(
            f"{API_BASE_URL}{path}",
            params=params,
            headers={**self._bearer(access_token), "Accept": "application/json"},
        )
        if response.status_code == 204:
            return []
        return self._check(response).json()

    def _get_raw(self, path: str, access_token: str, accept: str) -> bytes:
        response = self._http.get(
            f"{API_BASE_URL}{path}",
            headers={**self._bearer(access_token), "Accept": accept},
        )
        return self._check(response).content

    @staticmethod
    def _check(response: httpx.Response) -> httpx.Response:
        if response.is_success:
            return response
        if response.status_code == 429:
            raise PolarRateLimitError(429, "rate limit exceeded")
        raise PolarError(response.status_code, response.text[:300])
