# Dashboard

The Dashboard answers one question: **is my marketing earning more than it costs?** It pulls
together everything you have recorded in [Results](results.md) across all campaigns.

![Dashboard](../assets/dashboard.png)

## Choosing the period

Top right, pick a range:

| Option | What it covers |
| --- | --- |
| **Last 7 days** | The last week, including today. |
| **Last 30 days** | The default. Good for a monthly check-in. |
| **Last 90 days** | For spotting slower trends. |
| **All time** | Everything ever recorded. |
| **Custom range…** | Two date boxes appear — pick a from and to date. |

Every number on the page follows this range, including the campaign table at the bottom.

!!! tip "Use the same range as your ad platform"
    If you compare the Dashboard against an ads report, set the *same* dates on both sides.
    A campaign that started on the 15th will look "cheap" in a range that starts on the 1st.

## The four cards

| Card | What it means |
| --- | --- |
| **Spend** | Total money spent on ads in the period. |
| **Revenue** | Total money earned in the period. |
| **Orders** | How many orders were recorded. |
| **ROAS** | Revenue ÷ spend — the highlighted card. |

Each card shows a small badge like `+12.4% vs previous period`. That compares the current
range against the equally long range immediately before it, so "Last 30 days" is compared
with the 30 days before that. If there is no earlier data, the badge is hidden.

!!! warning "ROAS is not profit"
    `ROAS = 2.00x` means you got back twice what you spent on ads. It ignores product cost,
    shipping and VAT. Use it to compare campaigns, not to calculate profit.

## Revenue vs spend chart

The chart plots daily totals for the chosen range: one line for revenue, one for spend.
Read it as a shape rather than exact values:

- A revenue line **above** the spend line is a healthy day.
- A spend spike with no matching revenue bump is worth investigating — maybe the ads ran but
  the landing page did not convert, or the revenue arrived a day later.
- A flat zero line usually means nothing was recorded for those days (see
  [Results](results.md)).

## Campaign performance table

Every campaign appears here, sorted by revenue, with its status badge, spend, revenue, orders
and ROAS. Click a campaign name to open it.

Campaigns with no rows in the selected period are still listed, showing `€0.00` and `0.00x` —
that is why a campaign you finished last month sits at the bottom with zeros. Widen the range
to **All time** to see its real numbers.

## What "empty" looks like, and why

| What you see | Most likely cause |
| --- | --- |
| "No campaigns yet" | You have not created a campaign. Start with [Campaigns](campaigns.md). |
| "No results in this range" | No rows for these dates — widen the range or import results. |
| Spend `€0.00` but revenue is not | Only revenue has been recorded (typical with Google Analytics). ROAS needs spend. |
| ROAS shows `—` | There is no spend to divide by, or no revenue. |
| Everything is zero | The range is too narrow, or the dates in your CSV were in a different month. |

If something still looks wrong, [Troubleshooting & FAQ](faq.md) lists the usual suspects.
