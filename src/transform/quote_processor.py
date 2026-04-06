"""Stage 2: merge CRM quotes with the price list, calculate quantities/discounts/taxes.

Ported from Quote4inventory03.py.

Reads:
  - Export002.csv / Export002.xlsx  (CRM quote export — full quote data)

Writes:
  - ImportSO.csv  (ready for manual upload to Zoho Inventory)

Returns:
  - email_body (str) — plain-text order summary to send to colleagues
Raises:
  - ValueError if any (Contact Name, Product Name) pair in the quotes is
    missing from the price list (deduplicated, sorted, human-readable message)
"""

from pathlib import Path

import numpy as np
import pandas as pd


def _read_export(path: Path) -> pd.DataFrame:
    """Read Export002 file — supports both .csv and .xlsx."""
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        return pd.read_excel(path, engine="openpyxl", dtype={"Quote Number": str})
    return pd.read_csv(path, dtype={"Quote Number": str}, encoding="utf-8-sig")


def process_quotes(
    export_path: Path,
    listino_df: pd.DataFrame,
    output_path: Path,
) -> tuple[str, str]:
    """
    Merge quotes with price list, apply business rules, write ImportSO.csv.

    Parameters
    ----------
    export_path : path to Export002 file (.csv or .xlsx)
    listino_df  : DataFrame produced by listino_builder.build_listino()
    output_path : where to write ImportSO.csv

    Returns
    -------
    ("", email_body) — empty first element kept for call-site compatibility

    Raises
    ------
    ValueError  if any (Contact Name, Product Name) pair in the quotes is
                missing from the price list
    """
    quotes_df = _read_export(export_path)

    # -----------------------------------------------------------------------
    # Validate: every (Product Name, Contact Name) in the quotes must exist
    # in the price list.
    # -----------------------------------------------------------------------
    listino_pairs = set(zip(listino_df["Product Name"], listino_df["Contact Name"]))
    missing_pairs = sorted({
        (row["Contact Name"], row["Product Name"])
        for _, row in quotes_df.iterrows()
        if (row["Product Name"], row["Contact Name"]) not in listino_pairs
    })
    if missing_pairs:
        lines = [
            f"Coppie Cliente/Item non trovate nel Listino09.csv "
            f"({len(missing_pairs)} {'coppia' if len(missing_pairs) == 1 else 'coppie'}):"
        ]
        for contact, product in missing_pairs:
            lines.append(f"  • Cliente: {contact}  |  Item: {product}")
        lines.append("Aggiornare Listino09.csv prima di caricare.")
        raise ValueError("\n".join(lines))

    # -----------------------------------------------------------------------
    # Merge (right join: keep all quote lines even if price list is missing)
    # -----------------------------------------------------------------------
    merged = listino_df.merge(quotes_df, on=["Product Name", "Contact Name"], how="right")

    # Numeric coercion
    merged["Percent"] = pd.to_numeric(merged["Percent"], errors="coerce").fillna(0)
    merged["Quantity"] = pd.to_numeric(merged["Quantity"], errors="coerce").fillna(0)
    merged["flag sconto"] = pd.to_numeric(merged["flag sconto"], errors="coerce").fillna(0)

    # Calculated fields
    merged["Quantity Ordered"] = (0.5 + merged["Percent"] * merged["Quantity"] / 100).fillna(0).astype(int)
    merged["Quantity FOC"] = merged["Quantity Ordered"] * merged["flag sconto"]
    merged["discount type"] = "entity_level"

    # -----------------------------------------------------------------------
    # Group by Quote Number — compute per-order entity discount
    # -----------------------------------------------------------------------
    df = merged.copy()
    df["Quantity FOC"] = df["Quantity FOC"].astype(float)

    # Use transform so the groupby key column is preserved (pandas 3.0 compatible)
    df["Discount"] = df.groupby("Quote Number")["Quantity FOC"].transform("sum") / 10

    # -----------------------------------------------------------------------
    # Enrich fields
    # -----------------------------------------------------------------------
    df["Created Time"] = df["Created Time"].astype(str)
    df["Subject"] = df["Subject"].astype(str)
    df["Exchange Rate"] = "1.00"
    df["Delivery Place"] = "-"
    df["Order Date"] = df["Created Time"].str[:10]
    df["Order Nr"] = df["Quote Number"]

    df["Description"] = df["Description"].fillna("-")
    df["Note"] = (
        "Rif Ordine: " + df["Order Nr"]
        + " Rif. Cliente: " + df["Subject"]
        + " Note: " + df["Description"]
    )

    df["Line Desc"] = df["Caus"].apply(lambda c: "" if c == "Sales" else "Free Samples")

    # Sort: Quote Number first, then sort order
    df["sort"] = pd.to_numeric(df["sort"], errors="coerce").fillna(0)
    df = df.drop(columns=["Quote Number"])
    df = df.reset_index(drop=True)
    df = df.sort_values(by=["Order Nr", "sort"])

    # -----------------------------------------------------------------------
    # VAT fields
    # -----------------------------------------------------------------------
    df["IsTaxInclusive"] = np.where(df["Vat"] == "Y", "false", None)
    df["Item Tax"] = np.where(df["Vat"] == "Y", "VAT 8.1", None)
    df["Item Tax Type"] = np.where(df["Vat"] == "Y", "ItemAmount", None)
    df["Item Tax perc"] = np.where(df["Vat"] == "Y", "8.100000", None)

    # -----------------------------------------------------------------------
    # Rename columns to Zoho Inventory field names
    # (preserve original typo "Ammount" — that's what Zoho expects)
    # -----------------------------------------------------------------------
    df = df.rename(columns={
        "Order Nr": "SalesOrder Number",
        "Quote Stage": "Status",
        "discount type": "Discount Type",
        "Discount": "Entity Discount Ammount",
        "Price": "Item Price",
        "Line Desc": "Item Desc",
        "Quantity": "Quantity CRM",
        "Quantity Ordered": "Quantity",
        "CF.Delivery Terms": "Delivery Terms",
        "Note": "Note Portale",
    })

    # Clean up stray 'nan' strings, then write CSV
    df = df.replace("nan", np.nan)
    df.to_csv(output_path, index=False, sep=",", na_rep="")

    # -----------------------------------------------------------------------
    # Build plain-text email body
    # -----------------------------------------------------------------------
    email_lines: list[str] = []
    for order_number, order_data in df.groupby("SalesOrder Number"):
        contact = order_data["Contact Name"].iloc[0]
        email_lines.append(f"SalesOrder Number: {order_number}")
        email_lines.append(f"Contact Name: {contact}")
        email_lines.append("")
        for _, row in order_data.iterrows():
            email_lines.append(
                f"  Product: {row['Product Name']},  "
                f"Quantity: {row['Quantity']},  "
                f"Price: {row['Item Price']}"
            )
        email_lines.append("")

    email_body = "\n".join(email_lines)
    return warnings, email_body
