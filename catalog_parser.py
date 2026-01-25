#!/usr/bin/env python3
"""Crawl a product catalog and emit structured data for chatbot training."""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import deque
from dataclasses import dataclass, asdict
from typing import Iterable, Iterator, Optional
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup, Tag


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/119.0 Safari/537.36"
    )
}


def normalize_whitespace(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"\s+", " ", value).strip() or None


def strip_tracking(url: str) -> str:
    url, _frag = urldefrag(url)
    parsed = urlparse(url)
    query = parsed.query
    # Remove common marketing parameters to dedupe URLs.
    if not query:
        return url
    pairs = [p for p in query.split("&") if p and not p.lower().startswith("utm_")]
    sanitized = parsed._replace(query="&".join(pairs)).geturl()
    return sanitized


def load_json_candidates(nodes: Iterable[Tag]) -> Iterator[dict]:
    for node in nodes:
        text = node.string
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            yield payload
        elif isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict):
                    yield item


def gather_meta_content(soup: BeautifulSoup, *keys: str) -> Optional[str]:
    lower = {k.lower() for k in keys}
    for tag in soup.find_all("meta"):
        name = (tag.get("name") or tag.get("property") or tag.get("itemprop") or "").lower()
        if name in lower:
            value = tag.get("content")
            if value:
                return normalize_whitespace(value)
    return None


