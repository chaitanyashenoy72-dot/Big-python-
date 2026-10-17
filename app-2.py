import os

import altair as alt
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Stock market awareness survey", page_icon="📈", layout="wide")

DEFAULT_CSV = "response.csv"
ORDER = ["Yes", "No", "Not sure"]
COLORS = ["#1f7a6d", "#c4553a", "#b4bcc7"]
AGE_ORDER = ["Below 18", "18-20", "21-24", "25 and above"]

SHORT = {
    "Have you heard of stock market investment?": "Heard of stock market investment",
    "Do you know what a stock/share is?": "Know what a stock/share is",
    "Are you aware of the NSE and BSE?": "Aware of NSE and BSE",
    "Do you know what a DEMAT account is?": "Know what a DEMAT account is",
    "Are you aware that stock market investment involve risk?": "Aware investing involves risk",
    "Do you know the difference between investing and trading?": "Know investing vs trading",
    "Are you aware that stocks can be bought and sold through online platforms?": "Aware stocks trade online",
    "Do you know that investors can earn through capital appreciation and dividends?": "Know capital appreciation & dividends",
    "Have you ever considered investing in the stock market?": "Have considered investing",
    "Have you or anyone in your family invested in stocks?": "You or family have invested",
    "Do you think you have sufficient knowledge about stock market investments?": "Feel they know enough",
    "Do you think financial education can improve awareness about stock market investment?": "Think financial education helps",
    "Would you consider investing in the stock market in the future?": "Would consider investing in future",
}
AWARENESS = list(SHORT)[:8]
ATTITUDE = list(SHORT)[8:]
Q_FAMILY = "Have you or anyone in your family invested in stocks?"
Q_FUTURE = "Would you consider investing in the stock market in the future?"
Q_ENOUGH = "Do you think you have sufficient knowledge about stock market investments?"
Q_HEARD = "Have you heard of stock market investment?"


def read_one(source):
    df = pd.read_csv(source)
    df.columns = [c.strip() for c in df.columns]
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].astype(str).str.strip().replace("nan", pd.NA)
    return df


def load(sources):
    """Read one or many CSVs and stack them into a single table."""
    frames, problems = [], []
    required = {"Your age", *SHORT}
    for s in sources:
        name = getattr(s, "name", str(s))
        try:
            part = read_one(s)
        except Exception as e:
            problems.append(f"{name}: could not be read ({e})")
            continue
        missing = required - set(part.columns)
        if missing:
            problems.append(f"{name}: missing {len(missing)} expected column(s), skipped")
            continue
        frames.append(part)
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return df, problems


def long_counts(df, questions):
    rows = []
    for q in questions:
        counts = df[q].value_counts()
        for a in ORDER:
            rows.append({"Question": SHORT[q], "Answer": a, "Count": int(counts.get(a, 0))})
    out = pd.DataFrame(rows)
    out["Share"] = out["Count"] / out.groupby("Question")["Count"].transform("sum")
    return out


def stacked_bar(df, questions, sort_by_yes):
    data = long_counts(df, questions)
    yes_order = (
        data[data.Answer == "Yes"].sort_values("Share", ascending=False)["Question"].tolist()
        if sort_by_yes
        else [SHORT[q] for q in questions]
    )
    return (
        alt.Chart(data)
        .mark_bar()
        .encode(
            y=alt.Y("Question:N", sort=yes_order, title=None, axis=alt.Axis(labelLimit=320)),
            x=alt.X("Share:Q", stack="normalize", axis=alt.Axis(format="%"), title=None),
            color=alt.Color("Answer:N", scale=alt.Scale(domain=ORDER, range=COLORS), legend=alt.Legend(orient="top", title=None)),
            order=alt.Order("order:Q"),
            tooltip=["Question", "Answer", "Count", alt.Tooltip("Share:Q", format=".0%")],
        )
        .transform_calculate(order="indexof(['Yes','No','Not sure'], datum.Answer)")
        .properties(height=34 * len(questions) + 40)
    )


# ---------- Data ----------
st.title("What do students know about the stock market?")

