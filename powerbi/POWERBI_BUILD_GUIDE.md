# Power BI build guide: Credit Card Customer Segments

A step-by-step guide to building the Power BI report for this project, from the tables exported by the notebook.
Allow 3–5 hours. Save your work often (**Ctrl + S**).

**What you'll build:** a 5-page report

| Page | Question it answers |
|---|---|
| 1. Overview | Who are our customers, and where is the balance concentrated? |
| 2. Segment profiles | How does each segment differ from the average customer? |
| 3. Segment explorer | What do the customers in a segment look like, and who doesn't fit? |
| 4. Personas & actions | What should we do for each segment? |
| 5. Method | How were the segments found, and how confident are we? |

**Files in this folder**

| File | What it is |
|---|---|
| `data/customers.csv` | One row per customer (8,949): behaviour, segment, flags, PCA coordinates |
| `data/segments.csv` | One row per segment (6): name, description, action, risk view, colour |
| `data/metrics.csv` | One row per profile metric (12) |
| `data/segment_profile.csv` | One row per segment × metric (72): means and z-scores |
| `data/k_selection.csv` | One row per number of segments tried (2–10) |
| `DataKritii_theme.json` | Report theme in DataKritii colours |
| `measures.dax` | Every DAX measure, with its format |

---

## Part 1: Load the data

1. Open **Power BI Desktop**. If you don't have it, it's free from the Microsoft Store.
2. **Home → Get data → Text/CSV**, choose `powerbi/data/customers.csv`, then **Transform Data** (not Load). This opens Power Query.
3. Check the data types (the icon left of each column name). Change any that are wrong:

   | Column(s) | Type |
   |---|---|
   | `customer_id` | Text |
   | `segment_id`, `purchase_transactions`, `cash_advance_transactions`, `tenure_months`, `uses_cash_advance`, `usually_pays_in_full` | Whole number |
   | Everything else | Decimal number |

   `minimum_payments` has 313 blanks: leave them as null. They're genuinely missing, not zero.
4. **Home → New Source → Text/CSV** and repeat for `segments.csv`, `metrics.csv`, `segment_profile.csv` and `k_selection.csv`.
   Check that every `..._id` column and `k` are **Whole number**, and that `z_score`, `segment_mean`, `overall_mean`, `inertia` and `silhouette` are **Decimal number**.
5. **Home → Close & Apply.**

**Check:** in the Data view, `customers` has 8,949 rows and `segments` has 6.

---

## Part 2: Build the data model

1. Open **Model view** (the third icon on the left).
2. Power BI may have created relationships automatically. Make sure exactly these three exist, and delete any others:

   | From (many) | To (one) | Cardinality | Cross-filter direction |
   |---|---|---|---|
   | `customers[segment_id]` | `segments[segment_id]` | Many-to-one | Single |
   | `segment_profile[segment_id]` | `segments[segment_id]` | Many-to-one | Single |
   | `segment_profile[metric_id]` | `metrics[metric_id]` | Many-to-one | Single |

   To create one: drag the column from one table onto the matching column in the other, then double-click the line to check its settings.
   `k_selection` stays unconnected; it's only used on the Method page.
3. **Sort segments in persona order, not alphabetically.** In **Data view**, select `segments[segment_name]` → **Column tools → Sort by column → segment_id**.
4. **Sort metrics the same way.** Select `metrics[metric]` → **Sort by column → metric_id**.
5. **Hide technical columns** from report authors: in Model view, right-click and choose **Hide in report view** for every `segment_id` and `metric_id` column in the fact tables (`customers`, `segment_profile`).
6. **Format columns.** In **Column tools**:
   - `balance`, `purchases`, `oneoff_purchases`, `installment_purchases`, `cash_advance`, `credit_limit`, `payments`, `minimum_payments`: **Currency**, 0 decimals
   - `utilization`, `purchases_frequency`, `cash_advance_frequency`, `full_payment_rate`: **Percentage**, 0 decimals

**Why a star schema?** `customers` is the fact table; `segments` and `metrics` are dimensions. Filtering on `segments` flows to both `customers` and `segment_profile`, so a single segment slicer drives every visual.

---

## Part 3: Apply the theme and set up pages

1. **View → Themes → Browse for themes** → select `DataKritii_theme.json`.
   Pages get the ivory background, visuals get white cards, and the colour palette starts with the segment colours.
