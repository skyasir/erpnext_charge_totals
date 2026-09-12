# Copyright (c) 2026, Yasir Shaikh and contributors
"""Disable the Server Scripts this app reimplements in code."""

from erpnext_charge_totals.install import retire_legacy_scripts


def execute():
	retire_legacy_scripts()
