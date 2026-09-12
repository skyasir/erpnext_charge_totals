# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from erpnext_charge_totals import totals

MODULE = "Charge Totals"

# The DB-resident implementation this app replaces. Disabled -- not deleted -- so
# the change is reversible; delete them in Desk once you are satisfied.
LEGACY_SERVER_SCRIPTS = tuple(
	f"{doctype} - {suffix}"
	for doctype in totals.TARGET_DOCTYPES
	for suffix in (
		"Totals Without Additional Charges",
		"Total Without Additional Charges",
		"Goods and Charges Split",
	)
)


def after_install():
	setup()
	retire_legacy_scripts()
	for doctype in totals.TARGET_DOCTYPES:
		print(f"  backfilled {totals.backfill(doctype)} {doctype}(s)")
	frappe.db.commit()


def setup():
	"""Idempotent; also runs on every migrate."""
	make_custom_fields()


def retire_legacy_scripts():
	for name in LEGACY_SERVER_SCRIPTS:
		if frappe.db.exists("Server Script", name):
			frappe.db.set_value("Server Script", name, "disabled", 1, update_modified=False)
			print(f"  disabled Server Script {name}")
	frappe.clear_cache()


def custom_fields() -> dict:
	"""The three goods-side figures, on every selling document that carries charge rows.

	Each mirrors the standard field it shadows (Currency / options currency /
	read_only) and is placed next to it. print_hide is left off, matching `total`,
	so they behave like the standard totals in a print format.

	Note what is NOT here: `custom_is_tax_and_charge_item`, the flag these read.
	That belongs to whatever app or customisation maintains it -- uninstalling an
	app deletes every Custom Field carrying its module
	(installer._delete_linked_documents), so claiming the flag would take that
	feature down with this one.
	"""
	fields = {}

	for doctype in totals.TARGET_DOCTYPES:
		fields[doctype] = [
			{
				"fieldname": totals.TOTAL_FIELD,
				"label": "Total Amount Without Additional Charges",
				"fieldtype": "Currency",
				"options": "currency",
				"insert_after": "net_total",
				"read_only": 1,
				"description": "Total excluding every row ticked Is Tax and Charge Item.",
			},
			{
				"fieldname": totals.TAX_FIELD,
				"label": "Total Taxes and Charges Without Additional Charges",
				"fieldtype": "Currency",
				"options": "currency",
				"insert_after": totals.TOTAL_FIELD,
				"read_only": 1,
				"description": "Tax on the items only, excluding tax on rows ticked Is Tax and Charge Item.",
			},
			{
				"fieldname": totals.NET_FIELD,
				"label": "Net Total Without Additional Charges",
				"fieldtype": "Currency",
				"options": "currency",
				"insert_after": totals.TAX_FIELD,
				"read_only": 1,
				"description": "Net Total (after discount) excluding rows ticked Is Tax and Charge Item.",
			},
		]

	for field_list in fields.values():
		for field in field_list:
			field.setdefault("module", MODULE)

	return fields


def make_custom_fields():
	create_custom_fields(custom_fields(), ignore_validate=True)
