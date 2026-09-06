# Full news-article text is published in civicatlasma/markdown/

Found 2026-09-06 while working the `ungrounded-names-1` bucket. Sudbury2025's only
held reading turned out to be a whole Sudbury Weekly story, which
`civicatlasma/CLAUDE.md` forbids in as many words:

> **Full text of news articles.** This corpus cites journalism -- headline, URL,
> date, a short snippet -- it does not reproduce it. Several sources are paid
> subscriptions. Full article text belongs in `civicatlas-private`.
> A publish step that would place a news-sourced markdown file in this repository
> is a bug in the publish step, not a judgement call to make in the moment.

`civicatlas-private/CLAUDE.md` records that 213 such texts were removed from the
public repository and its history rebuilt in September 2026. These are back, or
never left.

## Method

Scanned all 983 files in `civicatlasma/markdown/` for outlet names, bylines and
site chrome (`Share This Article`, `Post navigation`, `Subscribe`, `Sign up for`,
`All Rights Reserved`, author-page links). 21 files matched; each was then opened
and classified by hand.

## Full commercial-news article text -- 17 files, 213 KB

| file | bytes | outlet |
|---|---|---|
| OakBluffs2022 | 39,430 | MV Times |
| Westwood2022 | 20,589 | Westwood Minute |
| Westwood2025 | 19,798 | Westwood Minute |
| Westwood2024 | 18,647 | Westwood Minute |
| Westwood2021 | 20,123 | Westwood Minute |
| Southborough2023 | 17,556 | MySouthborough |
| Dalton2025 | 16,581 | iBerkshires |
| Lanesborough2025 | 15,747 | iBerkshires |
| Grafton2025 | 11,787 | Community Advocate |
| Swampscott2021 | 7,429 | Wicked Local |
| Ludlow2022 | 4,847 | The Reminder |
| Marshfield2025 | 4,616 | WATD News |
| Leominster2021 | 4,357 | Telegram & Gazette |
| Sudbury2025 | 4,315 | Sudbury Weekly |
| WestSpringfield2025 | 3,503 | The Reminder |
| Mashpee2024 | 2,619 | Cape Cod Times |
| NorthAdams2021 | 1,226 | The Berkshire Eagle |

Several are paid subscriptions -- the Berkshire Eagle, Cape Cod Times, Telegram &
Gazette and MV Times among them. Swampscott2021 and Mashpee2024 still carry the
tracking query strings from the URL they were fetched with.

## Not this -- correctly public, listed so nobody re-checks them

- `Abington2025` (27,506) and `Worthington2026` (2,149) are the towns' own web
  pages. Municipal, in scope, fine.
- `Monterey2024` (1,542) and `Richmond2022` (2,663) are the citation-index form
  the rule asks for: a written summary naming the Berkshire Eagle story, its
  author, date and URL, with the figures in a table. Fine, and worth keeping as
  the model for what a news-sourced reading should look like.

## Not fixed here, deliberately

`civicatlasma/CLAUDE.md`: *"Never edit a file in this repository by hand. A hand
edit is silently overwritten by the next publish."* Deleting these seventeen from
the tip would leave them in the history and would come back on the next publish.
The fix is in the publish step and the removal is the owner's call -- and, given
the September 2026 history rebuild, may need to be a history rewrite again rather
than a deletion commit.
