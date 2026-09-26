# Branding assets

| Folder | What goes there |
|--------|-----------------|
| `partners/` | Partner (consultancy) logos. `shenuka-inc.png` is the default "Prepared by" logo. |
| `customers/` | Customer logos, named after the customer (e.g. `contoso.png`). |

To change the default partner, edit `DEFAULT_PARTNER_NAME` and `DEFAULT_PARTNER_LOGO` in `server.py`.
To use a different partner for one dashboard, pass `partner_name` (and optionally `partner_logo`)
to `create_roi_dashboard`, or use the dashboard's **Upload partner logo** button.
