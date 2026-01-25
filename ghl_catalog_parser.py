#!/usr/bin/env python3
"""
Parse Elastique Athletics product catalog from Shopify and format for GoHighLevel bot training.
Generates GHL-compatible product tiles with images, titles, prices, and links.
"""

import json
import re
from dataclasses import dataclass, asdict
from typing import Optional, List
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/119.0 Safari/537.36"
    )
}


@dataclass
class ElastiqueProduct:
    """Structured product data for Elastique Athletics"""
    title: str
    handle: str
    product_url: str
    image_url: str
    price: str
    original_price: Optional[str]
    description: str
    rating: Optional[str]
    reviews: Optional[str]
    collection: str
    style: str
    available_colors: List[str]
    available_sizes: List[str]
    benefits: str


class ElastiqueShopifyParser:
    """Parse Elastique Athletics Shopify catalog for GHL bot training"""

    def __init__(self):
        self.base_url = "https://www.elastiqueathletics.com"
        self.shop_url = f"{self.base_url}/collections/all"
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.products: List[ElastiqueProduct] = []

    def fetch_product_data(self) -> List[dict]:
        """Fetch JSON product data from Shopify storefront"""
        try:
            # Shopify products are available as JSON via .json endpoint
            shopify_api_url = "https://www.elastiqueathletics.com/collections/all/products.json"
            response = self.session.get(shopify_api_url, timeout=15)
            response.raise_for_status()
            return response.json().get("products", [])
        except Exception as e:
            print(f"Error fetching Shopify API: {e}")
            return []

    def fetch_product_page(self, product_url: str) -> BeautifulSoup:
        """Fetch individual product page for detailed extraction"""
        try:
            response = self.session.get(product_url, timeout=15)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            print(f"Error fetching {product_url}: {e}")
            return None

    def extract_product_details(self, product_data: dict) -> Optional[ElastiqueProduct]:
        """Extract and normalize product details from Shopify JSON"""
        try:
            title = product_data.get("title", "")
            handle = product_data.get("handle", "")
            product_url = f"{self.base_url}/products/{handle}"

            # Get primary image
            images = product_data.get("images", [])
            image_url = images[0]["src"] if images else ""

            # Price info
            variants = product_data.get("variants", [])
            if variants:
                primary_variant = variants[0]
                price = f"${primary_variant.get('price', '0')}"
                compare_price = primary_variant.get("compare_at_price")
                original_price = f"${compare_price}" if compare_price else None
            else:
                price = "Contact for pricing"
                original_price = None

            # Description
            description = product_data.get("body_html", "")
            description = BeautifulSoup(description, "html.parser").get_text(" ", strip=True)[:300]

            # Tags for collection and style
            tags = product_data.get("tags", [])
            if isinstance(tags, str):
                tag_list = [tag.strip() for tag in tags.split(",")]
            else:
                tag_list = list(tags) if tags else []
            collection = self._extract_collection(tag_list)
            style = self._extract_style(tag_list)
            benefits = self._extract_benefits(tag_list)

            # Color options (from variants)
            colors = set()
            for variant in variants:
                option_values = variant.get("option_values", {})
                if "Color" in option_values:
                    colors.add(option_values["Color"])
            colors = sorted(list(colors))

            # Size options
            sizes = set()
            for variant in variants:
                option_values = variant.get("option_values", {})
                if "Size" in option_values:
                    sizes.add(option_values["Size"])
            sizes = sorted(list(sizes))

            # Rating (if available in product data)
            rating = None
            reviews = None

            return ElastiqueProduct(
                title=title,
                handle=handle,
                product_url=product_url,
                image_url=image_url,
                price=price,
                original_price=original_price,
                description=description,
                rating=rating,
                reviews=reviews,
                collection=collection,
                style=style,
                available_colors=colors,
                available_sizes=sizes,
                benefits=benefits,
            )
        except Exception as e:
            print(f"Error extracting product details: {e}")
            return None

    def _extract_collection(self, tags: List[str]) -> str:
        """Extract collection name from tags"""
        collections = ["L'Original", "Divine", "Lisse", "Le Monde", "Riviera", "Fierce", "Adorn", "Iconic"]
        for tag in tags:
            if any(coll in tag for coll in collections):
                return tag
        return "General"

    def _extract_style(self, tags: List[str]) -> str:
        """Extract style/category from tags"""
        styles = ["Leggings", "Bras and Tops", "Bodysuits", "Shorts", "Tank", "Jumpsuit"]
        for tag in tags:
            for style in styles:
                if style.lower() in tag.lower():
                    return style
        return "Apparel"

    def _extract_benefits(self, tags: List[str]) -> str:
        """Extract key benefits from tags"""
        benefit_keywords = ["lymphatic drainage", "compression", "MicroPerle", "circulation"]
        benefits = []
        for tag in tags:
            for keyword in benefit_keywords:
                if keyword.lower() in tag.lower():
                    benefits.append(keyword)
        return ", ".join(set(benefits)) if benefits else "Compression & Wellness"

    def parse(self) -> List[ElastiqueProduct]:
        """Parse all products from catalog"""
        print("Fetching Elastique catalog from Shopify API...")
        product_data_list = self.fetch_product_data()

        if not product_data_list:
            print("No products found. Trying fallback method...")
            return []

        print(f"Found {len(product_data_list)} products. Extracting details...")
        for product_data in product_data_list:
            product = self.extract_product_details(product_data)
            if product:
                self.products.append(product)

        print(f"Successfully parsed {len(self.products)} products")
        return self.products


