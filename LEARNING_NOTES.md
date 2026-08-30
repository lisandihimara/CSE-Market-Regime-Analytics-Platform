# Learning & Development Notes

These are my personal learning and development notes for the **CSE Market Regime & Sector Rotation Dashboard**. I kept them as a record of how I worked through the project phase by phase, including things I initially misunderstood, implementation problems I encountered, decisions I had to make, and areas that still need improvement.

This project was developed with **AI assistance**. I used AI extensively as a development assistant, particularly for boilerplate implementation, parsing logic, debugging, and notebook scaffolding. However, I did not want the generated implementation to be the end of the process. After each major component, I reviewed the code, ran the pipeline, investigated unexpected results, studied the underlying concepts, and worked through why the implementation was designed that way.

These notes are therefore not intended to claim that every line of code was written manually. They document the process of turning an AI-assisted implementation into something I can understand, evaluate, explain, and continue developing myself.

---

## Phase 0 — Project Scoping

The original CSE dataset contained 34 statistics files covering a much longer historical period, going back to 1985. My first instinct was that using all available data would automatically make the project better.

After inspecting the files, I realized that this was not a realistic assumption.

The historical price files were not stored in one consistent format. The pre-2021 archives use structurally different layouts, and the sector classification system also changed over time. Simply combining everything would have required additional decisions about historical taxonomy mapping and multiple generations of file formats.

I therefore scoped the main analysis to **2021–2025**.

This became one of the first important data-science decisions in the project: more data is not necessarily better if the additional data is not comparable or requires assumptions that have not been properly justified.

The selected period also provides useful market conditions for the analysis, including the COVID-19 period, the 2022 sovereign default and political/economic crisis, and the subsequent recovery.

### What I learned

- Data availability and data usability are different things.
- Scope should be decided based on analytical comparability, not simply the amount of available data.
- Historical format changes can become a methodological issue, not just a programming problem.
- A scope decision should be documented rather than silently applied.

### Still to improve

If this project were expanded, I would investigate the older price formats separately instead of trying to force them into the current pipeline.

---

# Phase 1 — Data Ingestion

This was one of the first areas where the real-world data was much messier than I expected.

Initially, I assumed that loading an Excel file would mostly be:

```python
pd.read_excel(...)
```

That assumption did not hold consistently.

Some CSE files have title or metadata rows before the actual header. The position of the header can differ between files, and the **Market Indices - Daily** file contains a header structure spread across two rows.

I therefore spent time opening the files using:

```python
pd.read_excel(..., header=None)
```

and inspecting the first several rows before writing the parsing logic.

This changed how I think about data ingestion. The parser should be based on what the source data actually looks like rather than on an assumption about how an Excel file "should" look.

### Header detection

The project uses a reusable header-detection utility in:

```text
src/ingestion/excel_parser.py
```

The current heuristic scores candidate rows based partly on the number of non-numeric cells.

This works for the files currently handled by the project, but I do not consider it a perfect solution for arbitrary future CSE exports.

A heuristic that works on the current data can still fail when the source format changes.

### Data-quality issues discovered during ingestion

I encountered several format-specific issues, including:

- Header rows appearing at different positions.
- A two-row header structure in the daily market-index data.
- Column positions changing between historical formats.
- A title row being incorrectly identified as a sector header because it contained the word `"sector"`.

The sector-parser problem was particularly useful because it showed me why substring matching can be dangerous when identifying structural elements in messy data. The parser was changed to require a more specific/exact match instead.

### What I learned

- Inspect raw data before designing a parser.
- `header=None` is useful when the structure of a spreadsheet is unknown.
- A reusable parser can reduce duplicated ingestion logic.
- Heuristics should be treated as assumptions that can fail.
- Data ingestion is part of the analytical workflow, not just preparation before the "real" analysis.

### Still to improve

The header-detection heuristic could be replaced or supplemented with more explicit file-specific rules or stronger structural validation if new CSE exports are added.

---

# Phase 2 — Cleaning and Tidy Data

During this phase I learned the practical meaning of **tidy data** rather than only knowing the definition.

The principle I used was:

> One variable per column and one observation per row.

Some CSE files were provided in wide formats, with dates spread across columns. Those structures were not convenient for grouping, joining, or time-series analysis.