2. Rename **Page 1** to `Overview`, and add four more pages: `Segment profiles`, `Segment explorer`, `Personas & actions`, `Method`.
3. Keep the default page size (16:9).

**Segment colours.** Use these everywhere, so a segment looks the same on every page:

| Segment | Hex |
|---|---|
| Transactors | `#2E7D5B` |
| High-limit spenders | `#2C3E50` |
| Light users | `#95A5A6` |
| Heavy all-rounders | `#D4A20B` |
| Near-limit revolvers | `#B9603A` |
| Cash-advance reliant | `#7B5EA7` |

---

## Part 4: Create the measures

1. **Home → Enter data**, name the table `_Measures`, and click **Load**. This gives all measures one tidy home.
2. Select `_Measures` in the Data pane, then **Home → New measure**.
3. Open `measures.dax` in Notepad. Copy **one** measure at a time: everything from the name to the end of its expression, for example
   ```
   Share of Customers =
   DIVIDE ( [Customers], CALCULATE ( [Customers], REMOVEFILTERS ( segments ) ) )
   ```
   Paste it into the formula bar and press **Enter**.
4. With the measure selected, set the format from the comment above it in `measures.dax` (**Measure tools → Format**).
5. Repeat for every measure. Once they're all in, delete the default `Column1` from `_Measures`; its icon changes to the calculator symbol.

**Key DAX ideas used here**
- **`REMOVEFILTERS(segments)`** ignores the segment filter, so `Share of Customers` divides by all customers even when one segment is selected.
- **`SELECTEDVALUE`** returns the segment's text when exactly one segment is selected, and a fallback otherwise. It powers the persona cards.
- **Two utilization measures.** `Median Utilization` is the typical customer; `Portfolio Utilization` is total balance ÷ total limit, which weights big accounts more. Both are useful, and they answer different questions.

---

## Part 5: Build the pages

The layout sketches show roughly where each visual goes.

### Page 1: Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│ Credit card customer segments            [subtitle: data, method]    │
├────────────┬────────────┬────────────┬────────────┬──────────────────┤
│ Customers  │ Segments   │ Median     │ % using    │ % usually pay    │
│ 8,949      │ 6          │ utiliz.    │ cash adv.  │ in full          │
├────────────┴────────────┴─────┬──────┴────────────┴──────────────────┤
│ Customers by segment (bars)   │ Share of customers vs share of       │
│                               │ balance (clustered bars)             │
├───────────────────────────────┴──────────────────────────────────────┤
│ Key insight (text box)                                               │
└──────────────────────────────────────────────────────────────────────┘
```

1. **Title:** Insert → Text box: *Credit card customer segments*. Underneath, a smaller line: *8,949 cardholders · 6 months of behaviour · K-means clustering*.
2. **KPI cards:** five **Card** visuals with `Customers`, `Segments`, `Median Utilization`, `% Using Cash Advance` and `% Usually Pay in Full`.
   Rename each one's label (Format → Callout value / Category label) to plain words, e.g. *Customers*, *Typical utilization*.
3. **Customers by segment:** **Clustered bar chart**. Y-axis `segments[segment_name]`, X-axis `Customers`.
   - Sort by `segment_name` ascending (… → Sort axis), so the persona order applies.
   - Colour each bar by its segment: **Format → Bars → Colors → fx → Format style: Field value → What field: `Segment Color`**.
   - Turn on **Data labels**.
4. **Share of customers vs share of balance:** **Clustered bar chart**. Y-axis `segment_name`; X-axis `Share of Customers` and `Share of Balance`.
   Colour the two series charcoal `#2C3E50` and amber `#D4A20B`.
5. **Key insight text box:**
   > The two cash-using segments, *Cash-advance reliant* and *Heavy all-rounders*, are 39% of customers but hold 69% of all balances.
   > *Near-limit revolvers* (13% of customers) use a median 86% of their limit.

**Check your numbers:** Customers 8,949 · Segments 6 · Median utilization 30% · % using cash advance 48% · % usually pay in full 9%.

### Page 2: Segment profiles

```
┌──────────────────────────────────────────────────────────────────────┐
│ How each segment differs from the average customer                   │
├──────────────────────────────────────────────────────────────────────┤
│ Heatmap matrix: rows = metrics, columns = segments, values = z-score │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│ How to read: +1.0 = one standard deviation above average             │
└──────────────────────────────────────────────────────────────────────┘
```

