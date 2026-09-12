# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt
"""Totals with the tax-and-charge rows taken back out.

Transportation, Freight and Insurance are entered as ordinary item rows, so they
sit inside Total, Net Total and Total Taxes and Charges along with the goods. A
quote reading "TOTAL AMOUNT 7,30,009" is quietly carrying 1,000 of transport,
with no field a print format can use to show the two apart.

A row is a charge when `custom_is_tax_and_charge_item` is ticked. That field is
NOT owned here -- see install.py.

Why three fields and not one:

    amount      is before any document-level discount
    net_amount  is after it
    the GST components are always computed on the discounted value

so a print format that shows "Total, less Discount, Amount After Discount, plus
GST" needs both the pre- and post-discount figures. Adding the pre-discount
amount to post-discount tax overstates a discounted document by exactly the
discount.

Invariants, for any document:

    custom_total_amount_without_additional_charges + <charge rows' amount>     == total
    custom_net_total_without_additional_charges    + <charge rows' net_amount> == net_total
"""

import frappe
from frappe.utils import flt

TARGET_DOCTYPES = ("Quotation", "Sales Order", "Sales Invoice")

CHARGE_FLAG_FIELD = "custom_is_tax_and_charge_item"

TOTAL_FIELD = "custom_total_amount_without_additional_charges"
NET_FIELD = "custom_net_total_without_additional_charges"
TAX_FIELD = "custom_total_taxes_and_charges_without_additional_charges"

ALL_FIELDS = (TOTAL_FIELD, NET_FIELD, TAX_FIELD)

# india_compliance puts these on every sales item doctype
GST_COMPONENTS = (
	"igst_amount",
	"cgst_amount",
	"sgst_amount",
	"cess_amount",
	"cess_non_advol_amount",
)


def row_tax(row) -> float:
	return sum(flt(row.get(component)) for component in GST_COMPONENTS)


def compute(items) -> dict:
	"""Field -> amount, from an item table. Pure; no document is touched."""
	totals = dict.fromkeys(ALL_FIELDS, 0.0)

	for row in items or []:
		if row.get(CHARGE_FLAG_FIELD):
			continue

		totals[TOTAL_FIELD] += flt(row.get("amount"))
		totals[NET_FIELD] += flt(row.get("net_amount"))
		totals[TAX_FIELD] += row_tax(row)

	return totals


def update_totals(doc, method=None):
	for field, amount in compute(doc.items).items():
		doc.set(field, amount)


def backfill(doctype: str, names: list[str] | None = None) -> int:
	"""Recompute saved documents, submitted ones included.

	These are derived display values, so they are written straight to the table:
	nothing keys off them, and re-saving a submitted document only to refresh a
	print total would be far more disruptive.
	"""
	if doctype not in TARGET_DOCTYPES:
		frappe.throw(f"{doctype} does not carry charge rows")

	fields = ["amount", "net_amount", CHARGE_FLAG_FIELD, *GST_COMPONENTS]
	changed = 0

	for name in names or frappe.get_all(doctype, pluck="name"):
		totals = compute(
			frappe.get_all(
				f"{doctype} Item",
				filters={"parent": name, "parenttype": doctype},
				fields=fields,
			)
		)
		current = frappe.db.get_value(doctype, name, list(ALL_FIELDS), as_dict=True) or {}

		if all(abs(flt(current.get(f)) - totals[f]) < 0.005 for f in ALL_FIELDS):
			continue

		frappe.db.set_value(doctype, name, totals, update_modified=False)
		changed += 1

	return changed