They therefore needed to be converted into long/tidy form using operations such as `melt()`.

The shared cleaning functions are located in:

```text
src/cleaning/tidy.py
```

### Numeric coercion

One decision that I had to understand was why numeric conversion should sometimes use:

```python
errors="coerce"
```

rather than simply failing.

The reason is that source files can contain values that are not genuine numbers, including placeholders such as:

```text
Market Closed Due To COVID -19
```

Turning such a value into `0` would be misleading.

A missing value and a genuine zero have different meanings.

For example:

- `0` volume can represent a genuine zero.
- A market-closed placeholder represents the absence of a trading observation.

This distinction matters later when calculating returns, volatility, or aggregations.

### Validation

I also added post-load validation utilities in:

```text
src/utils/validation.py
```

These checks are intended to identify problems such as:

- unexpected null values
- duplicate keys
- future dates
- invalid labels
- malformed observations

### What I learned

- Cleaning is not simply "removing bad rows."
- Missing, zero, and invalid values can have different meanings.
- Tidy structure makes downstream analysis easier.
- Validation should happen after ingestion rather than assuming the loader worked correctly.

---

# Phase 3 — Feature Engineering

The next stage transformed cleaned market data into variables that could be used for analysis and regime detection.

The main features include:

- Daily return
- Log return
- Rolling return
- Rolling volatility
- Drawdown

A 20-trading-day rolling window is used for several features.

### Annualized volatility

One formula I had to understand rather than simply copy was the annualized volatility calculation using:

```text
sqrt(252)
```

The reasoning is that variance scales approximately linearly with time under the usual return-scaling assumptions, while standard deviation therefore scales with the square root of time.

So:

```text
Annualized volatility ≈ Daily volatility × √252
```

I initially knew the formula but not the reasoning behind it. I looked into the derivation and then connected it to the variance-scaling concept.

### Daily return vs log return

I also noticed an inconsistency in the implementation.

The pipeline calculates both:

```text
daily_return
log_return
```

but the downstream regime model currently uses `daily_return`.

This is not something I want to hide.

Possible future improvements are:

- remove `log_return` if it is unnecessary, or
- use it deliberately in an appropriate analysis.

### What I learned

- Feature engineering should have an analytical reason behind each feature.
- Rolling statistics introduce a time-window assumption.
- Annualization is not just a multiplier to memorize.
- Features that are calculated but never used should be reviewed rather than left unexplained.

---

# Phase 4 — Market Regime Detection with KMeans

This was the part of the project where I spent the most time trying to understand the underlying method rather than simply using the implementation.

The model uses features such as:

- return
- volatility
- drawdown

and applies **KMeans clustering** to identify groups of days with similar market characteristics.

## Why standardization is necessary

KMeans uses distance calculations, specifically Euclidean distance in the standard implementation.

If features are measured on very different scales, a feature with larger numerical magnitude can dominate the distance calculation.

Standardization puts the features onto a comparable scale before clustering.

This helped me understand that scaling is not an arbitrary preprocessing step. It directly affects how KMeans measures similarity.

## KMeans does not know what a "crisis" is

This was one of the most important concepts I learned.

KMeans does not receive labels such as:

```text
Bull
Crisis
Recovery
```

It only identifies groups of observations based on their feature similarity.

The numerical cluster labels themselves have no economic meaning.

A separate labelling step, such as:

```text
label_cluster
```

interprets the clusters based on characteristics such as average return and volatility.

Therefore:

```text
KMeans cluster 0
```

does not inherently mean:

```text
Crisis
```

The economic interpretation comes afterward.

## Historical-event comparison

I compared the detected regimes against four known historical events:

- COVID-19 market shock
- 2022 sovereign default
- 2022 political/economic crisis
- Easter Sunday attacks

Three of the four events were captured in the expected crisis/sell-off regime.

The Easter Sunday event did not align in the same way.

My current hypothesis is that the 20-day rolling features may have been too slow to reflect a shock that was concentrated over a relatively short period. However, I consider this a **hypothesis rather than a proven explanation**.

A shorter rolling window or alternative feature design would need to be tested before making that conclusion.

## Limitation of KMeans

KMeans treats observations according to their feature values but does not explicitly model temporal persistence.

A market regime normally has some degree of persistence:

```text
Crisis → Crisis → Crisis
```

