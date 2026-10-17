# Troubleshooting & FAQ

## Quick fixes

| Symptom | Most likely fix |
| --- | --- |
| Cannot sign in | Check the username and password with whoever set up the app. There is no self-service reset. |
| "Registration is disabled" | Normal. Accounts are created for you — use the [sign-in page](getting-started.md#1-sign-in) instead. |
| Dashboard is all zeros | The selected date range has no rows. Switch to **All time**, or [record results](results.md). |
| Spend is `€0.00` but revenue is not | Only revenue was imported (typical with Google Analytics). Record spend in the **Daily metrics** tab. |
| ROAS shows `—` | There is no spend to divide by, or no revenue in the range. |
| Some CSV rows were skipped | Read the line numbers in the import result and compare with [CSV import problems](#csv-import-problems). |
| A campaign shows `€0.00` on the Dashboard | It has no rows in the chosen range — widen the range to **All time**. |
| Google Analytics sync fails | Check the message on the card: see [Sync problems](#sync-problems). |
| Nothing appears on the Calendar | Items need a **Publish at** date; tasks need a **due date**. |

## Signing in

### I forgot my password, or I never got one

There is no "forgot password" flow by design — accounts are managed by whoever runs the app.
Ask them to reset it for you.

### The sign-up page says "Registration is disabled"

That is the normal setting. It means the instance is managed for a single organisation, and
accounts are created by an administrator.

## The Dashboard

### Everything is zero

Start with the date range. A CSV that only contains September will show nothing under *Last 7
days*. Switch to **All time** — if numbers appear, the range was the problem. If it is still
empty, no results have been recorded yet: see [Results](results.md).

### Revenue is there but spend is `€0.00`, and ROAS shows `—`

Google Analytics reports what you earned, not what you paid for ads. The Dashboard's spend and
ROAS come from the **Daily metrics** tab, so you need to put spend there — either the `spend`
column in a metrics CSV, or **Add row** by hand. See
[Results](results.md#the-tables-and-filters).

### I recorded an order in the Shop, but the Dashboard did not change

That is expected. Orders are the per-sale attribution story (which campaign, which link); the
Dashboard totals come from **Daily metrics**. Record the daily totals in
[Results](results.md).

### A campaign appears with all zeros

Its rows are outside the selected range. Widen the range to **All time**, or record results for
it. (Only the 20 highest-earning campaigns are listed; the rest still exist.)

### ROAS looks too good to be true

ROAS is revenue ÷ ad spend. It does not subtract product cost, shipping or VAT. Use it to
compare campaigns against each other, not as a profit figure.

## CSV import problems

The import summary tells you exactly how many rows were skipped, and lists each one with its
**line number** — line 1 is the header, so a problem reported on line 5 is the fourth data row.
Fix the file and import it again; re-importing is safe and updates existing rows.

| Message | What it means | Fix |
| --- | --- | --- |
| `campaign: Invalid pk "Fall baskets"` | You put the campaign **name** in the `campaign` column. | Use the campaign **id** — open the campaign, the id is the number at the end of the address (`/campaigns/12` → `12`). |
| `date: Date has wrong format` | The date is not `YYYY-MM-DD`. | Write `2026-10-01`, not `01/10/2026` or `Oct 1`. |
| `revenue: Ensure this value is greater than or equal to 0` | A negative number. | Imports accept `0` and above only. |
| `channel: Invalid pk "Instagram"` | You put the channel **name** in the `channel` column. | Use the channel **id**, or leave the column empty. |
| `A spend row already exists for this campaign/channel/date` | You added the same spend row twice by hand. | Edit the existing row instead of adding a second one. |
| The whole file was rejected | The upload was not a readable CSV. | Save as CSV (UTF-8) from your spreadsheet rather than `.xlsx`. |

A few things that are *not* errors, so you do not need to worry:

- **Extra columns** you do not use are ignored.
- **Blank lines** are skipped.
- **`campaign_id`** works as a heading just as well as `campaign`.
- **Re-importing the same file** updates rows rather than duplicating them.

## Sync problems

### The sync reports a 400 error

Google Analytics is not fully configured — usually a missing **property id**. Open
**Settings → API keys → Google Analytics 4 → Settings**, add the GA4 property id, save, and try
again. The card should read **Configured**.

### The sync reports a 502 error

The app reached Google and Google refused. The most common causes are:

- The service account does not have **Viewer** access to that GA4 property.
- The JSON key was revoked or the key file was pasted incompletely.
- The property id belongs to a different account.

The exact reason from Google is shown on the card under *Last sync failed*, so read that first.
An `invalid_grant` message almost always means the JSON key is wrong or expired.

### Sync ran but some campaigns were unmatched

Google Analytics reported traffic for a campaign name that does not exist in the app. Those
rows are **not imported** — and the sync tells you which names they were, so nothing is lost
silently.

To fix it, make the names agree:

1. Look at the name the sync listed, e.g. `fall-baskets-2026`.
2. Either correct the **UTM campaign** field on the campaign to match, or fix the tag in the
   links you are posting.
3. Run **Sync now** again.

Matching ignores upper and lower case, so `Fall-Baskets` and `fall-baskets` are the same
campaign.

### The sync ran but the Dashboard still shows no spend

Correct — a sync only brings in **revenue and orders**, never spend or CTR. Add spend in the
**Daily metrics** tab. See [Results](results.md).

### I imported a CSV and it replaced rows that came from Google Analytics

That is intentional. A manual import is treated as the more authoritative source, so the row is
updated and marked as manual. Simply run **Sync now** again if you want GA4's figures back for
those days.

### Can I make the sync run automatically every day?

Not in this version — press **Sync now** when you want fresh numbers. It always covers the last
7 days, so a weekly press is enough to stay current.

## Where a number came from

Every results row records its origin: **manual** for anything you typed or imported, **ga4** for
anything pulled from Google Analytics. That is how the app knows a CSV import should override a
synced row, and it is the honest answer to *"is this my number or Google's?"*

## Access and keys

### Who can change the API keys?

Only staff accounts. Everyone signed in can see whether a service is configured, but saving is
restricted. If the Save button does nothing for you, that is why.

### I saved a key and the box is empty again

Keys are write-only and never displayed after saving — the field stays blank on purpose. To
change it, type a new value; to change only a setting such as the property id, leave the key
box blank and it will keep the stored key.

### "Saved key can't be decrypted"

The server's secret key changed after the credential was saved. Remove the credential and save
it again.

## Other

### Generate AI does nothing, or shows a notice

AI suggestions need an OpenAI key. Ask an administrator to add one in
**Settings → API keys**, or use **Generate rules**, which always works.

### What currency is used?

Euros (€). Amounts are shown with two decimals.

### Can two people use the app at once?

Yes. There is one shared workspace — everyone signed in sees the same campaigns, content and
results.

### Something is broken and the page is blank

Reload the page. If it persists, the app may not be able to reach the backend — tell whoever
runs it, and mention what you were doing at the time.
