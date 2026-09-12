# Charge Totals

Transportation, Freight and Insurance are often entered as ordinary item rows rather than
as Sales Taxes and Charges. That keeps them inside taxable value where GSTR-1 wants them —
but it also buries them inside **Total**, **Net Total** and **Total Taxes and Charges**, so a
quote reading *"TOTAL AMOUNT 7,30,009"* is quietly carrying 1,000 of transport with no field a
print format can use to show the two apart.

This app adds that field. Three of them, in fact — see *Why three* below.

## What it adds

On **Quotation**, **Sales Order** and **Sales Invoice**:

| Field | Mirrors | Meaning |
|---|---|---|
| `custom_total_amount_without_additional_charges` | `total` | Total, less the charge rows |
| `custom_total_taxes_and_charges_without_additional_charges` | `total_taxes_and_charges` | Tax on the goods only |
| `custom_net_total_without_additional_charges` | `net_total` | Net Total (after discount), less the charge rows |

Each mirrors the standard field it shadows — Currency, `options: currency`, read-only — and sits
next to it. They are recomputed on every save, on `validate`, which runs *after* ERPNext's
`calculate_taxes_and_totals()`, so every amount they read is final.

A row counts as a charge when **`custom_is_tax_and_charge_item`** is ticked.

## Why three fields and not one

```
amount      is before any document-level discount
net_amount  is after it
the GST components are always computed on the discounted value
```

A printed column that reads *Total → less Discount → Amount After Discount → plus GST* needs
both the pre- and post-discount figures. Adding the **pre**-discount amount to **post**-discount
tax overstates a discounted document by exactly the discount — on a 5% discount that is the
difference between ₹7,63,636.90 and the correct ₹7,27,186.45.

If you never apply a document-level discount, the net field simply equals the amount field.

## Invariants

For any document, in any currency:

```
custom_total_amount_without_additional_charges + <charge rows' amount>     == total
custom_net_total_without_additional_charges    + <charge rows' net_amount> == net_total
```

Both are asserted by the test suite against every document on the site.

## What this app deliberately does NOT own

**`custom_is_tax_and_charge_item`**, the flag it reads. That belongs to whatever app or
customisation maintains it. `bench uninstall-app` deletes every Custom Field carrying the
removed app's module (`installer._delete_linked_documents`), so claiming the flag here would
take that other feature down with this one. A test asserts the flag is never stamped with this
app's module.

It also pairs naturally with a "no discount applicable" customisation — charge rows normally
should not absorb Additional Discount — but that is a separate concern and not included here.

## Using it in a print format

```jinja
{{ frappe.format_value(doc.custom_total_amount_without_additional_charges, {"fieldtype":"Currency"}, doc) }}
```

A full goods-then-charges column, reconciling to `grand_total`:

```
TOTAL AMOUNT              custom_total_amount_without_additional_charges
less DISCOUNT             discount_amount
AMOUNT AFTER DISCOUNT     custom_net_total_without_additional_charges
plus GST                  custom_total_taxes_and_charges_without_additional_charges
SUBTOTAL                  net-without-charges + tax-without-charges
plus each charge          its own amount and its own GST
TOTAL                     grand_total
```

Show each charge row's **own** GST as well as its amount, or the column will not reach
`grand_total`.

## Migrating from a Server Script implementation

Installing disables — does not delete — any Server Script named
`<DocType> - Totals Without Additional Charges` (and two earlier names), then backfills every
existing document, submitted ones included. Delete the disabled scripts in Desk once you are
satisfied.

## Install

```bash
bench get-app https://github.com/skyasir/erpnext_charge_totals
bench --site <site> install-app erpnext_charge_totals
```

Requires Frappe/ERPNext v15 or v16, and `custom_is_tax_and_charge_item` on the sales item
doctypes.

## Tests

```bash
cd <bench>/sites
../env/bin/python ../apps/erpnext_charge_totals/tests/test_charge_totals.py [site]
```

Runs against a live site and rolls everything back.
