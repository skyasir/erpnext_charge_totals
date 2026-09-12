app_name = "erpnext_charge_totals"
app_title = "Charge Totals"
app_publisher = "Yasir Shaikh"
app_description = (
	"Totals that exclude tax-and-charge item rows (transportation, freight, insurance), "
	"so a print format can show the goods figure and the charges apart"
)
app_email = "erp.yasirshaikh@gmail.com"
app_license = "mit"

required_apps = ["erpnext"]

after_install = "erpnext_charge_totals.install.after_install"

# Custom fields are re-applied on every migrate rather than once in a patch, so a
# later edit to a definition actually lands.
after_migrate = ["erpnext_charge_totals.install.setup"]

# `validate` doc_event handlers run after the controller's own validate, i.e.
# after calculate_taxes_and_totals(), so amount / net_amount / the GST components
# are all final by the time these read them.
doc_events = {
	doctype: {"validate": "erpnext_charge_totals.totals.update_totals"}
	for doctype in ("Quotation", "Sales Order", "Sales Invoice")
}