rather than every day being an independent state.

A **Hidden Markov Model (HMM)** would be a natural extension because it explicitly models transitions and persistence between hidden states.

I did not implement an HMM in this project because the goal was to build a transparent and understandable practice project rather than maximize model complexity.

### What I learned

- Unsupervised learning does not provide economic labels automatically.
- Feature scaling affects distance-based clustering.
- Cluster interpretation is separate from cluster formation.
- Historical events can provide useful sanity checks, but they are not equivalent to formal ground-truth validation.
- A more complicated model is not automatically a better model for a given project.

### Still to improve

I want to calculate silhouette scores across several values of `k` rather than relying mainly on interpretability when selecting `k = 4`.

---

# Phase 5 — Dividend Event Study

The event-study component was the most finance-oriented part of the project.

The objective was to examine stock-price reactions around dividend ex-dates.

The key concept I had to understand was **abnormal return**.

Conceptually:

```text
Abnormal Return
= Actual Return − Expected Return
```

The abnormal returns are then accumulated over the event window to obtain:

```text
Cumulative Abnormal Return (CAR)
```

CAR therefore represents the cumulative price reaction relative to the expected market-related movement over the selected event window.

## Unexpected data problem

During testing, one dividend event produced an approximately:

```text
98,500% CAR
```

This was clearly implausible.

Instead of deleting that particular event manually, I traced the problem back to an implausible daily price movement in the source data.

I introduced a general return-quality rule that excludes daily returns beyond ±50% from the event-study calculation.

I prefer this approach to deleting one specific row because a rule is reproducible.

However, the **50% threshold itself is a heuristic**. It should not be treated as a universally correct financial-data threshold. A more systematic price-error detection method would be preferable in a future version.

## Statistical testing

After calculating CAR, I used a one-sample t-test to examine whether the mean CAR was statistically distinguishable from zero.

The hypotheses are conceptually:

```text
H0: Mean CAR = 0

H1: Mean CAR ≠ 0
```

The resulting mean CAR was significantly negative in the current analysis.

I also noticed that the individual CAR distribution is fat-tailed rather than perfectly normal.

This led me to investigate why a t-test on the mean can still be useful with a large number of observations.

The Central Limit Theorem provides an approximate justification for the sampling distribution of the mean becoming more normally distributed as sample size increases, under appropriate conditions.

However, I do not want to overstate this point. Large sample size does not automatically remove every problem. Independence, extreme observations, event clustering, and other assumptions still matter.

### Important limitation

The event study uses a simplified market-adjusted model with:

```text
Beta = 1
```

against the ASPI.

A more rigorous market model would estimate beta separately for each stock using an estimation window.

Another important limitation is that the analysis does not explicitly correct for the **mechanical ex-dividend price adjustment**. A price decline around an ex-dividend date is not automatically evidence of a negative market reaction.

### What I learned

- Event studies require a clear definition of the event and event window.
- CAR is not simply the stock's cumulative return.
- Data-quality errors can completely distort an event study.
- Statistical significance and economic significance are different concepts.
- Statistical tests should be interpreted together with their assumptions and limitations.

---

# Phase 6 — Cross-Signal Analysis

I wanted to investigate whether foreign investor activity appeared to differ across market regimes.

My initial assumption was:

> Foreign investors would probably be net sellers during crisis regimes.

I initially wrote my interpretation around that expectation.

When I actually examined the results, the mean foreign flow during crisis periods appeared to indicate net buying instead.

Instead of accepting that result immediately, I investigated the distribution further.

I found that a small number of very large monthly observations were strongly affecting the mean.

The median was much closer to a 50/50 pattern, suggesting that there was no strong evidence of a consistent foreign-buying tendency during crisis periods.

## Regime-transition analysis

I also looked at foreign flow around transitions into crisis regimes to see whether it could act as an early-warning signal.

The result was approximately:

```text
52%
```

which was essentially close to a coin-flip interpretation rather than a convincing predictive signal.

I therefore did not present foreign investor flow as a reliable early-warning indicator.

### Important lesson

This was one of the most useful analytical lessons in the project.

I had a hypothesis first, but the data did not support the simple story I expected.

Instead of changing the interpretation to make the result more interesting, I kept the unexpected result and investigated why the mean and median differed.

