# trackers/github_projects.py
from __future__ import annotations
import os
from datetime import datetime
import requests
from timeutil import parse_ts
from trackers.base import Card, filter_me

GQL_URL = "https://api.github.com/graphql"

_QUERY = """
query($project: ID!, $cursor: String) {
  node(id: $project) {
    ... on ProjectV2 {
      items(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          fieldValueByName(name: "Status") {
            ... on ProjectV2ItemFieldSingleSelectValue { name }
          }
          content {
            __typename
            ... on Issue {
              title number closed closedAt
              timelineItems(first: 1, itemTypes: CLOSED_EVENT) {
                nodes { ... on ClosedEvent { createdAt actor { login } } }
              }
            }
            ... on PullRequest {
              title number merged mergedAt closedAt mergedBy { login }
            }
          }
        }
      }
    }
  }
}
"""

def _status_name(node: dict) -> str | None:
    fv = node.get("fieldValueByName") or {}
    return fv.get("name")

def _completion(content: dict) -> tuple[datetime | None, str | None]:
    """(earliest completion ts, author) or (None, None) if not completed."""
    candidates: list[tuple[datetime, str | None]] = []
    if content.get("__typename") == "PullRequest" and content.get("merged"):
        if content.get("mergedAt"):
            login = (content.get("mergedBy") or {}).get("login")
            candidates.append((parse_ts(content["mergedAt"]), login))
    if content.get("__typename") == "Issue" and content.get("closed"):
        tl = (content.get("timelineItems") or {}).get("nodes") or []
        if tl and tl[0].get("createdAt"):
            login = (tl[0].get("actor") or {}).get("login")
            candidates.append((parse_ts(tl[0]["createdAt"]), login))
        elif content.get("closedAt"):
            candidates.append((parse_ts(content["closedAt"]), None))
    if not candidates:
        return None, None
    return min(candidates, key=lambda t: t[0])

def parse_items(nodes: list[dict], done_status: list[str], since: datetime,
                until: datetime, me: str | None) -> list[Card]:
    cards: list[Card] = []
    done_set = set(done_status)
    for node in nodes:
        content = node.get("content")
        if not content:
            continue
        status = _status_name(node)
        ts, author = _completion(content)
        is_done = (status in done_set) or (ts is not None)
        if not is_done or ts is None:
            continue
        if not (since <= ts <= until):
            continue
        cards.append(Card(id=str(content.get("number", content.get("title"))),
                          title=content.get("title", ""),
                          completed_at=ts, author=author))
    return filter_me(cards, me)

def fetch_items(token: str, project_node_id: str) -> list[dict]:
    nodes: list[dict] = []
    cursor = None
    headers = {"Authorization": f"Bearer {token}"}
    while True:
        resp = requests.post(GQL_URL, headers=headers,
                             json={"query": _QUERY,
                                   "variables": {"project": project_node_id, "cursor": cursor}})
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            raise RuntimeError(f"GitHub GraphQL error: {data['errors']}")
        items = data["data"]["node"]["items"]
        nodes.extend(items["nodes"])
        if not items["pageInfo"]["hasNextPage"]:
            return nodes
        cursor = items["pageInfo"]["endCursor"]

class GitHubProjectsTracker:
    def __init__(self, token: str, project_node_id: str, done_status: list[str], me: str | None):
        self._token = token
        self._project = project_node_id
        self._done = done_status
        self._me = me

    def list_completed_cards(self, since: datetime, until: datetime) -> list[Card]:
        nodes = fetch_items(self._token, self._project)
        return parse_items(nodes, self._done, since, until, self._me)
