import streamlit as st
import pandas as pd

from longevity import db
from longevity.pipeline import run_weekly
from longevity.report import build_report
from longevity.retrieval import retrieve
from longevity.logging_utils import event

st.set_page_config(
    page_title="Longevity Evidence",
    page_icon="✳",
    layout="wide",
    initial_sidebar_state="expanded",
)
db.init_db()

st.markdown("""
<style>
:root { --ink:#202722; --muted:#68736c; --line:#dfe4df; --accent:#315b48; --paper:#ffffff; --canvas:#f7f8f6; }
html, body, [data-testid="stAppViewContainer"] { background:var(--canvas); color:var(--ink); }
.block-container { max-width: 1180px; padding-top: 1.5rem; padding-bottom: 3rem; }
[data-testid="stSidebar"] { background:#f1f3f0; border-right:1px solid var(--line); }
[data-testid="stMetric"] { background:var(--paper); border:1px solid var(--line); padding:12px 14px; border-radius:3px; }
.eyebrow { color:var(--muted); text-transform:uppercase; letter-spacing:.08em; font-size:.70rem; font-weight:650; }
.hero { padding:1.1rem 0 1.25rem 0; background:transparent; border:0; border-bottom:1px solid var(--line); border-radius:0; margin-bottom:1.25rem; }
.hero h1 { margin:.25rem 0 .35rem 0; font-size:2rem; font-weight:620; color:var(--ink); letter-spacing:-.035em; }
.hero p { color:var(--muted); margin:0; max-width:760px; }
.paper { padding:.9rem 0; border:0; border-bottom:1px solid var(--line); border-radius:0; margin:.25rem 0; background:transparent; }
.paper-title { font-size:1rem; font-weight:620; line-height:1.45; margin-bottom:.35rem; }
.meta { color:var(--muted); font-size:.8rem; }
.pill { display:inline-block; padding:2px 7px; border-radius:2px; background:#edf0ec; color:#42584b; font-size:.72rem; margin:2px 4px 2px 0; }
.note { border-left:2px solid #a58a55; padding:.6rem .8rem; background:#f3f1eb; color:#544c3d; border-radius:0; }
div[data-testid="stTabs"] button { font-weight:600; }
.stButton > button, .stDownloadButton > button { border-radius:3px; }
</style>
""", unsafe_allow_html=True)

profile = db.get_profile()
papers = db.list_papers(limit=2000)

with st.sidebar:
    st.markdown("## Longevity Evidence")
    st.caption("Research workspace")
    page = st.radio(
        "Workspace",
        ["Discover", "Library", "Research brief", "Collection", "Activity", "Privacy & data"],
        label_visibility="collapsed",
    )
    st.divider()
    with st.expander("Research preferences", expanded=False):
        st.caption("Optional context for literature triage. This is not a clinical eligibility assessment.")
        age = st.number_input("Age", min_value=18, max_value=110, value=int(profile["age"] or 45))
        sex_options = ["not specified", "female", "male"]
        current_sex = profile.get("sex") if profile.get("sex") in sex_options else "not specified"
        sex = st.selectbox("Sex", sex_options, index=sex_options.index(current_sex))
        disease_text = st.text_input("Conditions to monitor", ", ".join(profile.get("diseases", [])))
        interest_options = ["physical_activity", "sleep", "diet", "smoking", "alcohol", "social_connection", "aging"]
        interests = st.multiselect("Research topics", interest_options,
                                   default=profile.get("interests") or ["aging", "physical_activity", "sleep"])
        if st.button("Save preferences", use_container_width=True):
            diseases = [x.strip() for x in disease_text.split(",") if x.strip()]
            db.save_profile(age, sex, diseases, interests)
            event("profile_saved", disease_count=len(diseases), interest_count=len(interests))
            st.success("Preferences saved.")
            st.rerun()
    st.divider()
    st.caption(f"{len(papers):,} papers in your local library")
    st.caption("Research workspace · Local database")

def hero(kicker, title, subtitle):
    st.markdown(
        f'<div class="hero"><div class="eyebrow">{kicker}</div>'
        f'<h1>{title}</h1><p>{subtitle}</p></div>',
        unsafe_allow_html=True,
    )