1. **Matrix** visual. Rows: `metrics[metric]`. Columns: `segments[segment_name]`. Values: `Profile Z-Score`.
2. Turn off totals: Format → **Row subtotals** off, **Column subtotals** off.
3. **Heatmap colouring:** Values → `Profile Z-Score` → **Conditional formatting → Background color**.
   - Format style: **Gradient**, and tick **Add a middle color**
   - Minimum: Number **−1.5**, colour `#2C6E9E` (blue)
   - Center: Number **0**, colour `#FFFFFF`
   - Maximum: Number **1.5**, colour `#B9603A` (rust)
4. Format → Values: 1 decimal place, centred. Widen the columns so the segment names fit (Format → Column headers → Text wrap on).
5. **Tooltip (optional, worth it):** add `Profile Segment Mean` and `Profile Overall Mean` to the visual's **Tooltips** well, so hovering shows the actual values.
6. **Explanation text box:** *Each cell shows how far the segment's average is from the overall average, in standard deviations. Rust = above average, blue = below.*

**Check your numbers:** Transactors / Full-payment rate = **+2.2**; Near-limit revolvers / Utilization = **+1.1**; Cash-advance reliant / Purchase frequency = **−1.1**.

### Page 3: Segment explorer

```
┌───────────────────────────┬──────────────────────────────────────────┐
│ Segment slicer (tiles)    │ Selection summary (card)                 │
├───────────────────────────┴───────────────┬──────────────────────────┤
│ Scatter: pca_1 × pca_2, coloured by       │ Utilization distribution │
│ segment                                   │ (column chart of bins)   │
│                                           │                          │
├───────────────────────────────────────────┴──────────────────────────┤
│ Least typical customers (table, sorted by distance_to_centre)        │
└──────────────────────────────────────────────────────────────────────┘
```

1. **Slicer:** field `segments[segment_name]`. Format → Slicer settings → Style: **Tile**; Selection: **Multi-select with Ctrl** on, **Show "Select all"** on.
2. **Selection summary:** a **Card** with the `Selection Summary` measure. It reads, e.g., *Near-limit revolvers: 1,153 customers (13% of all)*.
3. **Scatter chart:** X-axis `customers[pca_1]` (set to **Don't summarize**), Y-axis `customers[pca_2]` (**Don't summarize**), Legend `segments[segment_name]`, Values `customers[customer_id]`.
   - Format → **Markers → Colors**: set each segment's colour from the table in Part 3.
   - Axis titles: X *Buying and paying off ← → Borrowing and cash*; Y *Overall activity and size*.
   - With 8,949 points, Power BI may show a sample. That's fine for the picture.
4. **Utilization distribution:** in the Data pane, right-click `customers[utilization]` → **New group** → Group type **Bin**, bin size **0.1**.
   Then a **Clustered column chart**: X-axis `utilization (bins)`, Y-axis `Customers`.
5. **Least typical customers:** **Table** with `customer_id`, `segment_name`, `balance`, `credit_limit`, `utilization`, `cash_advance`, `distance_to_centre`.
   Sort by `distance_to_centre` descending. These customers sit far from their segment's centre, and they're the ones whose segment label fits least well.

**Try it:** click *Near-limit revolvers* in the slicer. The scatter, histogram and table all filter to that segment, and the histogram shifts to the right.

### Page 4: Personas & actions

```
┌────────────────────────────────┬─────────────────────────────────────┐
│ Segment slicer (tiles,         │ Selected Segment (big card)         │
│ single select)                 │ Selection Summary                   │
├────────────────────────────────┴─────────────────────────────────────┤
│ Who they are: Selected Description                                   │
│ What to do:   Selected Action            Risk view: Selected Risk    │
├──────────────────────────────────────────────────────────────────────┤
│ Segment vs all customers (table): 4 metrics × 2 columns              │
└──────────────────────────────────────────────────────────────────────┘
```

1. **Slicer:** `segments[segment_name]`, Style **Tile**, Selection → **Single select** on.
2. **Big card:** **Card** with `Selected Segment`; callout font 28.
3. **Card** with `Selection Summary` beneath it.
4. **Persona text:** a **Card (new)** or **Multi-row card** with `Selected Description`, `Selected Action` and `Selected Risk View`.
   Label them *Who they are*, *What to do* and *Risk view*. Turn on word wrap.