### Statistical-grain issue

The foreign-flow data is monthly, while much of the market data is daily.

Broadcasting a monthly value across every daily row can create a misleading number of apparent observations.

For example, one monthly foreign-flow observation repeated across approximately 20 trading days is still **one monthly observation**, not 20 independent foreign-flow observations.

This is a form of pseudo-replication risk.

The project therefore documents the grain mismatch explicitly and uses caution when interpreting the combined panel.

### What I learned

- A hypothesis should not determine the result.
- Means can be strongly affected by outliers.
- Median and distributional inspection can change the interpretation of a result.
- Different datasets can have different statistical grains.
- Joining data at a common row level does not automatically make the observations statistically independent.

---

# Phase 7 — Testing and Validation

I initially thought testing mainly meant checking whether the program ran successfully.

This project changed that understanding.

There are two different ideas in the pipeline:

### Runtime data validation

Located in:

```text
src/utils/validation.py
```

These checks examine the current data and look for things such as:

- duplicate keys
- missing values
- invalid dates
- unexpected labels
- structural problems

### Automated software tests

Located in:

```text
tests/test_pipeline.py
```

These tests check whether the code continues to behave as expected.

This distinction became particularly clear when I created regression tests for problems that had actually occurred during development.

For example, one test checks that an event cannot again produce an implausibly large CAR.

The purpose is not simply:

> "Does the program run?"

It is:

> "Does the program continue to satisfy important assumptions after future changes?"

I also discovered that one test function called:

```text
test_car_by_sign
```

was actually splitting observations by **size**, not sign.

That naming/logic mismatch was something I could have easily missed if I only checked whether the test suite passed.

### What I learned

- Data validation and software testing solve different problems.
- Tests can act as regression guards against previously discovered bugs.
- Passing tests does not guarantee that the analysis is statistically correct.
- Test names and test logic should also be reviewed critically.

---

# Phase 8 — Streamlit Dashboard

The dashboard turns the analysis into an interactive application.

The main application is:

```text
app.py
```

The dashboard contains pages for:

- Market Overview
- Sector Rotation
- Foreign Activity
- Company Explorer
- Event Study
- About / Methodology

## Streamlit caching

One useful implementation detail I learned was:

```python
@st.cache_data
```

Without caching, expensive data-loading operations can be repeated unnecessarily when the application reruns.

Since the dashboard reads multiple processed Parquet files, caching the data-loading functions improves the user experience.

I initially thought caching was simply an optional optimization. I now understand that for an interactive data application, avoiding unnecessary repeated data loading can be an important design consideration.

## Page routing

I used a simple conditional page-routing approach rather than Streamlit's native multipage folder structure.

For the current project size, this keeps the application relatively easy to scan.

If the dashboard grows significantly, I would consider switching to a more modular page structure.

### What I learned

- A dashboard is an application layer on top of the analytical pipeline.
- Visualization and data processing should not be treated as the same component.
- Caching can be important for interactive applications.
- Architecture should match the size and complexity of the project rather than adding complexity unnecessarily.

---

# Phase 9 — Final Review and Reflection

After the main implementation was complete, I went through the project again from beginning to end.

Instead of only checking whether the dashboard worked, I tried to explain each component as if someone were asking me about it in an interview.

This exposed several things I had initially accepted without fully understanding.

Examples included:

- Why KMeans requires feature scaling.
- Why cluster numbers do not automatically have economic meaning.
- Why the `log_return` feature existed even though downstream analysis used `daily_return`.
- Why monthly foreign-flow values should not be treated as independent daily observations.
- The difference between runtime validation and regression testing.
- The mismatch between the `test_car_by_sign` name and what the test actually did.

This review was important because it showed me that **working code and understood code are not the same thing**.

The project is only useful to me as a learning experience if I can explain the reasoning behind the implementation.

---

# Current Limitations

The main limitations I currently recognize are:

