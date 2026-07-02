import json
import streamlit as st
import importlib
import ranker
importlib.reload(ranker)
from ranker import score_candidate

st.set_page_config(page_title="Candidate Ranker Sandbox", layout="wide")
st.title("Candidate Ranker — Sandbox")
st.caption("Upload or paste a candidate dataset (JSON array) to rank candidates.")

# --- Input ---
uploaded = st.file_uploader("Upload a .json file (array of candidates)", type=["json"])
pasted = st.text_area("Or paste JSON array here", height=200)

candidates = None

if uploaded:
    try:
        candidates = json.load(uploaded)
        if not isinstance(candidates, list):
            st.error("JSON must be an array of candidates.")
            candidates = None
    except Exception as e:
        st.error(f"Invalid JSON file: {e}")
elif pasted.strip():
    try:
        candidates = json.loads(pasted)
        if not isinstance(candidates, list):
            st.error("JSON must be an array of candidates.")
            candidates = None
    except Exception as e:
        st.error(f"Invalid JSON: {e}")

# --- Controls ---
if candidates:
    st.success(f"Loaded {len(candidates)} candidates.")
    top_n = st.number_input("Top N candidates to show", min_value=1, max_value=len(candidates), value=min(10, len(candidates)), step=1)

    if st.button("Rank"):
        scored = []
        disqualified = 0
        for c in candidates:
            score, reasoning = score_candidate(c)
            if score is not None and score > 0:
                scored.append({
                    "candidate_id": c["candidate_id"],
                    "name": c["profile"]["anonymized_name"],
                    "title": c["profile"]["current_title"],
                    "company": c["profile"]["current_company"],
                    "yoe": c["profile"]["years_of_experience"],
                    "score": round(score, 4),
                    "reasoning": reasoning
                })
            else:
                disqualified += 1

        scored.sort(key=lambda x: x["score"], reverse=True)
        top = scored[:top_n]

        st.markdown(f"**{len(scored)} scored, {disqualified} disqualified. Showing top {len(top)}.**")

        for rank, c in enumerate(top, start=1):
            with st.expander(f"#{rank} — {c['candidate_id']} | {c['title']} @ {c['company']} | Score: {c['score']}"):
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.markdown(f"**Name:** {c['name']}")
                    st.markdown(f"**YOE:** {c['yoe']}")
                    st.markdown(f"**Score:** {c['score']}")
                with col2:
                    st.markdown(f"**Reasoning:** {c['reasoning']}")