5. **Segment vs all customers:** build a **Table** with the measures in pairs:
   `Median Utilization`, `Median Utilization (All)`, `% Using Cash Advance`, `% Using Cash Advance (All)`, `% Usually Pay in Full`, `% Usually Pay in Full (All)`, `Avg Purchases`, `Avg Purchases (All)`.
   Rename the columns (double-click in the Values well) to *Utilization: segment*, *Utilization: all*, and so on.
   *Tidier option:* a **Clustered bar chart** per metric, with the segment value in its colour and the "All" value in grey.

**Check your numbers** (select *Cash-advance reliant*): 2,390 customers (27% of all) · median utilization 64% vs 30% · % using cash advance 100% vs 48% · % usually pay in full 0% vs 9%.

### Page 5: Method

```
┌──────────────────────────────────┬───────────────────────────────────┐
│ Inertia by k (line chart)        │ Silhouette by k (line chart)      │
├──────────────────────────────────┴───────────────────────────────────┤
│ How the segments were built (text)  │ Limitations (text)             │
└──────────────────────────────────────────────────────────────────────┘
```

1. **Line chart:** X-axis `k_selection[k]` (set to **Don't summarize**; Format → X-axis → Type **Categorical**), Y-axis `inertia`.
   In the **Analytics** pane (magnifying-glass icon) → **X-axis constant line** at **6**, labelled *Chosen*.
2. **Line chart** the same way for `silhouette`, with the Y-axis from 0 to 0.4 so the flatness is visible.
3. **How the segments were built (text box):**
   > 10 behavioural features (6 amounts on a log scale, 3 frequencies, utilization), standardised. K-means with k = 6.
   > The silhouette score is low (≈ 0.22) and flat from 3 to 10 segments: customers sit on a continuum, not in separate clouds.
   > k = 6 was chosen for business usefulness: it separates near-limit revolvers, whom a 5-segment solution merges with low-utilization spenders.
   > Stability: re-running on different random starts and on 80% subsets gives near-identical segments (adjusted Rand index 0.97–1.00).
4. **Limitations (text box):** one 6-month snapshot from one issuer, no outcome data (profit, defaults), so actions are hypotheses to test; fuzzy segment boundaries.
5. Add a small text line with the link to the GitHub repo and notebook.

---

## Part 6: Polish

1. **Page navigation:** Insert → Buttons → **Navigator → Page navigator**. Put it at the top of every page, or on page 1 only.
2. **Consistent titles:** every visual gets a plain-language title that says what it shows.
3. **Edit interactions:** on the Overview page, select the first bar chart → **Format → Edit interactions**, and make sure clicking a segment *filters* the other visuals rather than just highlighting.
4. **Alt text** (Format → General → Alt text) for each chart, for accessibility.
5. **Check every page** with no segment selected and with each segment selected.

---

## Part 7: Save and share

1. **Save** the report as `powerbi/credit_card_segments.pbix`.
2. **Export a PDF:** File → Export → **Export to PDF**. Save it as `powerbi/credit_card_segments.pdf`.
3. **Screenshots:** for each page, Windows key + Shift + S. Save them in `reports/figures/powerbi_1_overview.png`, `powerbi_2_profiles.png`, and so on.
4. **Optional: a short GIF or video walkthrough** of clicking through the segments, using a free screen recorder such as ScreenToGif, or the Snipping Tool's video mode. A 60–90-second video also works well on the DataKritii YouTube channel.
5. **Commit and push:**
   ```bash
   git add .
   git commit -m "Add Power BI report, PDF export and screenshots"
   git push
   ```
6. In the project `README.md`, replace the placeholders under **Power BI report** with your screenshots.

---

## Interview checklist

You should be able to explain:
- Why the amounts were log-transformed and every feature standardised before K-means
- Why k = 6, even though the silhouette score slightly prefers 5 (the near-limit revolvers)
- What a z-score in the profile matrix means, and why the heatmap uses one
- The difference between `Median Utilization` and `Portfolio Utilization`
- What `REMOVEFILTERS` and `SELECTEDVALUE` do in your measures
- How you'd keep the segments up to date in production: re-assign customers monthly, refit yearly, track segment migration
