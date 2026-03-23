"""
Shopify Store Monitor — Source Adapter Plugin

Monitors Shopify stores via their public /products.json endpoint.
Detects: price changes, new products, out-of-stock events.

Config:
  store_urls: list of Shopify store URLs
  check_prices: bool (default True)
  check_inventory: bool (default True)
  check_new_products: bool (default True)
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# State file for tracking previous snapshots
STATE_DIR = Path(__file__).resolve().parent
STATE_FILE = STATE_DIR / "state.json"


def _load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _fetch_products(store_url: str) -> list[dict]:
    """Fetch products from a Shopify store's public products.json endpoint."""
    url = store_url.rstrip("/") + "/products.json?limit=250"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "OpenClaw-Intelligence/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("products", [])
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        print(f"  Warning: Could not fetch {url}: {e}")
        return []


def _product_key(store_url: str, product_id) -> str:
    """Create a unique key for a product across stores."""
    return hashlib.md5(f"{store_url}:{product_id}".encode()).hexdigest()[:12]


def _extract_price(product: dict) -> float | None:
    """Get the lowest variant price for a product."""
    variants = product.get("variants", [])
    if not variants:
        return None
    prices = []
    for v in variants:
        try:
            prices.append(float(v.get("price", 0)))
        except (ValueError, TypeError):
            pass
    return min(prices) if prices else None


def _is_available(product: dict) -> bool:
    """Check if any variant is available."""
    for v in product.get("variants", []):
        if v.get("available", False):
            return True
    return False


def collect(config: dict) -> list[dict]:
    """
    Collect findings by monitoring Shopify stores.

    Returns a list of finding dicts for the intelligence pipeline.
    """
    store_urls = config.get("store_urls", [])
    check_prices = config.get("check_prices", True)
    check_inventory = config.get("check_inventory", True)
    check_new_products = config.get("check_new_products", True)

    if not store_urls:
        print("  No store_urls configured. Add them to config.json.")
        return []

    state = _load_state()
    findings = []
    now = datetime.now(timezone.utc).isoformat()

    for store_url in store_urls:
        store_url = store_url.rstrip("/")
        store_key = hashlib.md5(store_url.encode()).hexdigest()[:8]
        print(f"  Checking {store_url}...")

        products = _fetch_products(store_url)
        if not products:
            continue

        prev_products = state.get(store_key, {})
        current_products = {}

        for product in products:
            pid = str(product.get("id", ""))
            title = product.get("title", "Unknown")
            handle = product.get("handle", "")
            price = _extract_price(product)
            available = _is_available(product)
            product_url = f"{store_url}/products/{handle}"
            key = _product_key(store_url, pid)

            current_products[pid] = {
                "title": title,
                "price": price,
                "available": available,
                "handle": handle,
            }

            prev = prev_products.get(pid)

            if prev is None and check_new_products:
                # New product detected
                findings.append({
                    "id": f"shopify-new-{key}",
                    "title": f"New product: {title}",
                    "url": product_url,
                    "source": "plugin:shopify-monitor",
                    "category": "ecommerce",
                    "summary": f"New product listed on {store_url}: {title} at ${price:.2f}" if price else f"New product listed: {title}",
                    "timestamp": now,
                    "metadata": {
                        "event": "new_product",
                        "store": store_url,
                        "product_id": pid,
                        "price": price,
                    },
                })

            elif prev is not None:
                prev_price = prev.get("price")
                prev_available = prev.get("available")

                # Price change
                if check_prices and price is not None and prev_price is not None and price != prev_price:
                    direction = "dropped" if price < prev_price else "increased"
                    findings.append({
                        "id": f"shopify-price-{key}",
                        "title": f"Price {direction}: {title}",
                        "url": product_url,
                        "source": "plugin:shopify-monitor",
                        "category": "ecommerce",
                        "summary": f"{title} price {direction} from ${prev_price:.2f} to ${price:.2f} on {store_url}",
                        "timestamp": now,
                        "metadata": {
                            "event": "price_change",
                            "store": store_url,
                            "product_id": pid,
                            "old_price": prev_price,
                            "new_price": price,
                            "direction": direction,
                        },
                    })

                # Inventory change
                if check_inventory and available != prev_available:
                    event = "back_in_stock" if available else "out_of_stock"
                    label = "back in stock" if available else "out of stock"
                    findings.append({
                        "id": f"shopify-stock-{key}",
                        "title": f"{title} is now {label}",
                        "url": product_url,
                        "source": "plugin:shopify-monitor",
                        "category": "ecommerce",
                        "summary": f"{title} is now {label} on {store_url}",
                        "timestamp": now,
                        "metadata": {
                            "event": event,
                            "store": store_url,
                            "product_id": pid,
                        },
                    })

        # Update state
        state[store_key] = current_products

    _save_state(state)
    return findings
