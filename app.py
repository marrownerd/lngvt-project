import streamlit as st
import pandas as pd
from longevity import db
from longevity.pipeline import run_weekly
from longevity.report import build_report
from longevity.retrieval import retrieve
from longevity.matching import match_profile
from longevity.logging_utils import event

st.set_page_config(page_title="Longevity Evidence", page_icon="🧬", layout="wide")
db.init_db()

st.title("Longevity Evidence")
st.caption("A local research-monitoring prototype. It explains evidence limitations and uncertainty; it does not diagnose or predict lifespan.")

with st.sidebar:
    st.header("Research profile")
    old = db.get_profile()
    age = st.number_input("Age", min_value=18, max_value=110,
                          value=int(old["age"] or 45), step=1)
    sex = st.selectbox("Sex", ["not specified", "female", "male"],
                       index=["not specified","female","male"].index(old["sex"]))
    disease_text = st.text_input("Conditions to monitor (comma-separated)",
                                 value=", ".join(old["diseases"]))
    interest_options = ["physical_activity","sleep","diet","smoking","alcohol","social_connection","aging"]
    interests = st.multiselect("Topics", interest_options,
                               default=old["interests"] or ["aging","physical_activity","sleep"])
    if st.button("Save profile", type="primary"):
        diseases = [x.strip() for x in disease_text.split(",") if x.strip()]
        db.save_profile(age, sex, diseases, interests)
        event("profile_saved", disease_count=len(diseases), interest_count=len(interests))
        st.success("Profile saved.")
    profile = db.get_profile()

tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Collect papers", "Ask the library", "Research log"])

with tab1:
    papers = db.list_papers(limit=2000)
    c1,c2,c3 = st.columns(3)
    c1.metric("Papers in local library", len(papers))
    c2.metric("Topics selected", len(profile["interests"]))
    c3.metric("Conditions tracked", len(profile["diseases"]))
    st.subheader("Latest publications")
    if papers:
        df = pd.DataFrame([{
            "Date": p.get("pub_date"), "Title": p.get("title"), "Journal": p.get("journal"),
            "PMID": p.get("pmid"), "Topics detected": ", ".join(p.get("inferred_topics", [])),
            "Diseases detected": ", ".join(p.get("inferred_diseases", []))
        } for p in papers[:30]])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("The library is empty. Open 'Collect papers' and run the first import.")

with tab2:
    st.subheader("Import recent PubMed publications")
    st.write("The collector searches the selected topics over a recent publication-date window.")
    days = st.slider("Look-back window (days)", 7, 90, 14)
    max_results = st.slider("Maximum results", 10, 300, 100, step=10)
    if st.button("Run collection", type="primary"):
        with st.spinner("Searching PubMed and importing records..."):
            try:
                result = run_weekly(profile["interests"] or ["aging"], profile["diseases"], days, max_results)
                st.success(f"Found {result['found']} records; added {result['inserted']} new records.")
                st.code(result["query"])
            except Exception as e:
                st.error(f"Collection failed: {e}")
    st.caption("For unattended weekly runs, see README.md. NCBI API limits and access policies apply.")

with tab3:
    st.subheader("Search and build a research briefing")
    question = st.text_area("Question", value="What does the literature say about physical activity and healthy aging?")
    if st.button("Build briefing"):
        report = build_report(question, profile)
        st.markdown(report)
        st.download_button("Download briefing (.md)", report, file_name="research_briefing.md")
        event("briefing_created", question_length=len(question))
    st.divider()
    st.subheader("Quick evidence search")
    q = st.text_input("Search local abstracts")
    if q:
        for hit in retrieve(q, profile, k=10):
            p = hit["paper"]
            st.markdown(f"**[{p['title']}]({p.get('url')})** — score {hit['score']:.3f}")
            st.caption(f"PMID {p['pmid']} · {p.get('pub_date')} · {', '.join(p.get('inferred_topics', []))}")
            st.write((p.get("abstract") or "")[:800] + ("..." if len(p.get("abstract") or "") > 800 else ""))

with tab4:
    st.subheader("Pipeline runs")
    runs = db.recent_runs()
    if runs:
        st.dataframe(pd.DataFrame(runs), use_container_width=True, hide_index=True)
    else:
        st.info("No runs yet.")
    st.subheader("Event log")
    from longevity.config import LOG_PATH
    if LOG_PATH.exists():
        st.code("\n".join(LOG_PATH.read_text(encoding="utf-8").splitlines()[-50:]))
    else:
        st.caption("No events recorded yet.")

st.divider()
st.caption("Important: profile matching is heuristic. Always inspect the original publication and its population, methods, outcomes and limitations. No personal life-expectancy estimate is produced.")
