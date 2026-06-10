"""
Splitwise integration via the raw REST API.

For personal use you do NOT need OAuth. Register an app at
https://secure.splitwise.com/apps -> "Register your application" ->
scroll to "API keys" -> generate one. That key is a Bearer token that
acts on YOUR account. Put it in .env as SPLITWISE_API_KEY.

Base URL: https://secure.splitwise.com/api/v3.0
Auth:     Authorization: Bearer <api_key>
"""

import os
import requests

BASE = "https://secure.splitwise.com/api/v3.0"


class Splitwise:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ["SPLITWISE_API_KEY"]
        self.headers = {"Authorization": f"Bearer {self.api_key}"}

    def _get(self, path: str, **params):
        r = requests.get(f"{BASE}/{path}", headers=self.headers, params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    def current_user(self) -> dict:
        return self._get("get_current_user")["user"]

    def groups(self) -> list[dict]:
        """Each group has id, name, and members [{id, first_name, last_name}]."""
        return self._get("get_groups")["groups"]

    def members(self, group_id: int) -> list[dict]:
        """Flat list of {id, name} for a group. Used to map voice-note names -> Splitwise IDs."""
        g = self._get("get_group", id=group_id)["group"]
        out = []
        for m in g["members"]:
            name = m.get("first_name") or ""
            if m.get("last_name"):
                name += f" {m['last_name']}"
            out.append({"id": m["id"], "name": name.strip()})
        return out

    def create_expense(
        self,
        *,
        group_id: int,
        description: str,
        cost: float,
        shares: list[dict],  # [{"user_id": int, "paid": float, "owed": float}, ...]
        currency: str = "INR",
    ) -> dict:
        """
        The itemized-split format is the part people get wrong. Splitwise wants
        a FLAT form body with indexed keys users__N__<field>, NOT nested JSON:

            cost                 = "1000.00"          (total, as a string)
            users__0__user_id    = 111
            users__0__paid_share = "1000.00"          (who fronted the money)
            users__0__owed_share = "400.00"           (that person's real share)
            users__1__user_id    = 222
            users__1__paid_share = "0.00"
            users__1__owed_share = "600.00"

        Hard rule: sum(paid_share) == cost AND sum(owed_share) == cost, to the cent,
        or the API silently returns errors and creates nothing.
        """
        payload = {
            "group_id": group_id,
            "description": description,
            "cost": f"{cost:.2f}",
            "currency_code": currency,
        }
        for i, s in enumerate(shares):
            payload[f"users__{i}__user_id"] = s["user_id"]
            payload[f"users__{i}__paid_share"] = f"{s['paid']:.2f}"
            payload[f"users__{i}__owed_share"] = f"{s['owed']:.2f}"

        r = requests.post(f"{BASE}/create_expense", headers=self.headers, data=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        # Splitwise returns 200 even on validation failure; errors live in the body.
        if data.get("errors"):
            raise RuntimeError(f"Splitwise rejected the expense: {data['errors']}")
        return data["expenses"][0]
