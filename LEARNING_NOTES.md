# Learning Notes

Personal notes I kept while building this project, phase by phase. Not
polished — kept mostly as I wrote them, including the bits where I was
still confused or wrong about something, because that's more honest than
cleaning it up after the fact.

I used AI assistance for implementation speed on a lot of the boilerplate
(parsing logic, header-detection code, notebook scaffolding). These notes
are where I worked through actually understanding *why* things were built
the way they were, not just accepting that they worked.

---

## Phase 0 — Scoping

Before writing anything I had to decide how much of the raw data to
actually use. There's 34 files going back to 1985, and my first instinct
was "use everything, more data is better." Had to talk myself out of
that — the pre-2021 price files are in a completely different format, and
the sector taxonomy changed around 2016, so mixing eras in would either
break the parser or quietly merge things that aren't actually the same
category. Scoped to 2021-2025 instead and wrote down *why* rather than
just doing it silently. Feels like a small thing but I think this was
actually the first real "data science judgment call" of the project,
before any code.

## Phase 1 — Ingestion

This was more annoying than I expected. Assumed `pd.read_excel()` would
just work. It didn't — header rows aren't always row 0, and one file
(Market Indices - Daily) has its header split across *two* rows. Spent a
while just opening files raw with `header=None` and looking at what was
actually in the first 8-10 rows before writing any parsing logic. Lesson
I want to remember: look at the data before you write code for it, don't
assume the first attempt will work.

Still not 100% sure I'd catch every future format quirk with the current
`excel_parser.py` heuristic (it scores rows by "how many non-numeric
cells does this row have") — I can see how that could misfire on a file
I haven't looked at yet. Something to keep in mind if this pipeline ever
needs to run on a new export.

## Phase 2 — Cleaning / tidy data

Learned the actual term for what I was doing here — "tidy data," one
variable per column, one observation per row. The wide-format files
(index name as a column, one column per date) needed melting before
`groupby` would work on them properly. Also had to think about *why*
`errors="coerce"` is the right call for numeric parsing instead of just
crashing or filling with 0 — a missing value and a real zero mean
different things (e.g. "market closed" isn't a 0-volume trading day,
it's not a trading day at all).

## Phase 3 — Feature engineering

Rolling 20-day return and volatility features, drawdown. I know *why*
sqrt(252) is used to annualize volatility now — variance scales linearly
with time so std scales with sqrt(time) — but I want to be honest that I
didn't derive that myself, I looked it up and then made sure I actually
understood it rather than just pasting the formula. Also noticed I
compute both `daily_return` and `log_return` but only actually use
`daily_return` downstream — small inconsistency I should either fix or
be ready to explain if anyone asks why `log_return` exists at all.

## Phase 4 — Regime detection (KMeans)

The part I spent the most time actually understanding rather than just
using. Two things that weren't obvious to me at first:

1. Why you have to standardize features before KMeans — because it uses
   Euclidean distance, and without scaling, whichever feature has the
   biggest raw numbers dominates the distance calculation regardless of
   whether it's actually the most informative one.
2. That the model doesn't "know" what a crisis is — it just groups
   similar days together. A separate rule (`label_cluster`) is what
   turns cluster numbers into "Crisis / Sell-off" after the fact, based
   on each cluster's average return/volatility.

Validated against 4 known real events (2022 default, 2022 political
crisis, COVID, Easter Sunday attacks). 3 out of 4 landed correctly. The
4th (Easter Sunday) didn't, and my best guess why is that a 20-day
rolling window is too slow to catch a shock that resolved within days —
but I want to flag that as a guess, not something I've actually proven.

Biggest thing I'd change with more time: this treats every day as
independent, no concept of regimes persisting over time. A Hidden Markov
Model would model that properly. Didn't build it here, but I understand
why it'd be the natural next step, not just "cite as a future extension"
because that's a checkbox to tick.

## Phase 5 — Event study

This is the most "textbook finance" part of the project. Had to
understand cumulative abnormal return (CAR) as a concept before any of
the code made sense — actual return minus what you'd expect it to be if
the event hadn't happened, summed over a window around the event.

Found a genuinely bad data point while testing this — one dividend event
came out with a 98,500% CAR, which is obviously not real. Traced it to
one bad price value in the raw file. Fixed it with a general rule (drop
any day where the return is more than 50% in magnitude) rather than just
deleting that one row, because a specific-row fix doesn't generalize and
kind of looks like cherry-picking if someone ever checks.

Ran a proper t-test on this afterward instead of just eyeballing the
average. Mean CAR came out significantly negative. Had to actually think
about why a t-test is valid here even though individual CARs clearly
aren't normally distributed (fat-tailed histogram) — it's the Central
Limit Theorem, the test only needs the *sampling distribution of the
mean* to be roughly normal, which holds with ~1,000 events regardless of
individual-event skew.

## Phase 6 — Cross-signal panel

Wanted to check whether foreign investor flow relates to market regime.
Almost got this wrong: my first pass assumed foreign investors sell
during Crisis regimes, wrote that up, then actually ran the numbers and
found the *mean* said the opposite (net buying). Dug further and found
that was two outlier billion-rupee months skewing the mean — the median
was close to a 50/50 split, no real tilt either way. Also checked
foreign flow before vs. after transitions into a Crisis regime hoping to
find an early-warning signal — came back basically a coin flip (52%),
no real signal.

Kept this in the notebook instead of quietly rewriting it to sound more
interesting, because catching my own wrong first read felt like the most
useful thing in that whole notebook, more useful than a clean-looking
result would have been.

## Phase 7 — Tests

Wrote these as regression guards for the actual bugs I found, not
generic "does the code run" tests — e.g. one test specifically asserts
no event should ever again produce a >100% CAR, because that's the exact
shape of bug that happened once already. Realized partway through that
this is a different thing from the runtime validation checks in
`validation.py` — tests check the *code*, validation checks *this run's
data*, and I needed both because a new/different raw export could break
an invariant without any code changing at all.

## Phase 8 — Dashboard

Streamlit. Learned `@st.cache_data` isn't optional-nice-to-have — without
it, the whole script re-runs top to bottom on every single click, which
would re-read every parquet file from disk each time. Chose the simple
if/elif page-routing pattern over Streamlit's native multi-page folder
structure since the project's small enough that one file is still easy
to scan — would switch to the native pattern if this grew past a
handful of pages.

## Phase 9 — Wrapping up

Went back through the whole thing end to end after it was "done" and
made myself explain each piece out loud, file by file, like I was being
asked about it in an interview. Found a few things I couldn't cleanly
explain on the first pass (the `log_return`/`daily_return` inconsistency
from Phase 3, the `test_car_by_sign` function that actually splits by
size not sign) — better to know that now than get caught by it later.

Still want to come back to:
- actually run a silhouette score across a few values of k instead of
  just picking k=4 for interpretability
- read more on Granger causality before I try the lead-lag foreign-flow
  question properly instead of the informal before/after check I did