def render_paper(hit, index=None):
    p = hit["paper"]
    title = p.get("title") or "Untitled publication"
    date = p.get("pub_date") or "Date unavailable"
    journal = p.get("journal") or "Journal unavailable"
    pmid = p.get("pmid") or "—"
    score = hit.get("score")
    st.markdown('<div class="paper">', unsafe_allow_html=True)
    st.markdown(f'<div class="paper-title">{index + ". " if index else ""}{title}</div>', unsafe_allow_html=True)
    score_text = f" · Text match {score:.2f}" if score is not None else ""
    st.markdown(f'<div class="meta">{journal} · {date} · PMID {pmid}{score_text}</div>', unsafe_allow_html=True)
    tags = p.get("inferred_topics") or []
    if tags:
        st.markdown("".join(f'<span class="pill">{t.replace("_", " ")}</span>' for t in tags), unsafe_allow_html=True)
    abstract = p.get("abstract") or "No abstract available."
    with st.expander("Read abstract and source details"):
        st.write(abstract)
        if p.get("url"):
            st.link_button("Open PubMed record", p["url"])
        types = p.get("publication_types") or []
        if types:
            st.caption("Publication types: " + ", ".join(types))
        extraction = p.get("extraction_json") or {}
        if extraction:
            st.caption("Automated study-type label: " + str(extraction.get("study_type", "unknown")) + " (heuristic)")
    st.markdown('</div>', unsafe_allow_html=True)

if page == "Discover":
    hero("Literature discovery", "Find evidence worth examining.", 
         "Search your collected PubMed library, inspect original abstracts, and keep relevance separate from evidence strength.")
    query = st.text_input("Research question", placeholder="e.g. Does resistance training affect healthy aging outcomes?")
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        result_count = st.selectbox("Results", [5, 10, 20], index=1)
    with c2:
        topic_filter = st.selectbox("Topic", ["All topics", "aging", "physical_activity", "sleep", "diet",
                                                "smoking", "alcohol", "social_connection"])
    with c3:
        st.caption("Search runs against your local collection. Import more papers from Collection.")
    if query.strip():
        hits = retrieve(query.strip(), profile, k=100)
        if topic_filter != "All topics":
            hits = [h for h in hits if topic_filter in (h["paper"].get("inferred_topics") or [])]
        hits = hits[:result_count]
        st.markdown(f"### {len(hits)} results")
        if hits:
            for i, hit in enumerate(hits, 1):
                render_paper(hit, i)
        else:
            st.info("No matching records found. Try broader wording or collect more publications.")
    else:
        st.markdown("### Start with a research question")
        st.write("Your search will return source-linked records from the local library.")
        if papers:
            st.caption("Recently added")
            for i, p in enumerate(papers[:5], 1):
                render_paper({"paper": p}, i)
        else:
            st.info("Your library is empty. Start by collecting recent publications from PubMed.")

elif page == "Library":
    hero("Your research library", "A searchable collection of publications.",
         "Browse imported records and inspect metadata before using them in a research synthesis.")
    if papers:
        search = st.text_input("Filter titles, journals and abstracts", placeholder="Search within your library")
        topic_options = sorted({t for p in papers for t in (p.get("inferred_topics") or [])})
        selected_topic = st.selectbox("Topic filter", ["All"] + topic_options)
        filtered = papers
        if search.strip():
            term = search.lower()
            filtered = [p for p in filtered if term in (p.get("title") or "").lower()
                        or term in (p.get("abstract") or "").lower()
                        or term in (p.get("journal") or "").lower()]
        if selected_topic != "All":
            filtered = [p for p in filtered if selected_topic in (p.get("inferred_topics") or [])]
        st.caption(f"Showing {len(filtered)} of {len(papers)} records")
        for i, p in enumerate(filtered[:100], 1):
            render_paper({"paper": p}, i)
        if len(filtered) > 100:
            st.info("Showing the first 100 matching records. Narrow your filters to inspect more.")
    else:
        st.info("No publications yet. Use Collection to import records from PubMed.")

elif page == "Research brief":
    hero("Evidence synthesis", "Turn a question into a research briefing.",
         "The briefing links back to retrieved publications and makes missing evidence and uncertainty explicit.")
    question = st.text_area("Research question", placeholder="What does the literature say about...", height=100)
    col1, col2 = st.columns([1, 3])
    with col1:
        k = st.selectbox("Sources to examine", [5, 8, 12, 20], index=1)
    if st.button("Generate research brief", type="primary", disabled=not question.strip()):
        with st.spinner("Retrieving publications and preparing the briefing..."):
            report = build_report(question.strip(), profile, k=k)
        st.session_state["latest_report"] = report
        event("briefing_created", question_length=len(question))
    report = st.session_state.get("latest_report")
    if report:
        st.download_button("Download Markdown report", report, file_name="longevity_research_brief.md")
        st.markdown("---")
        st.markdown(report)
    else:
        st.caption("A report will appear here after you submit a research question.")
    st.markdown('<div class="note">Important: retrieval relevance is not evidence quality. This prototype does not provide medical advice, treatment recommendations or personal lifespan estimates.</div>', unsafe_allow_html=True)

