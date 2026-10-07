"""Convert Chrome bookmark exports into safe, grouped resource captures."""

from collections.abc import Iterable
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import json
import re

from personal_os.domain.resources import ResourceCapture


SENSITIVE_QUERY_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "code",
    "credential",
    "key",
    "password",
    "secret",
    "session",
    "sessionid",
    "signature",
    "token",
}


def load_chrome_bookmarks(path: Path) -> tuple[ResourceCapture, ...]:
    """Read one local Chrome profile and retain folders as grouping evidence."""
    body = json.loads(path.read_text(encoding="utf-8"))
    captures: list[ResourceCapture] = []
    roots = body.get("roots", {})
    for root_name, root in roots.items():
        if not isinstance(root, dict) or root.get("type") != "folder":
            continue
        display_name = root.get("name") or root_name.replace("_", " ").title()
        captures.extend(_walk(root.get("children", ()), (display_name,)))
    return tuple(captures)


def _walk(nodes: Iterable[dict], folders: tuple[str, ...]) -> list[ResourceCapture]:
    captures: list[ResourceCapture] = []
    for node in nodes:
        node_type = node.get("type")
        if node_type == "folder":
            name = (node.get("name") or "Untitled folder").strip()
            captures.extend(_walk(node.get("children", ()), (*folders, name)))
            continue
        if node_type != "url":
            continue
        url = sanitize_bookmark_url(node.get("url") or "")
        if url is None:
            continue
        title = (node.get("name") or urlsplit(url).netloc).strip()
        resource_type, tags = classify_bookmark(title, url, folders)
        notes = f"Imported from Chrome folder: {' / '.join(folders)}."
        if url == "https://dsa.chaicode.com/roadmap":
            notes += " User identified this as the DSA roadmap they were following."
            tags = tuple(dict.fromkeys((*tags, "active", "dsa", "interview")))
        captures.append(
            ResourceCapture(
                title=title,
                resource_type=resource_type,
                url=url,
                notes=notes,
                tags=tags,
                source="browser_bookmark",
            )
        )
    return captures


def sanitize_bookmark_url(value: str) -> str | None:
    """Drop non-web bookmarks and query parameters that commonly carry secrets."""
    parts = urlsplit(value.strip())
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return None
    query = [
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if key.casefold() not in SENSITIVE_QUERY_KEYS
    ]
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query, doseq=True), "")
    )


def classify_bookmark(
    title: str,
    url: str,
    folders: tuple[str, ...] = (),
) -> tuple[str, tuple[str, ...]]:
    """Apply conservative, inspectable grouping instead of model-only taxonomy."""
    content_text = " ".join((title, url)).casefold()
    text = " ".join((content_text, *folders)).casefold()
    tags: list[str] = []
    groups = {
        "french": ("french", "français", "francais"),
        "dsa": ("dsa", "algorithm", "leetcode", "coding interview"),
        "jobs-career": (
            " job",
            "jobs ",
            "career",
            "hire",
            "recruit",
            "interview",
            "cold email",
        ),
        "kubernetes-devops": (
            "kubernetes",
            "k8s",
            "devops",
            "docker",
            "cloud",
            "linux lab",
        ),
        "rust-systems": ("rust", "xv6", "operating system", "lowlevel"),
        "distributed-backend": (
            "distributed system",
            "system design",
            "backend",
            "load balancer",
            "web works",
        ),
        "ai-agents": ("agentic", "ai agent", "agents-for", "langgraph"),
        "ai-inference": (
            "inference",
            "llm",
            "language model",
            "gpu",
            "kernel",
            "rag",
            "machine learning",
            "mlops",
        ),
        "databases": ("database", "postgres", "sql", "query engine", "indexing"),
        "security": ("security", "hacking", "offensive", "vuln"),
        "networks": ("network", "packet", "tcp", "http protocol"),
        "frontend": ("react", "browser engine", "typescript", "kotlin"),
        "projects": ("project-based", "build-your-own", "hands-on", "from scratch"),
    }
    for group, keywords in groups.items():
        if any(keyword in text for keyword in keywords):
            tags.append(group)

    host = urlsplit(url).netloc.casefold()
    if host.endswith("x.com") or host.endswith("twitter.com"):
        resource_type = "social_post"
    elif "youtube.com/playlist" in url or "playlist" in title.casefold():
        resource_type = "youtube_playlist"
    elif "youtube.com" in host or "youtu.be" in host:
        resource_type = "video"
    elif (
        "roadmap" in content_text
        or "learning track" in content_text
        or "learning map" in content_text
    ):
        resource_type = "roadmap"
    elif any(
        keyword in content_text
        for keyword in (
            "course",
            "curriculum",
            "training",
            "tutorial",
            "exercises to learn",
            "missing semester",
        )
    ):
        resource_type = "course"
    elif re.search(r"\bbook\b|\bbooks\b|reading list", content_text):
        resource_type = "book"
    elif urlsplit(url).path.casefold().endswith(".pdf"):
        resource_type = "paper"
    elif any(
        keyword in content_text for keyword in ("careers", "job board", "technical roles")
    ):
        resource_type = "target_job"
    else:
        resource_type = "bookmark"

    if not tags:
        tags.append("uncategorized")
    return resource_type, tuple(tags[:10])
