"""Tests for Charge Totals, run against a live site. Everything is rolled back.

    cd <bench>/sites
    ../env/bin/python ../apps/erpnext_charge_totals/tests/test_charge_totals.py [site]
"""

import pathlib
import sys
import unittest

import frappe


def _default_site():
	current = pathlib.Path("currentsite.txt")
	if current.is_file():
		return current.read_text().strip()
	sites = sorted(p.name for p in pathlib.Path(".").iterdir() if (p / "site_config.json").is_file())
	if len(sites) == 1:
		return sites[0]
	sys.exit(f"Pass the site name as an argument. Found {len(sites)}: {', '.join(sites) or 'none'}")


SITE = sys.argv[1] if len(sys.argv) > 1 else _default_site()


def setUpModule():
	frappe.init(site=SITE)
	frappe.connect()
	frappe.set_user("Administrator")


def tearDownModule():
	frappe.db.rollback()
	frappe.destroy()


class _Row(dict):
	"""Stands in for an item row; compute() only ever calls .get()."""


class TestCompute(unittest.TestCase):
	def setUp(self):
		from erpnext_charge_totals import totals

		self.totals = totals

	def rows(self):
		return [
			_Row(amount=10000, net_amount=9000, cgst_amount=810, sgst_amount=810,
			     custom_is_tax_and_charge_item=0),
			_Row(amount=20000, net_amount=18000, cgst_amount=1620, sgst_amount=1620,
			     custom_is_tax_and_charge_item=0),
			_Row(amount=1000, net_amount=1000, cgst_amount=25, sgst_amount=25,
			     custom_is_tax_and_charge_item=1),
		]

	def test_charge_rows_are_excluded_from_all_three(self):
		out = self.totals.compute(self.rows())
		self.assertEqual(out[self.totals.TOTAL_FIELD], 30000)
		self.assertEqual(out[self.totals.NET_FIELD], 27000)
		self.assertEqual(out[self.totals.TAX_FIELD], 4860)

	def test_amount_and_net_differ_under_discount(self):
		"""The whole reason three fields exist rather than one."""
		out = self.totals.compute(self.rows())
		self.assertNotEqual(out[self.totals.TOTAL_FIELD], out[self.totals.NET_FIELD])

	def test_an_untyped_charge_row_is_still_excluded(self):
		rows = self.rows()
		rows[2].pop("custom_charge_type", None)
		self.assertEqual(self.totals.compute(rows)[self.totals.TOTAL_FIELD], 30000)

	def test_no_charge_rows_means_the_totals_match_the_document(self):
		rows = [r for r in self.rows() if not r["custom_is_tax_and_charge_item"]]
		out = self.totals.compute(rows)
		self.assertEqual(out[self.totals.TOTAL_FIELD], sum(r["amount"] for r in rows))

	def test_empty_table(self):
		self.assertEqual(self.totals.compute([])[self.totals.TOTAL_FIELD], 0)
		self.assertEqual(self.totals.compute(None)[self.totals.NET_FIELD], 0)


class TestFieldOwnership(unittest.TestCase):
	def test_app_owns_its_three_fields(self):
		from erpnext_charge_totals import install, totals

		for doctype in totals.TARGET_DOCTYPES:
			for field in totals.ALL_FIELDS:
				module = frappe.db.get_value(
					"Custom Field", {"dt": doctype, "fieldname": field}, "module"
				)
				self.assertEqual(module, install.MODULE, f"{doctype}.{field} is not stamped")

	def test_app_does_not_own_the_flag_it_reads(self):
		"""Uninstall deletes every Custom Field carrying the app's module; the flag
		belongs to whatever maintains it, so claiming it would break that."""
		from erpnext_charge_totals import install, totals

		for doctype in totals.TARGET_DOCTYPES:
			module = frappe.db.get_value(
				"Custom Field",
				{"dt": f"{doctype} Item", "fieldname": totals.CHARGE_FLAG_FIELD},
				"module",
			)
			self.assertNotEqual(module, install.MODULE)

	def test_the_flag_exists(self):
		from erpnext_charge_totals import totals

		for doctype in totals.TARGET_DOCTYPES:
			self.assertTrue(
				frappe.get_meta(f"{doctype} Item").get_field(totals.CHARGE_FLAG_FIELD),
				f"{doctype} Item is missing {totals.CHARGE_FLAG_FIELD}",
			)


class TestAgainstRealDocuments(unittest.TestCase):
	"""The invariants have to hold on whatever the site actually contains."""

	def test_invariants_hold_on_every_document(self):
		from erpnext_charge_totals import totals

		checked = 0
		for doctype in totals.TARGET_DOCTYPES:
			for name in frappe.get_all(doctype, pluck="name"):
				doc = frappe.get_doc(doctype, name)
				charge_amount = sum(
					r.amount or 0 for r in doc.items if r.get(totals.CHARGE_FLAG_FIELD)
				)
				charge_net = sum(
					r.net_amount or 0 for r in doc.items if r.get(totals.CHARGE_FLAG_FIELD)
				)

				self.assertAlmostEqual(
					(doc.get(totals.TOTAL_FIELD) or 0) + charge_amount, doc.total, places=2,
					msg=f"{name}: amount invariant",
				)
				self.assertAlmostEqual(
					(doc.get(totals.NET_FIELD) or 0) + charge_net, doc.net_total, places=2,
					msg=f"{name}: net invariant",
				)
				checked += 1

		self.assertTrue(checked, "no documents on this site to check")

	def test_a_plain_save_repopulates_the_fields(self):
		from erpnext_charge_totals import totals

		name = frappe.db.get_value("Quotation", {"docstatus": 0}, "name")
		if not name:
			self.skipTest("no draft Quotation on this site")

		before = frappe.db.get_value("Quotation", name, list(totals.ALL_FIELDS), as_dict=True)
		frappe.db.set_value("Quotation", name, dict.fromkeys(totals.ALL_FIELDS, 0),
		                    update_modified=False)

		frappe.get_doc("Quotation", name).save()

		after = frappe.db.get_value("Quotation", name, list(totals.ALL_FIELDS), as_dict=True)
		for field in totals.ALL_FIELDS:
			self.assertAlmostEqual(after[field], before[field], places=2, msg=field)


if __name__ == "__main__":
	unittest.main(argv=sys.argv[:1], verbosity=2)
