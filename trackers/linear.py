# trackers/linear.py
from __future__ import annotations
from datetime import datetime
import requests
from timeutil import parse_ts
from trackers.base import Card, filter_me

GQL_URL = "https://api.linear.app/graphql"

_QUERY = """
query($team: ID!, $cursor: String) {
  team(id: $team) {
    issues(first: 100, after: $cursor,
           filter: { state: { type: { eq: "completed" } } }) {
      pageInfo { hasNextPage endCursor }
      nodes {
        identifier title completedAt
        state { type }
        assignee { email }
        creator { email }
      }
    }
  }
}
"""

def parse_issues(nodes: list[dict], since: datetime, until: datetime,
                 me: str | None) -> list[Card]:
    cards: list[Card] = []
    for n in nodes:
        if (n.get("state") or {}).get("type") != "completed":
            continue
        if not n.get("completedAt"):
            continue
        ts = parse_ts(n["completedAt"])
        if not (since <= ts <= until):
            continue
        author = (n.get("assignee") or {}).get("email") or (n.get("creator") or {}).get("email")
        cards.append(Card(id=n.get("identifier", n.get("title", "")),
                          title=n.get("title", ""), completed_at=ts, author=author))
    return filter_me(cards, me)

def fetch_issues(token: str, team_id: str) -> list[dict]:
    nodes: list[dict] = []
    cursor = None
    headers = {"Authorization": token}  # Linear uses the raw key, no "Bearer "
    while True:
        resp = requests.post(GQL_URL, headers=headers,
                             json={"query": _QUERY, "variables": {"team": team_id, "cursor": cursor}})
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            raise RuntimeError(f"Linear GraphQL error: {data['errors']}")
        issues = data["data"]["team"]["issues"]
        nodes.extend(issues["nodes"])
        if not issues["pageInfo"]["hasNextPage"]:
            return nodes
        cursor = issues["pageInfo"]["endCursor"]

class LinearTracker:
    def __init__(self, token: str, team_id: str, me: str | None):
        self._token = token
        self._team = team_id
        self._me = me

    def list_completed_cards(self, since: datetime, until: datetime) -> list[Card]:
        nodes = fetch_issues(self._token, self._team)
        return parse_issues(nodes, since, until, self._me)