with st.sidebar:
    st.header("Data & filters")
    uploads = st.file_uploader(
        "Upload responses CSV (one file with all 60 rows, or several files)",
        type="csv",
        accept_multiple_files=True,
    )
    sources = list(uploads) if uploads else ([DEFAULT_CSV] if os.path.exists(DEFAULT_CSV) else [])
    if not sources:
        st.info(f"Upload one or more CSVs, or place `{DEFAULT_CSV}` next to this file.")
        st.stop()
    df, problems = load(sources)
    for p in problems:
        st.warning(p)
    if df.empty:
        st.error("No usable responses found in the uploaded file(s).")
        st.stop()
    if len(sources) > 1:
        dupes = int(df.duplicated().sum())
        if dupes and st.checkbox(f"Remove {dupes} exact duplicate row(s)", value=True):
            df = df.drop_duplicates(ignore_index=True)
    st.success(f"{len(df)} responses loaded from {len(sources)} file(s)")

    df = df.dropna(subset=["Your age"])
    ages = [a for a in AGE_ORDER if a in df["Your age"].unique()] + sorted(set(df["Your age"]) - set(AGE_ORDER))
    chosen = st.multiselect("Age group", ages, default=ages)
    sort_by_yes = st.toggle("Sort awareness bars by Yes", value=True)

view = df[df["Your age"].isin(chosen)]
if view.empty:
    st.warning("No responses match the selected age groups.")
    st.stop()

n = len(view)
st.caption(f"{n} of {len(df)} responses shown")

# ---------- Headline metrics ----------
pct = lambda q: (view[q] == "Yes").mean()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Responses", n)
c2.metric("Heard of stock investing", f"{pct(Q_HEARD):.0%}")
c3.metric("Feel they know enough", f"{pct(Q_ENOUGH):.0%}")
c4.metric("Would consider investing", f"{pct(Q_FUTURE):.0%}")

# ---------- Charts ----------
tab1, tab2, tab3, tab4 = st.tabs(["Awareness", "Experience & attitude", "Knowledge score", "Family & intent"])

with tab1:
    st.subheader("Awareness questions")
    st.altair_chart(stacked_bar(view, AWARENESS, sort_by_yes), use_container_width=True)

with tab2:
    st.subheader("Experience and attitude")
    st.altair_chart(stacked_bar(view, ATTITUDE, False), use_container_width=True)

with tab3:
    st.subheader("Awareness score (Yes answers out of 8)")
    score = (view[AWARENESS] == "Yes").sum(axis=1).rename("Score")
    hist = score.value_counts().reindex(range(9), fill_value=0).rename_axis("Score").reset_index(name="Respondents")
    st.altair_chart(
        alt.Chart(hist)
        .mark_bar(color=COLORS[0])
        .encode(x=alt.X("Score:O", title="Yes answers"), y=alt.Y("Respondents:Q"), tooltip=["Score", "Respondents"]),
        use_container_width=True,
    )
    st.caption(f"Average score: {score.mean():.1f} out of 8")

with tab4:
    st.subheader("Would consider investing, by family experience")
    grp = (
        view.groupby(Q_FAMILY)[Q_FUTURE]
        .agg(Respondents="size", Yes=lambda s: (s == "Yes").sum())
        .reindex(ORDER)
        .dropna()
        .reset_index()
        .rename(columns={Q_FAMILY: "Family invested"})
    )
    grp["Would invest"] = grp["Yes"] / grp["Respondents"]
    st.altair_chart(
        alt.Chart(grp)
        .mark_bar(color=COLORS[0])
        .encode(
            x=alt.X("Family invested:N", sort=ORDER, title="You or family have invested"),
            y=alt.Y("Would invest:Q", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1]), title="Would consider investing"),
            tooltip=["Family invested", "Respondents", alt.Tooltip("Would invest:Q", format=".0%")],
        ),
        use_container_width=True,
    )

# ---------- Raw data ----------
with st.expander("View responses"):
    st.dataframe(view, use_container_width=True, hide_index=True)
    st.download_button("Download filtered CSV", view.to_csv(index=False), "filtered_responses.csv", "text/csv")

if n < 10 or len(chosen) < len(ages):
    st.caption("Small groups (under 10 responses) are too few to compare reliably.")