def format_ghl_knowledge_base_entry(product: ElastiqueProduct) -> dict:
    """
    Format product as GHL Knowledge Base entry (FAQ + Rich Text)
    """
    faq_question = f"Tell me about {product.title}"

    # Create rich text response with product info
    faq_answer = f"""
{product.title}

{product.benefits}

Price: {product.price}
{f'Regular: {product.original_price}' if product.original_price else ''}

Available Sizes: {', '.join(product.available_sizes) if product.available_sizes else 'Multiple'}
Available Colors: {', '.join(product.available_colors[:5]) if product.available_colors else 'Multiple'}

{product.description}

Learn more: {product.product_url}
"""

    return {
        "question": faq_question,
        "answer": faq_answer.strip(),
        "product_url": product.product_url,
        "image_url": product.image_url,
        "price": product.price,
        "type": "product_recommendation"
    }


def format_ghl_product_tile(product: ElastiqueProduct) -> dict:
    """
    Format product as GHL-compatible rich text card/tile
    Returns HTML/markdown that renders as a product tile in chat
    """
    discount_badge = ""
    if product.original_price and product.price:
        # Calculate discount percentage
        try:
            current = float(product.price.replace("$", ""))
            original = float(product.original_price.replace("$", ""))
            discount_pct = int(((original - current) / original) * 100)
            if discount_pct > 0:
                discount_badge = f'<div class="discount-badge">{discount_pct}% OFF</div>'
        except:
            pass

    # HTML product tile (GHL compatible)
    tile_html = f"""
<div class="ghl-product-tile" style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; margin: 8px 0; max-width: 280px; background: #fff;">
    {discount_badge}
    <img src="{product.image_url}" alt="{product.title}" style="width: 100%; height: 280px; object-fit: cover; border-radius: 6px; margin-bottom: 12px;">
    <h3 style="margin: 12px 0 8px 0; font-size: 16px; font-weight: 600; color: #222;">{product.title}</h3>
    <p style="margin: 8px 0; font-size: 13px; color: #666; line-height: 1.4;">{product.benefits}</p>
    <div style="margin: 12px 0;">
        <span style="font-size: 18px; font-weight: 700; color: #2c3e50;">{product.price}</span>
        {f'<span style="font-size: 13px; color: #999; text-decoration: line-through; margin-left: 8px;">{product.original_price}</span>' if product.original_price else ''}
    </div>
    <div style="margin: 8px 0; font-size: 12px; color: #666;">
        Sizes: {', '.join(product.available_sizes[:3]) if product.available_sizes else 'Multiple'}
    </div>
    <a href="{product.product_url}" target="_blank" style="display: inline-block; background: #2c3e50; color: white; padding: 10px 20px; border-radius: 4px; text-decoration: none; font-weight: 600; margin-top: 12px;">View Product</a>
</div>
"""
    return {
        "format": "html",
        "content": tile_html,
        "product": asdict(product)
    }


def write_ghl_knowledge_base(products: List[ElastiqueProduct], output_file: str):
    """Write products as GHL Knowledge Base entries (JSON)"""
    kb_entries = [format_ghl_knowledge_base_entry(p) for p in products]
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(kb_entries, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(kb_entries)} knowledge base entries to {output_file}")


def write_ghl_product_tiles(products: List[ElastiqueProduct], output_file: str):
    """Write products as GHL product tile HTML"""
    tiles = [format_ghl_product_tile(p) for p in products]
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(tiles, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(tiles)} product tiles to {output_file}")


def write_structured_catalog(products: List[ElastiqueProduct], output_file: str):
    """Write structured product data as JSON"""
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump([asdict(p) for p in products], f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(products)} structured products to {output_file}")


def main():
    parser = ElastiqueShopifyParser()
    products = parser.parse()

    if products:
        # Output files
        write_structured_catalog(products, "elastique_products.json")
        write_ghl_knowledge_base(products, "ghl_knowledge_base.json")
        write_ghl_product_tiles(products, "ghl_product_tiles.json")

        print("\n✓ Parsing complete!")
        print(f"  - Structured catalog: elastique_products.json")
        print(f"  - GHL Knowledge Base: ghl_knowledge_base.json")
        print(f"  - Product tiles: ghl_product_tiles.json")
    else:
        print("No products parsed. Check your connection and Shopify API access.")


if __name__ == "__main__":
    main()
