from __future__ import annotations

import httpx


class MondayClientError(RuntimeError):
    pass


class MondayClient:
    def __init__(self, token: str, api_url: str = "https://api.monday.com/v2"):
        if not token:
            raise ValueError("MONDAY_API_TOKEN is required")
        self.token = token
        self.api_url = api_url
        self.headers = {"Authorization": token, "Content-Type": "application/json", "API-Version": "2025-04"}

    def query(self, query: str, variables: dict | None = None) -> dict:
        payload = {"query": query, "variables": variables or {}}
        try:
            response = httpx.post(self.api_url, json=payload, headers=self.headers, timeout=60)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise MondayClientError(f"Monday API request failed: {exc}") from exc
        data = response.json()
        if data.get("errors"):
            raise MondayClientError(f"Monday API returned errors: {data['errors']}")
        return data.get("data", {})

    def test_connection(self) -> dict:
        return self.query("query { me { id name email } account { id name slug } }")

    def get_account(self) -> dict:
        return self.query("query { account { id name slug tier first_day_of_the_week } }").get("account", {})

    def get_workspaces(self) -> list[dict]:
        q = "query { workspaces { id name kind description state } }"
        return self.query(q).get("workspaces", [])

    def get_users(self) -> list[dict]:
        q = "query { users { id name email title enabled is_admin is_guest is_pending } }"
        return self.query(q).get("users", [])

    def get_boards(self, workspace_id: str | None = None) -> list[dict]:
        if workspace_id:
            q = "query($workspace_ids: [ID!]) { boards(workspace_ids: $workspace_ids, limit: 500) { id name description state board_kind workspace_id } }"
            return self.query(q, {"workspace_ids": [workspace_id]}).get("boards", [])
        q = "query { boards(limit: 500) { id name description state board_kind workspace_id } }"
        return self.query(q).get("boards", [])

    def get_board_schema(self, board_id: str) -> dict:
        q = """
        query($ids: [ID!]) {
          boards(ids: $ids) {
            id name description state board_kind workspace_id
            groups { id title }
            columns { id title type settings_str description }
          }
        }
        """
        boards = self.query(q, {"ids": [board_id]}).get("boards", [])
        return boards[0] if boards else {}

    def get_board_items_page(self, board_id: str, cursor: str | None = None, limit: int = 100) -> dict:
        limit = max(1, min(limit, 500))
        if cursor:
            q = "query($cursor: String!, $limit: Int!) { next_items_page(cursor: $cursor, limit: $limit) { cursor items { id name state group { id title } column_values { id text value type } subitems { id name } } } }"
            return self.query(q, {"cursor": cursor, "limit": limit}).get("next_items_page", {})
        q = "query($ids: [ID!], $limit: Int!) { boards(ids: $ids) { items_page(limit: $limit) { cursor items { id name state group { id title } column_values { id text value type } subitems { id name } } } } }"
        boards = self.query(q, {"ids": [board_id], "limit": limit}).get("boards", [])
        return boards[0].get("items_page", {}) if boards else {}

    def get_all_board_items(self, board_id: str, limit: int | None = None) -> list[dict]:
        items: list[dict] = []
        cursor = None
        page_limit = min(limit or 500, 500)
        while True:
            page = self.get_board_items_page(board_id, cursor=cursor, limit=page_limit)
            batch = page.get("items", [])
            items.extend(batch)
            if limit and len(items) >= limit:
                return items[:limit]
            cursor = page.get("cursor")
            if not cursor or not batch:
                return items
