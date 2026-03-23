"""Stage 1: build the internal price list DataFrame from raw input files.

Ported from quote_Listino.py.

Reads:
  - Export002.csv   (CRM quote export — used only to get unique contact names)
  - Listino09.csv   (product prices per client)
  - Gadget.csv      (FOC/gadget items appended to every client)
  - Clienti09.csv   (customer master: payment terms, delivery terms, VAT)

Returns a pandas DataFrame with the same columns as listino00.csv.
"""

import csv
import re
from pathlib import Path
from typing import Any

import pandas as pd


CSV_ENCODING = "utf-8-sig"
CSV_DELIMITER = ","


# ---------------------------------------------------------------------------
# Low-level CSV helpers (kept as pure Python — no pandas needed for stage 1)
# ---------------------------------------------------------------------------

def _normalize(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _read_csv(file_path: Path) -> list[dict[str, str]]:
    with open(file_path, mode="r", encoding=CSV_ENCODING, newline="") as f:
        reader = csv.DictReader(f, delimiter=CSV_DELIMITER)
        return [{_normalize(k): _normalize(v) for k, v in row.items()} for row in reader]


def _parse_float(value: str) -> float:
    value = _normalize(value)
    if not value:
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def _fmt(value: Any) -> str:
    """Format a number as string without trailing .0"""
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return ""
        try:
            value = float(value)
        except ValueError:
            return value
    if isinstance(value, (int, float)):
        return str(int(value)) if float(value).is_integer() else str(float(value))
    return str(value)


def _extract_sku(item_inventory: str) -> str:
    """Return the text before '--' (e.g. 'ABC123--Product' → 'ABC123')."""
    s = _normalize(item_inventory)
    return s.split("--", 1)[0].strip() if "--" in s else s


def _extract_sort(item_inventory: str) -> int:
    """Return last 3 digits of the item string as sort order."""
    s = _normalize(item_inventory)
    if len(s) >= 3 and s[-3:].isdigit():
        return int(s[-3:])
    digits = re.findall(r"(\d{3})", s)
    return int(digits[-1]) if digits else 0


def _first(row: dict[str, str], *names: str) -> str:
    """Return the value of the first matching key found in the row."""
    for name in names:
        if name in row:
            return _normalize(row[name])
    return ""


# ---------------------------------------------------------------------------
# Stage 1 logic
# ---------------------------------------------------------------------------

def build_listino(
    export_path: Path,
    listino09_path: Path,
    gadget_path: Path,
    clienti09_path: Path,
) -> pd.DataFrame:
    """
    Build the internal price list and return it as a DataFrame.

    Parameters
    ----------
    export_path    : path to Export002.csv
    listino09_path : path to Listino09.csv
    gadget_path    : path to Gadget.csv
    clienti09_path : path to Clienti09.csv

    Returns
    -------
    pd.DataFrame with columns:
        Contact Name, Customer Name, Payment Terms, Product Name, Item Name,
        Caus, Percent, SKU, Price, CF.Delivery Terms, flag sconto, sort, Vat
    """
    export_rows = _read_csv(export_path)
    listino_rows = _read_csv(listino09_path)
    gadget_rows = _read_csv(gadget_path)
    clienti_rows = _read_csv(clienti09_path)

    # Unique contact names in order of first appearance
    seen: set[str] = set()
    unique_contacts: list[str] = []
    for row in export_rows:
        name = _normalize(row.get("Contact Name", ""))
        if name and name not in seen:
            seen.add(name)
            unique_contacts.append(name)

    # Index Listino09 by client name
    listino_index: dict[str, list[dict[str, str]]] = {}
    for row in listino_rows:
        cliente = _normalize(row.get("Cliente", ""))
        if cliente:
            listino_index.setdefault(cliente, []).append(row)

    # Index Clienti09 by Full Name (first occurrence wins)
    clienti_index: dict[str, dict[str, str]] = {}
    for row in clienti_rows:
        name = _normalize(row.get("Full Name", ""))
        if name and name not in clienti_index:
            clienti_index[name] = row

    # Build rows
    wrk_rows: list[dict[str, str]] = []

    for contact_name in unique_contacts:
        for row in listino_index.get(contact_name, []):
            product_name = _first(row, "Item", "Product Name")
            item_inv = _first(
                row,
                "Item di Inventory",
                "Item di Inventory ",
                "Item Inventory",
                "Inventory Item",
            )
            causale = _first(row, "Causale Qty agg.", "Causale Qty agg")
            qty_agg_pct = _parse_float(
                _first(row, "Qta aggiuntiva (%)", "Quantità aggiuntiva (%)", "Quantita aggiuntiva (%)")
            )
            prezzo = _first(row, "Prezzo")
            prezzo_agg = _first(row, "Prezzo Qty aggiuntiva", "Prezzo Qty aggiuntiva ")

            sku = _extract_sku(item_inv)
            sort_val = _extract_sort(item_inv)

            # Main sales row
            wrk_rows.append({
                "Contact Name": contact_name,
                "Customer Name": "",
                "Payment Terms": "",
                "Product Name": product_name,
                "Item Name": "",
                "Caus": "Sales",
                "Percent": _fmt(100),
                "SKU": sku,
                "Price": prezzo,
                "CF.Delivery Terms": "",
                "flag sconto": _fmt(0),
                "sort": _fmt(sort_val),
                "Vat": "",
            })

            # Additional quantity row (only when qty_agg_pct > 0)
            if qty_agg_pct > 0:
                flag = 1 if causale == "Free Sample (FOC)" else 0
                wrk_rows.append({
                    "Contact Name": contact_name,
                    "Customer Name": "",
                    "Payment Terms": "",
                    "Product Name": product_name,
                    "Item Name": "",
                    "Caus": causale,
                    "Percent": _fmt(qty_agg_pct),
                    "SKU": sku,
                    "Price": prezzo_agg,
                    "CF.Delivery Terms": "",
                    "flag sconto": _fmt(flag),
                    "sort": _fmt(sort_val + 1),
                    "Vat": "",
                })

        # Gadgets appended to every client
        for gadget in gadget_rows:
            wrk_rows.append({
                "Contact Name": contact_name,
                "Customer Name": "",
                "Payment Terms": "",
                "Product Name": _normalize(gadget.get("Product Name", "")),
                "Item Name": "",
                "Caus": "FOC",
                "Percent": _fmt(100),
                "SKU": _normalize(gadget.get("SKU", "")),
                "Price": _fmt(0.1),
                "CF.Delivery Terms": "",
                "flag sconto": _fmt(1),
                "sort": _fmt(900),
                "Vat": "",
            })

    # Enrich with customer master data
    final_rows: list[dict[str, str]] = []
    for row in wrk_rows:
        contact_name = row["Contact Name"]
        c = clienti_index.get(contact_name, {})
        final_rows.append({
            "Contact Name": contact_name,
            "Customer Name": _normalize(c.get("Department", "")),
            "Payment Terms": _normalize(c.get("Payment_Terms", "")),
            "Product Name": row["Product Name"],
            "Item Name": row["Item Name"],
            "Caus": row["Caus"],
            "Percent": row["Percent"],
            "SKU": row["SKU"],
            "Price": row["Price"],
            "CF.Delivery Terms": _normalize(c.get("Delivery_Terms", "")),
            "flag sconto": row["flag sconto"],
            "sort": row["sort"],
            "Vat": _normalize(c.get("Vat Number", "")),
        })

    columns = [
        "Contact Name", "Customer Name", "Payment Terms", "Product Name",
        "Item Name", "Caus", "Percent", "SKU", "Price", "CF.Delivery Terms",
        "flag sconto", "sort", "Vat",
    ]
    return pd.DataFrame(final_rows, columns=columns)