1. Daily price analysis is limited to 2021–2025.
2. Older CSE price archives use different formats and are not currently integrated.
3. Sector classification changes across historical periods are not cross-mapped.
4. Regime detection uses KMeans rather than a temporal regime-switching model.
5. The choice of `k = 4` should be evaluated more systematically.
6. Regime labels are interpreted from cluster characteristics rather than learned from ground-truth labels.
7. Historical-event comparison is a sanity check, not formal supervised validation.
8. The event study assumes beta = 1.
9. The event study does not explicitly model the mechanical ex-dividend price adjustment.
10. The 50% return filter is a heuristic for identifying implausible price movements.
11. Foreign-flow data has a monthly statistical grain while much of the market panel is daily.
12. The current cross-signal analysis does not establish a causal relationship between foreign flow and regime changes.

---

# Things I Want to Improve

The following are deliberately left as future work rather than pretending they have already been solved.

## 1. Evaluate the number of clusters

Run KMeans across several values of `k` and compare:

- Silhouette score
- Cluster sizes
- Economic interpretability
- Stability of the resulting regimes

The goal is to understand whether `k = 4` is actually supported by the data or mainly chosen for interpretability.

## 2. Compare KMeans with an HMM

An HMM could explicitly model:

- hidden market states
- transition probabilities
- regime persistence

This would provide a more appropriate temporal comparison with the current KMeans approach.

## 3. Improve the event-study model

Replace the simplified beta = 1 assumption with a market model using estimated stock-specific beta.

## 4. Investigate ex-dividend effects

Separate the mechanical dividend adjustment from the abnormal component of the price movement.

## 5. Extend historical data

Investigate the older CSE price archives and determine whether their different structures can be integrated without making unjustified assumptions.

## 6. Study foreign-flow lead/lag relationships properly

Before implementing Granger causality or another lead-lag method, I want to understand the assumptions and stationarity requirements properly rather than applying a statistical test simply because it is a commonly cited method.

---

# Key Lessons From the Project

The most important things I learned were not specific Python functions.

### 1. More data is not automatically better

Data has to be comparable and appropriate for the question.

### 2. Inspect before processing

Real-world files rarely behave exactly like clean textbook datasets.

### 3. Machine learning does not automatically produce meaningful labels

KMeans creates groups. The economic interpretation comes afterward.

### 4. Statistical results should challenge assumptions

If the data contradicts my initial expectation, the correct response is to investigate the result rather than change the story.

### 5. Data grain matters

A monthly observation repeated across daily rows does not become multiple independent observations.

### 6. Tests and validation are different

Tests protect the code. Validation checks the current data.

### 7. A working implementation is not the same as understanding

Being able to explain why a method is used is more important than simply being able to run it.

### 8. Limitations should be explicit

A smaller project with clearly stated limitations is more defensible than a larger project built on hidden assumptions.

---

# AI-Assisted Development Approach

AI was used throughout this project as a development assistant.

I used it particularly for:

- Boilerplate implementation
- Excel parsing logic
- Header-detection approaches
- Debugging assistance
- Notebook scaffolding
- Exploring alternative implementation approaches
- Documentation support

I did not treat generated code as automatically correct.

The development process involved reviewing the generated implementation, running it against the actual CSE data, investigating unexpected outputs, identifying bugs, studying the relevant concepts, and making or evaluating changes.

Several of the most useful learning moments came from situations where the initial implementation or interpretation was not correct, including the implausible CAR, the foreign-flow interpretation, the statistical-grain issue, and the test naming/logic mismatch.

For me, the purpose of using AI was therefore not to avoid learning the project. It was to reduce implementation time while using the saved time to understand, test, question, and improve the resulting system.

---

# Final Reflection

This project started as a practical exercise in working with CSE market data and gradually became a broader lesson in how a data-science system is built.

The most valuable part was not the KMeans model or the Streamlit dashboard by itself.

It was learning to move through the complete process:

```text
Raw Data
   ↓
Data Inspection
   ↓
Ingestion
   ↓
Cleaning
   ↓
Feature Engineering
   ↓
Statistical / ML Analysis
   ↓
Validation
   ↓
Testing
   ↓
Dashboard
   ↓
Critical Review
```

I also learned that analytical work does not always produce the result I initially expect. The foreign-flow analysis was a good example: my initial assumption was not supported by the data in the simple way I expected, and investigating that discrepancy taught me more than a result that simply confirmed my hypothesis would have.

There are still several areas I would improve, particularly cluster-selection analysis, temporal regime modelling, the event-study market model, and formal lead-lag analysis.

That is intentional. This project is a learning and portfolio project, not a claim that every part of the market-analysis problem has been solved.
