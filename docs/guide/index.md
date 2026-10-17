# The map of the app

Everything lives in the left sidebar, grouped into four areas. You do not need to use all of
them on day one — most people start with **Campaigns**, **Results** and **Dashboard**.

| Area | Pages | What you do there |
| --- | --- | --- |
| **Plan** | [Dashboard](dashboard.md) | See spend, revenue, orders and ROAS for the period you choose. |
| | [Campaigns](campaigns.md) | Create and run campaigns; open one to see its results, content, tasks and suggestions. |
| | [Content](content-calendar.md) | Plan the posts, stories and ads you will publish, per channel. |
| | [Calendar](content-calendar.md) | See the same content laid out over the month. |
| **Measure** | [Results](results.md) | Record spend and revenue — manually, by CSV import, or automatically from Google Analytics. |
| | [Suggestions](suggestions.md) | Get rule-based and AI next steps, and turn one into a task. |
| **Shop** | [Shop](shop.md) | Products, orders and channels — and which campaign an order came from. |
| **Settings** | [Settings](settings.md) | Build tagged links, pick a theme, connect Google Analytics, manage API keys. |

## How the numbers fit together

The Dashboard is built from two simple things:

- **Spend** — money going out. Comes from the *Ad spend* rows, or from a Google Ads
  connection later.
- **Revenue** and **orders** — money coming in. Come from the *Daily metrics* rows, or from a
  Google Analytics 4 connection.

From those it shows **ROAS** (*Return On Ad Spend*), which is simply:

$$
\text{ROAS} = \frac{\text{revenue}}{\text{spend}}
$$

A ROAS of `2.00x` means every €1 of ad spend brought back €2 of revenue. Below `1.00x`, the
campaign is costing more than it earns.

!!! warning "A campaign with revenue but no spend shows ROAS of —"
    That is normal at first. Google Analytics tells us revenue, but it does not tell us what
    you paid for the ads. Until you record spend (manually or by CSV), there is nothing to
    divide by. See [Results](results.md).

## The three habits that make this app work

These three things are what separate a useful Dashboard from a pretty but empty one:

1. **Create the campaign before you spend money on it.** Otherwise the spend has nowhere to go.
2. **Tag every link with the campaign's UTM campaign name.** This is what connects a visit or
   an order back to a campaign. The [UTM builder](settings.md#utm-builder) does it for you.
3. **Record results regularly.** Daily is ideal; weekly is workable. Late data is still data.

!!! tip "The one field that matters most"
    If you remember nothing else: fill in **UTM campaign** on every campaign, and use that
    exact name in your links. Almost everything else in the app depends on it.
