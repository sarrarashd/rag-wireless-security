"""WiSec Assistant: question-answering interface (Streamlit).

Run:  streamlit run app.py
"""
import sqlite3
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from config import CHUNK_SIZES, DB_PATH, DEFAULT_CHUNK_SIZE, DEFAULT_K  # noqa: E402
from rag import MIN_VECTOR_SCORE, MODEL, answer, pick_backend  # noqa: E402

EXAMPLES = [
    "What does SUCI stand for and what problem does it solve?",
    "Is it safe to pair my wireless headphones?",
    "How does 5G protect a subscriber's permanent identity compared with LTE?",
    "What security improvements does WPA3 bring over WPA2?",
]

st.set_page_config(page_title="WiSec Assistant", page_icon="📡", layout="wide")


@st.cache_data
def load_documents():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        """SELECT d.series_number, d.title, d.publisher, d.pub_year, d.status, d.technology,
                  d.num_pages, d.source_url,
                  SUM(k.chunk_size = 500), SUM(k.chunk_size = 1500)
           FROM documents d LEFT JOIN chunks k ON k.doc_id = d.doc_id
           GROUP BY d.doc_id ORDER BY d.doc_id"""
    ).fetchall()
    conn.close()
    columns = ["Series", "Title", "Publisher", "Year", "Status", "Technology", "Pages",
               "Source", "Chunks (500)", "Chunks (1500)"]
    return [dict(zip(columns, r)) for r in rows]


def save_feedback(query_id, rating):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE query_log SET feedback = ? WHERE query_id = ?", (rating, query_id))
    conn.commit()
    conn.close()


def show_result(result):
    if result["status"] == "answered":
        st.markdown(result["answer"])
    elif result["status"] == "insufficient":
        st.info(result["answer"])
    else:
        st.markdown(result["answer"])
    for warning in result["warnings"]:
        st.warning(warning)

    if result["citations"]:
        st.subheader("Sources cited")
        for c in result["citations"]:
            flag = " · :red[WITHDRAWN]" if c["status"] == "withdrawn" else ""
            label = (f'[{c["number"]}] {c["citation"]} · {c["title"]} '
                     f'({c["publisher"]}, {c["year"]}){flag}')
            with st.expander(label):
                st.write(c["text"])

    t = result["timing"]
    reason = f' · reason: {result["reason"]}' if result["reason"] else ""
    st.caption(
        f'Status: {result["status"]}{reason} · {result["mode"]} search, k={result["k"]}, '
        f'chunk size {result["chunk_size"]} · retrieval {t["retrieval_ms"]} ms, '
        f'generation {t["generation_ms"] / 1000:.1f} s'
    )

    with st.expander(f'All {len(result["passages"])} retrieved passages'):
        cited = {c["number"] for c in result["citations"]}
        for n, h in enumerate(result["passages"], 1):
            used = "cited" if n in cited else "not cited"
            pages = (f'p. {h["page_start"]}' if h["page_start"] == h["page_end"]
                     else f'pp. {h["page_start"]}-{h["page_end"]}')
            st.markdown(f'**[{n}] {h["series"]}, {pages}** · score {h["score"]} · {used}')
            st.write(h["text"])

    if result.get("query_id"):
        st.write("Was this answer helpful?")
        cols = st.columns([1, 1, 1, 6])
        for col, (label, rating) in zip(cols, [("👍 Yes", 1), ("😐 Partly", 0), ("👎 No", -1)]):
            if col.button(label, key=f'fb{rating}'):
                save_feedback(result["query_id"], rating)
                st.toast("Feedback saved")


st.title("📡 WiSec Assistant")
st.caption("Answers questions about wireless security from 11 NIST and NSA publications "
           "(Wi-Fi, Bluetooth, LTE, 5G). Every answer cites the passages it used.")

with st.sidebar:
    st.header("Search settings")
    mode = st.radio("Search method", ["vector", "keyword", "hybrid"],
                    format_func=lambda m: {"vector": "Vector (by meaning)",
                                           "keyword": "Keyword (BM25)",
                                           "hybrid": "Hybrid (both, rank fusion)"}[m])
    chunk_size = st.radio("Chunk size (characters)", CHUNK_SIZES,
                          index=CHUNK_SIZES.index(DEFAULT_CHUNK_SIZE))
    k = st.slider("Passages to retrieve (k)", 1, 10, DEFAULT_K)
    st.divider()
    try:
        st.caption(f"Language model: {MODEL} via {pick_backend()}")
    except RuntimeError as exc:
        st.error(str(exc))
    st.caption(f"Safe-response threshold: similarity below {MIN_VECTOR_SCORE}")

ask_tab, docs_tab = st.tabs(["Ask a question", "Document collection"])

with ask_tab:
    st.write("Try an example:")
    for col, example in zip(st.columns(len(EXAMPLES)), EXAMPLES):
        if col.button(example, use_container_width=True):
            st.session_state["question"] = example
            st.session_state["run"] = True

    with st.form("ask"):
        question = st.text_input("Your question", key="question",
                                 placeholder="e.g. How should I secure Bluetooth on a work laptop?")
        submitted = st.form_submit_button("Ask", type="primary")

    if (submitted or st.session_state.pop("run", False)) and question.strip():
        with st.spinner("Searching the documents and writing an answer..."):
            try:
                st.session_state["result"] = answer(question, k, chunk_size, mode)
            except Exception as exc:  # show the problem instead of a stack trace
                st.session_state.pop("result", None)
                st.error(f"Could not answer: {exc}")

    if "result" in st.session_state:
        st.divider()
        st.subheader(st.session_state["result"]["question"])
        show_result(st.session_state["result"])

with docs_tab:
    st.dataframe(load_documents(), use_container_width=True, hide_index=True,
                 column_config={"Source": st.column_config.LinkColumn("Source")})
    st.caption("SP 800-97 is withdrawn: answers that cite it carry a warning.")