def find_table_sizes(soup: BeautifulSoup) -> list[str]:
    sizes: list[str] = []
    for table in soup.find_all("table"):
        text = table.get_text(" ", strip=True).lower()
        if "size" not in text:
            continue
        rows = []
        for row in table.find_all("tr"):
            cells = [normalize_whitespace(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"])]
            cells = [c for c in cells if c]
            if cells:
                rows.append(" | ".join(cells))
        if rows:
            sizes.extend(rows)
    return sizes


def find_option_sizes(soup: BeautifulSoup) -> list[str]:
    sizes: list[str] = []
    for select in soup.find_all("select"):
        haystack = " ".join(
            filter(
                None,
                [
                    select.get("name"),
                    select.get("id"),
                    select.get("data-option"),
                    select.get("aria-label"),
                ],
            )
        ).lower()
        if "size" not in haystack:
            continue
        for option in select.find_all("option"):
            if option.get("disabled"):
                continue
            text = normalize_whitespace(option.get_text())
            if text:
                sizes.append(text)
    button_candidates = soup.select("[data-option-name], [data-option], button, label")
    for node in button_candidates:
        class_attr = node.get("class")
        if isinstance(class_attr, (list, tuple)):
            class_text = " ".join(class_attr)
        else:
            class_text = class_attr or ""
        attrs = " ".join(
            filter(
                None,
                [
                    node.get("data-option-name"),
                    node.get("data-option"),
                    node.get("aria-label"),
                    class_text,
                ],
            )
        ).lower()
        if "size" not in attrs:
            continue
        text = normalize_whitespace(node.get_text())
        if text:
            sizes.append(text)
    return list(dict.fromkeys(sizes))


def extract_images(soup: BeautifulSoup) -> list[str]:
    urls: list[str] = []
    for img in soup.find_all("img"):
        src = img.get("data-src") or img.get("data-zoom-image") or img.get("src")
        if not src:
            continue
        src = src.strip()
        if src and src.lower().startswith("http"):
            urls.append(src)
    return list(dict.fromkeys(urls))


@dataclass
class ProductRecord:
    title: Optional[str]
    sku: Optional[str]
    price: Optional[str]
    description: Optional[str]
    sizes: list[str]
    url: str
    images: list[str]
    breadcrumbs: list[str]
    source_links: list[str]


class CatalogParser:
    def __init__(
        self,
        base_url: str,
        *,
        product_keywords: Optional[list[str]] = None,
        max_pages: int = 200,
        max_products: int = 80,
        delay: float = 0.0,
        headers: Optional[dict] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.domain = urlparse(self.base_url).netloc
        self.product_keywords = [k.lower() for k in (product_keywords or ["product", "shop", "item"])]
        self.max_pages = max_pages
        self.max_products = max_products
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update(headers or DEFAULT_HEADERS)
        self.crawled_pages: list[str] = []

    def crawl(self) -> list[ProductRecord]:
        queue: deque[str] = deque([self.base_url])
        visited: set[str] = set()
        products: list[ProductRecord] = []
        while queue and len(visited) < self.max_pages and len(products) < self.max_products:
            current = queue.popleft()
            normalized = self._normalize_url(current)
            if not normalized or normalized in visited:
                continue
            visited.add(normalized)
            try:
                response = self.session.get(normalized, timeout=30)
            except requests.RequestException:
                continue
            if not response.headers.get("content-type", "").startswith("text"):
                continue
            soup = BeautifulSoup(response.text, "html.parser")
            self.crawled_pages.append(normalized)
            if self._looks_like_product(normalized, soup):
                record = self._parse_product(normalized, soup)
                if record:
                    products.append(record)
            for link in soup.find_all("a", href=True):
                absolute = urljoin(normalized, link["href"])
                cleaned = self._normalize_url(absolute)
                if not cleaned:
                    continue
                if cleaned in visited or cleaned in queue:
                    continue
                if urlparse(cleaned).netloc != self.domain:
                    continue
                queue.append(cleaned)
            if self.delay:
                time.sleep(self.delay)
        return products

    def _normalize_url(self, url: str) -> Optional[str]:
        if not url:
            return None
        url = strip_tracking(url)
        parsed = urlparse(url)
        if not parsed.scheme:
            url = urljoin(self.base_url, url)
            parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return None
        if not parsed.netloc:
            return None
        return url.rstrip("/")

    def _looks_like_product(self, url: str, soup: BeautifulSoup) -> bool:
        lower_url = url.lower()
        if any(keyword in lower_url for keyword in self.product_keywords):
            return True
        json_ld = list(load_json_candidates(soup.find_all("script", attrs={"type": "application/ld+json"})))
        for block in json_ld:
            if block.get("@type") == "Product" or (
                isinstance(block.get("@type"), list) and "Product" in block.get("@type")
            ):
                return True
        if soup.find(attrs={"itemtype": re.compile("Product", re.I)}):
            return True
        return False

    def _parse_product(self, url: str, soup: BeautifulSoup) -> Optional[ProductRecord]:
        title = gather_meta_content(soup, "og:title", "twitter:title")
        if not title:
            heading = soup.find(["h1", "h2"], string=True)
            title = normalize_whitespace(heading.get_text() if heading else None)
        description = gather_meta_content(soup, "description", "og:description")
        sku = gather_meta_content(soup, "sku", "product:sku")
        price = gather_meta_content(soup, "price", "product:price:amount", "og:price:amount")
        json_ld_blocks = list(load_json_candidates(soup.find_all("script", attrs={"type": "application/ld+json"})))
        for block in json_ld_blocks:
            if block.get("@type") == "Product" or (
                isinstance(block.get("@type"), list) and "Product" in block.get("@type")
            ):
                title = title or normalize_whitespace(block.get("name"))
                description = description or normalize_whitespace(block.get("description"))
                sku = sku or normalize_whitespace(block.get("sku"))
                offers = block.get("offers")
                if isinstance(offers, dict):
                    price = price or normalize_whitespace(str(offers.get("price")))
                break
        if not title:
            return None
        sizes = find_option_sizes(soup)
        if not sizes:
            sizes = find_table_sizes(soup)
        breadcrumbs = []
        breadcrumb_container = soup.find(attrs={"aria-label": re.compile("crumb", re.I)}) or soup.select_one("nav.breadcrumb, ol.breadcrumb")
        if breadcrumb_container:
            for item in breadcrumb_container.find_all(["a", "span"]):
                text = normalize_whitespace(item.get_text())
                if text:
                    breadcrumbs.append(text)
        images = extract_images(soup)
        page_links = []
        for link in soup.find_all("a", href=True):
            absolute = urljoin(url, link["href"])
            cleaned = self._normalize_url(absolute)
            if not cleaned:
                continue
            text = normalize_whitespace(link.get_text()) or ""
            page_links.append(f"{text} -> {cleaned}")
        return ProductRecord(
            title=title,
            sku=sku,
            price=price,
            description=description,
            sizes=sizes,
            url=url,
            images=images,
            breadcrumbs=breadcrumbs,
            source_links=list(dict.fromkeys(page_links)),
        )


def format_training_example(product: ProductRecord) -> dict:
    summary_bits: list[str] = []
    if product.description:
        summary_bits.append(product.description)
    if product.price:
        summary_bits.append(f"Price: {product.price}")
    if product.sizes:
        summary_bits.append("Available sizes: " + ", ".join(product.sizes[:10]))
    if product.images:
        summary_bits.append("Images: " + ", ".join(product.images[:3]))
    prompt = f"Tell me about {product.title}."
    completion_lines = [
        f"{product.title} (SKU: {product.sku or 'n/a'})",
        *summary_bits,
        f"More info: {product.url}",
    ]
    return {"prompt": prompt, "completion": " \n".join(filter(None, completion_lines))}


def write_jsonl(path: str, rows: Iterable[dict | ProductRecord]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            payload = asdict(row) if isinstance(row, ProductRecord) else row
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl a site and extract product catalog data.")
    parser.add_argument("base_url", help="Homepage or collection page to start crawling from")
    parser.add_argument("output", help="Path to write JSONL product records")
    parser.add_argument("--examples", help="Optional JSONL output with prompt/completion pairs")
    parser.add_argument("--keywords", nargs="+", help="Keywords that indicate product URLs (default: product shop item)")
    parser.add_argument("--max-pages", type=int, default=200, help="Cap on total pages fetched")
    parser.add_argument("--max-products", type=int, default=80, help="Cap on total product pages parsed")
    parser.add_argument("--delay", type=float, default=0.0, help="Sleep seconds between requests")
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    parser = CatalogParser(
        args.base_url,
        product_keywords=args.keywords,
        max_pages=args.max_pages,
        max_products=args.max_products,
        delay=args.delay,
    )
    products = parser.crawl()
    write_jsonl(args.output, products)
    if args.examples:
        training_rows = [format_training_example(product) for product in products]
        write_jsonl(args.examples, training_rows)
    print(f"Captured {len(products)} product pages from {len(parser.crawled_pages)} crawled pages.")
    if args.examples:
        print(f"Wrote prompt/completion pairs to {args.examples}.")


if __name__ == "__main__":
    main()