elif page == "Collection":
    hero("Source management", "Keep your literature library up to date.",
         "Import recent publication records from PubMed. Collection uses publication dates and may not capture every newly available online record.")
    c1, c2 = st.columns(2)
    with c1:
        days = st.slider("Look-back window", 7, 180, 30, help="Number of days of publication dates to search.")
    with c2:
        max_results = st.slider("Maximum records", 10, 500, 100, step=10)
    st.caption("Selected topics: " + (", ".join(profile.get("interests", [])) or "aging (default)"))
    if st.button("Collect publications", type="primary"):
        with st.spinner("Searching PubMed and importing records..."):
            try:
                result = run_weekly(profile.get("interests") or ["aging"], profile.get("diseases"), days, max_results)
                st.success(f"Found {result['found']} records; added {result['inserted']} new records.")
                with st.expander("PubMed query used"):
                    st.code(result["query"])
            except Exception as exc:
                st.error(f"Collection failed: {type(exc).__name__}: {exc}")
    st.markdown("#### How collection works")
    st.write("PubMed search → fetch metadata and abstracts → heuristic metadata extraction → SQLite storage.")
    st.caption("For scheduled weekly collection, see weekly.py and the README.")

elif page == "Activity":
    hero("System activity", "Collection and application history.",
         "Inspect recent pipeline runs and operational events.")
    runs = db.recent_runs()
    if runs:
        st.subheader("Collection runs")
        st.dataframe(pd.DataFrame(runs), use_container_width=True, hide_index=True)
    else:
        st.info("No collection runs recorded yet.")
    from longevity.config import LOG_PATH
    st.subheader("Application events")
    if LOG_PATH.exists():
        st.code("\n".join(LOG_PATH.read_text(encoding="utf-8").splitlines()[-40:]))
    else:
        st.caption("No events recorded yet.")

elif page == "Privacy & data":
    hero("Privacy and data handling", "Your research data, clearly accounted for.",
         "This prototype is designed to run locally. It does not need advertising, behavioural analytics or third-party tracking.")
    st.subheader("What is stored on this device")
    st.markdown("""
    - **Research library:** publication metadata and abstracts imported from PubMed, stored in the local SQLite database.
    - **Research preferences:** optional age range, sex, conditions and topics, stored in the same local database if you choose to save them.
    - **Operational history:** collection timestamps, counts and status. Search text and personal health details should not be included in operational logs.
    - **Generated briefings:** held in the current app session unless you download them.
    """)
    st.subheader("Cookies and browser storage")
    st.markdown("""
    - No advertising, analytics, marketing or cross-site tracking cookies are intentionally added by this application.
    - Streamlit may use strictly necessary session mechanisms to keep the app working. These are platform/runtime behaviour, not an optional analytics system.
    - This build does not add a cookie-consent banner because it does not intentionally deploy non-essential cookies. If analytics, embedded media, or other non-essential storage is added later, it must remain off until the visitor gives valid consent.
    """)
    st.subheader("External services and AI")
    st.markdown("""
    - PubMed is contacted when you explicitly run a collection. The request contains search terms derived from the selected research topics.
    - External LLM processing is **disabled by default** in this build. Do not enable it for sensitive research questions unless you have reviewed the provider's current terms, retention settings and data-processing terms.
    - API keys belong in server-side environment variables, never in frontend code, source control or browser storage.
    """)
    st.subheader("Your controls")
    st.markdown("""
    - Research preferences are optional. Avoid entering diagnoses, exact birth dates, names or other identifying details.
    - The local database and event log live in the `data/` directory (or `LONGEVITY_DATA_DIR`, if configured). Protect this folder and include it in backups only if you intend to retain its contents.
    - To erase locally stored data, stop the app and remove the `data/longevity.sqlite3` and `data/events.jsonl` files. This permanently deletes the local library, preferences and local activity history.
    """)
    st.subheader("Important limitation")
    st.warning("This is a technical privacy notice for the current local prototype, not a legal compliance certification or a substitute for a GDPR assessment. A public multi-user deployment needs authentication, access controls, retention/deletion workflows, processor agreements, hosting-region review and a complete privacy notice.")
    st.caption("No advertising or behavioural analytics package is included in this project.")

st.divider()
st.caption("Longevity Evidence is a literature-navigation and research-triage prototype. Automated age, sex, disease and topic matching is heuristic. Always inspect the original study; mentions do not establish subgroup findings. No individual survival or lifespan estimate is produced.")
