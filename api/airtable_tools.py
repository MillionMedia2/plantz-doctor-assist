import os
import requests
from datetime import datetime, timedelta
from typing import List, Optional
import re

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY_STRAINS") or os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_STRAINS_BASE_ID") or os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_ID = os.getenv("AIRTABLE_STRAINS_PRODUCTS") or os.getenv("AIRTABLE_TABLE_ID")

API_URL = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ID}"
HEADERS = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}


def fetch_products(filter_formula: str, max_records: int = 10):
    params = {
        "filterByFormula": filter_formula,
        "maxRecords": max_records,
    }
    resp = requests.get(API_URL, headers=HEADERS, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json().get("records", [])


def get_product_prices(product_name: str) -> List[dict]:
    """Return all price/quantity options for a product by name (robust partial match)."""
    # Remove anything in parentheses and trim
    clean_name = re.sub(r"\s*\([^)]*\)", "", product_name).strip()
    # Use case-insensitive partial match
    formula = f"SEARCH(LOWER('{clean_name}'), LOWER({{product_name}}))"
    records = fetch_products(formula, max_records=5)
    results = []
    for rec in records:
        fields = rec.get("fields", {})
        results.append({
            "product_name": fields.get("product_name"),
            "SKU": fields.get("SKU"),
            "quantity": fields.get("quantity"),
            "price": fields.get("price"),
            "dose_unit": fields.get("dose_unit"),
        })
    return results


def filter_products(product_type: Optional[str] = None, condition: Optional[str] = None, min_price: Optional[float] = None, max_price: Optional[float] = None, limit: int = 3) -> List[dict]:
    """Filter products by type, condition, and price range."""
    formula_parts = []
    if product_type:
        formula_parts.append(f"FIND('{product_type}', {{product_type}})")
    if condition:
        formula_parts.append(f"FIND('{condition}', ARRAYJOIN({{condition}}, ','))")
    if min_price is not None:
        formula_parts.append(f"VALUE({{price}})>={min_price}")
    if max_price is not None:
        formula_parts.append(f"VALUE({{price}})<={max_price}")
    formula = "AND(" + ",".join(formula_parts) + ")" if formula_parts else ""  
    records = fetch_products(formula, max_records=limit)
    results = []
    for rec in records:
        fields = rec.get("fields", {})
        results.append({
            "product_name": fields.get("product_name"),
            "SKU": fields.get("SKU"),
            "quantity": fields.get("quantity"),
            "price": fields.get("price"),
            "dose_unit": fields.get("dose_unit"),
        })
    return results


def get_latest_products(days: int = 14, limit: int = 3) -> List[dict]:
    """Return products created or modified in the last N days."""
    since = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    formula = f"OR(IS_AFTER({{Created}}, '{since}'), IS_AFTER({{Last Modified}}, '{since}'))"
    records = fetch_products(formula, max_records=limit)
    results = []
    for rec in records:
        fields = rec.get("fields", {})
        results.append({
            "product_name": fields.get("product_name"),
            "SKU": fields.get("SKU"),
            "quantity": fields.get("quantity"),
            "price": fields.get("price"),
            "dose_unit": fields.get("dose_unit"),
            "created": fields.get("Created"),
            "last_modified": fields.get("Last Modified"),
        })
    return results


def format_product_markdown(product: dict) -> str:
    """Format a product dict as markdown for LLM output."""
    return f"**{product.get('product_name', 'Unknown Product')}**\n- SKU: {product.get('SKU', '-')}, Quantity: {product.get('quantity', '-')}, Price: {product.get('price', '-')}, Unit: {product.get('dose_unit', '-')}"


def format_products_markdown(products: List[dict]) -> str:
    if not products:
        return "No products found."
    return "\n".join([format_product_markdown(p) for p in products]) 