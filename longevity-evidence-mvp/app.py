import streamlit as st
import pandas as pd
from longevity import db
from longevity.pipeline import run_weekly
from longevity.report import build_report
from longevity.retrieval import retrieve
from longevity.matching import match_profile
from longevity.logging_utils import event
from longevity.effect_extraction import extract_from_papers
from longevity.meta_analysis import pool_effects

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

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Overview", "Collect papers", "Ask the library", "Research log", "Evidence & statistics"])

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
        st.dataframe(df, width="stretch", hide_index=True)
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
        st.dataframe(pd.DataFrame(runs), width="stretch", hide_index=True)
    else:
        st.info("No runs yet.")
    st.subheader("Event log")
    from longevity.config import LOG_PATH
    if LOG_PATH.exists():
        st.code("\n".join(LOG_PATH.read_text(encoding="utf-8").splitlines()[-50:]))
    else:
        st.caption("No events recorded yet.")

with tab5:
    st.subheader("Numerical evidence extraction")
    st.write(
        "The prototype scans stored PubMed abstracts and cached open-access full texts for HR, RR, OR and IRR estimates, "
        "95% confidence intervals and p-values. Each candidate retains the exact sentence "
        "and its PubMed source. This is a conservative regex extractor, not a validated "
        "full-text extraction model."
    )
    papers_for_extraction = db.list_papers(limit=5000)
    from longevity.effect_extraction import extract_from_papers
    from longevity.open_access import fetch_open_access_full_text
    with st.expander("Fetch available open-access full texts", expanded=False):
        st.write("The app checks Europe PMC for open-access full text and caches permitted XML-derived text locally. It does not bypass publisher paywalls. Availability varies by article; review each article's licence before reuse or redistribution.")
        full_text_limit = st.slider("Maximum papers to check in this batch", 1, 30, 10)
        if st.button("Fetch OA full texts"):
            eligible_papers = [p for p in papers_for_extraction if p.get("pmid")][:full_text_limit]
            statuses = {"downloaded": 0, "cached": 0, "unavailable": 0, "error": 0, "skipped": 0}
            details = []
            progress = st.progress(0)
            for idx, paper in enumerate(eligible_papers, 1):
                result = fetch_open_access_full_text(paper)
                statuses[result["status"]] = statuses.get(result["status"], 0) + 1
                if result["status"] in {"downloaded", "unavailable", "error"}:
                    details.append(f'PMID {paper["pmid"]}: {result.get("reason", result["status"])}')
                progress.progress(idx / max(len(eligible_papers), 1))
            st.write(statuses)
            for detail in details:
                st.caption(detail)
            st.info("The extraction table below now prefers cached full text over the abstract.")
    extracted = extract_from_papers(papers_for_extraction)
    if not extracted:
        st.info("No ratio effect estimates were recognized in the abstracts currently stored. This does not mean the studies contain no numerical results. Try collecting more records or inspect full texts.")
    else:
        st.metric("Candidate numerical estimates", len(extracted))
        st.caption("Mechanical validation checks arithmetic consistency only. It does not validate study design, confounding, causal interpretation or whether the estimate answers your question.")
        view_rows = [{
            "PMID": r["pmid"], "Measure": r["effect_measure"], "Estimate": r["estimate"],
            "95% CI": (f'{r["ci95_lower"]:.3g}–{r["ci95_upper"]:.3g}' if r["ci95_lower"] is not None and r["ci95_upper"] is not None else "not parsed"),
            "p-value": r["p_value_text"] or "not parsed", "Outcome hint": r["outcome_hint"] or "not classified",
            "Source": r["source_type"], "Validation": r["validation_status"], "Study": (r["title"] or "")[:100]
        } for r in extracted]
        st.dataframe(pd.DataFrame(view_rows), width="stretch", hide_index=True)
        st.download_button(
            "Download extracted evidence (CSV)",
            pd.DataFrame(extracted).drop(columns=["validation_errors", "validation_warnings"]).to_csv(index=False).encode("utf-8-sig"),
            file_name="extracted_effect_estimates.csv", mime="text/csv"
        )
        with st.expander("Inspect source sentences and validation notes", expanded=False):
            for idx, r in enumerate(extracted, 1):
                st.markdown(f'**{idx}. PMID {r["pmid"]} · {r["effect_measure"]} {r["estimate"]} · {r["validation_status"]}**')
                st.write(r["source_text"])
                st.caption(f'Source: {r["source_url"]} · type: {r["source_type"]} · text span: {r["source_char_start"]}:{r["source_char_end"]}')
                if r["validation_errors"]:
                    st.error("; ".join(r["validation_errors"]))
                if r["validation_warnings"]:
                    st.warning("; ".join(r["validation_warnings"]))

        st.divider()
        st.subheader("Random-effects synthesis")
        st.warning(
            "Pooling is not automatic. Select estimates only after opening the original papers. "
            "You must confirm that outcome/estimand, population, comparator, follow-up and design "
            "are sufficiently compatible, and that the selected reports represent independent studies. "
            "The software cannot establish these facts."
        )
        poolable = [r for r in extracted if r["validation_status"] == "mechanically_consistent" and r["standard_error_log_scale"] is not None and r["pmid"]]
        if len(poolable) < 2:
            st.info("At least two estimates with a parsed 95% CI and no mechanical consistency flags are needed for this lab. Estimates without a CI remain visible above but cannot be pooled in this version.")
        else:
            labels = {
                f'{i+1} · PMID {r["pmid"]} · {r["effect_measure"]} {r["estimate"]:.3g} [{r["ci95_lower"]:.3g}, {r["ci95_upper"]:.3g}]': r
                for i, r in enumerate(poolable)
            }
            selected_labels = st.multiselect("Select estimates to review", list(labels.keys()))
            measure_options = sorted({labels[x]["effect_measure"] for x in selected_labels})
            if measure_options and len(measure_options) > 1:
                st.error("Selected estimates use different effect measures. Split them into separate analyses.")
            outcome = st.text_input("Exact outcome / estimand shared by these studies", placeholder="e.g. all-cause mortality")
            population = st.text_input("Population shared by these studies", placeholder="e.g. community-dwelling adults")
            comparator = st.text_input("Comparator shared by these studies", placeholder="e.g. highest vs lowest activity category")
            follow_up = st.text_input("Follow-up compatibility", placeholder="e.g. cohort follow-up; analyse similar horizons")
            design = st.text_input("Compatible study design", placeholder="e.g. prospective cohort studies")
            method = st.selectbox("Between-study variance estimator", ["REML", "DL"], index=0)
            confirmed = st.checkbox("I reviewed the original sources and confirm endpoint, population, comparator, follow-up and design compatibility, with no overlapping/duplicate study populations.")
            if st.button("Run random-effects synthesis", type="primary", disabled=len(selected_labels) < 2):
                try:
                    chosen = []
                    for label in selected_labels:
                        row = dict(labels[label])
                        row.update({"outcome": outcome, "population": population, "comparator": comparator, "follow_up": follow_up, "design": design})
                        chosen.append(row)
                    result = pool_effects(chosen, method=method, confirm_compatibility=confirmed)
                    ratio = result["pooled_ratio"]
                    lo, hi = result["ci95_ratio"]
                    st.success("Synthesis completed for the manually selected estimates.")
                    m1, m2, m3 = st.columns(3)
                    m1.metric(f'Pooled {result["effect_measure"]}', f'{ratio:.3f}', f'{(ratio-1)*100:+.1f}% relative ratio')
                    m2.metric("95% CI", f'{lo:.3f}–{hi:.3f}')
                    m3.metric("Pooled p-value", f'{result["pooled_p_value"]:.4g}')
                    st.write(f'Heterogeneity: I²={result["i_squared_percent"]:.1f}%; τ²={result["tau_squared"]:.4g}; Q={result["q"]:.3f}; Q p={result["q_p_value"]:.4g}' if result["q_p_value"] is not None else f'Heterogeneity: I²={result["i_squared_percent"]:.1f}%; τ²={result["tau_squared"]:.4g}')
                    st.write(f'Method: {result["method"]}; {result["ci_method"]}; k={result["number_of_studies"]}. The pooled null hypothesis is ratio=1 (log effect=0); CI excludes null: {result["ci_excludes_null"]}.')
                    if result["prediction_interval_95_ratio"]:
                        pi = result["prediction_interval_95_ratio"]
                        st.write(f'Approximate 95% prediction interval for a new study: {pi[0]:.3f}–{pi[1]:.3f}')
                    else:
                        st.write("Prediction interval not shown: at least three studies are required in this implementation.")
                    st.caption(result["interpretation"] + " A ratio-scale effect is not an absolute percentage-point risk reduction and cannot be converted into years of life.")
                except Exception as exc:
                    st.error(f"Synthesis not run: {exc}")


st.divider()
st.caption("Important: profile matching is heuristic. Always inspect the original publication and its population, methods, outcomes and limitations. No personal life-expectancy estimate is produced.")
