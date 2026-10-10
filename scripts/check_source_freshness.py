import argparse
import csv
import json
from datetime import UTC, datetime
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from regularag.ingestion.manifest import load_manifest

PORTAL = "https://portal.uit.edu.vn"


def canonical_url(value: str) -> str:
    parsed = urlsplit(urljoin(PORTAL, value))
    if parsed.scheme != "https" or parsed.netloc != "portal.uit.edu.vn":
        raise ValueError("Source freshness checker only reads the official UIT portal")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


class PortalLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.groups = []
        self.stack = []
        self.links = set()
        self.anchor = None

    def handle_starttag(self, tag, attrs):
        if tag == "li":
            self.stack.append([])
        if tag == "a":
            href = dict(attrs).get("href", "")
            if href.startswith("/media/") and "/file_id" in href:
                self.anchor = {"url": canonical_url(href), "label": ""}
                self.links.add(self.anchor["url"])

    def handle_data(self, data):
        if self.anchor is not None:
            self.anchor["label"] += data

    def handle_endtag(self, tag):
        if tag == "a" and self.anchor is not None:
            for group in self.stack:
                group.append({**self.anchor, "label": " ".join(self.anchor["label"].split())})
            self.anchor = None
        if tag == "li" and self.stack:
            group = self.stack.pop()
            if group:
                self.groups.append(group)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recheck public portal attachment groups and hashes without republishing PDFs."
    )
    parser.add_argument("--manifest", type=Path, default=Path("data/manifests/documents.csv"))
    parser.add_argument(
        "--summary", type=Path, default=Path("data/manifests/source_freshness_checks.csv")
    )
    args = parser.parse_args()
    documents = load_manifest(args.manifest)
    pages = {}
    for url in sorted({document["index_url"] for document in documents.values()}):
        request = Request(url, headers={"User-Agent": "RegulaRAG-source-check/1.0"})
        with urlopen(request, timeout=60) as response:
            content = response.read()
        page = PortalLinks()
        page.feed(content.decode("utf-8"))
        if not page.links:
            raise ValueError("Portal markup changed; no document attachments were found")
        pages[url] = (page, sha256(content).hexdigest())
    rows = []
    for document in documents.values():
        url = canonical_url(document["source_url"])
        page, page_hash = pages[document["index_url"]]
        groups = [group for group in page.groups if any(link["url"] == url for link in group)]
        group = max(groups, key=len) if groups else []
        digest = sha256()
        request = Request(url, headers={"User-Agent": "RegulaRAG-source-check/1.0"})
        with urlopen(request, timeout=60) as response:
            while block := response.read(65536):
                digest.update(block)
        remote_hash = digest.hexdigest()
        row = {
            "document_id": document["document_id"],
            "source_sha256": document["sha256"],
            "checked_at": datetime.now(UTC).isoformat(),
            "check_status": (
                "not_listed"
                if url not in page.links
                else "unchanged"
                if remote_hash == document["sha256"]
                else "source_changed"
            ),
            "remote_sha256": remote_hash,
            "index_url": document["index_url"],
            "index_sha256": page_hash,
            "portal_group_attachments_json": json.dumps(group, ensure_ascii=False),
        }
        rows.append(row)
        print(json.dumps({key: row[key] for key in ("document_id", "check_status")}), flush=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    with args.summary.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    if any(row["check_status"] != "unchanged" for row in rows):
        raise SystemExit("Source drift detected; review required before selecting a new version")
    print(
        "All registered source bytes remain unchanged and listed; groups need manual date review."
    )


if __name__ == "__main__":
    main()
