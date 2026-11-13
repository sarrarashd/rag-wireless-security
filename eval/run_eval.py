"""Evaluate retrieval and answers on the test questions in eval/questions.json.

Part 1 - retrieval (no language model, fast): every combination of search mode,
chunk size and k. A retrieved passage counts as relevant when it comes from one of
the question's expected documents AND contains one of its evidence terms.
  Hit@k      share of questions with at least one relevant passage in the top k
  MRR        mean of 1 / rank of the first relevant passage (0 when none)
  P@k        mean share of the top k passages that are relevant
  Coverage   multi-document questions only: share that retrieved passages from
             at least `min_docs` different expected documents

Part 2 - answers (calls the language model; add --answers): five configurations
are compared. Each answer gets an automatic verdict, which is a first pass that a
person should review (docs/evaluation.md records the manual review):
  correct    every key fact is present, the cited sources are expected documents,
             and a multi-document answer cites enough different documents
  partial    some key facts are present, or the citations are off
  incorrect  no key fact, an unsupported answer, or a refusal of an answerable question
  For unanswerable questions: correct = safe response, incorrect = any answer.

Run:  python eval/run_eval.py              retrieval only
      python eval/run_eval.py --answers    retrieval and answers
"""
import argparse
import csv
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from rag import answer  # noqa: E402
from search import retrieve  # noqa: E402

RESULTS = ROOT / "eval" / "results"
QUESTIONS = json.loads((ROOT / "eval" / "questions.json").read_text())

MODES = ["vector", "keyword", "hybrid"]
SIZES = [500, 1500]
KS = [3, 5, 10]

# (label, mode, chunk_size, k): the baseline plus one change at a time
ANSWER_CONFIGS = [
    ("vector-500-k5", "vector", 500, 5),     # baseline
    ("keyword-500-k5", "keyword", 500, 5),   # keyword instead of vector search
    ("hybrid-500-k5", "hybrid", 500, 5),     # both rankings fused
    ("vector-1500-k5", "vector", 1500, 5),   # larger chunks
    ("vector-500-k3", "vector", 500, 3),     # fewer passages
]


def is_relevant(hit, q):
    text = hit["text"].lower()
    return hit["series"] in q["expected_docs"] and any(e.lower() in text for e in q["evidence"])


def evaluate_retrieval():
    answerable = [q for q in QUESTIONS if q["expected_docs"]]
    summary, detail = [], []
    for mode in MODES:
        for size in SIZES:
            retrieve("warm up", 1, size, mode)  # load the model and index before timing
            for k in KS:
                hits_at_k, rr, precision, coverage, latency = [], [], [], [], []
                for q in answerable:
                    start = time.perf_counter()
                    hits = retrieve(q["question"], k, size, mode)
                    latency.append((time.perf_counter() - start) * 1000)
                    flags = [is_relevant(h, q) for h in hits]
                    first = flags.index(True) + 1 if any(flags) else 0
                    hits_at_k.append(bool(first))
                    rr.append(1 / first if first else 0)
                    precision.append(sum(flags) / k)
                    docs = {h["series"] for h in hits if h["series"] in q["expected_docs"]}
                    if q["type"] == "multi":
                        coverage.append(len(docs) >= q.get("min_docs", 2))
                    detail.append({
                        "mode": mode, "chunk_size": size, "k": k, "id": q["id"], "type": q["type"],
                        "first_relevant_rank": first, "relevant_in_top_k": sum(flags),
                        "top_score": hits[0]["score"] if hits else "",
                        "retrieved": "; ".join(f'{h["series"]} p.{h["page_start"]}' for h in hits),
                    })
                summary.append({
                    "mode": mode, "chunk_size": size, "k": k,
                    "hit_rate": round(statistics.mean(hits_at_k), 2),
                    "mrr": round(statistics.mean(rr), 2),
                    "precision": round(statistics.mean(precision), 2),
                    "multi_doc_coverage": round(statistics.mean(coverage), 2),
                    "mean_latency_ms": round(statistics.mean(latency), 1),
                })
    return summary, detail


def grade(q, result):
    """Automatic first-pass verdict for one answer. Returns (verdict, notes)."""
    if q["type"] == "unanswerable":
        if result["status"] == "insufficient":
            return "correct", "safe response"
        return "incorrect", "answered a question the documents do not cover"
    if result["status"] == "insufficient":
        return "incorrect", "refused an answerable question"
    if result["status"] == "unsupported":
        return "incorrect", "answer has no citations"

    text = result["answer"].replace("\\", "").lower()  # drop Markdown escapes
    found = sum(any(alt.lower() in text for alt in group) for group in q["key_facts"])
    cited = [c["series"] for c in result["citations"]]
    on_target = [s for s in cited if s in q["expected_docs"]]
    citation_precision = len(on_target) / len(cited)
    notes = (f"{found}/{len(q['key_facts'])} key facts; "
             f"{len(on_target)}/{len(cited)} citations from expected documents")
    enough_docs = len(set(on_target)) >= q.get("min_docs", 1)
    if found == len(q["key_facts"]) and citation_precision >= 0.5 and enough_docs:
        return "correct", notes
    if found or on_target:
        if not enough_docs:
            notes += f"; cites {len(set(on_target))} of the {q.get('min_docs', 1)} documents needed"
        return "partial", notes
    return "incorrect", notes


def evaluate_answers():
    rows, records = [], {}
    for label, mode, size, k in ANSWER_CONFIGS:
        print(f"  generating answers: {label}")
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(
                lambda q: answer(q["question"], k, size, mode, log=False), QUESTIONS))
        records[label] = []
        for q, r in zip(QUESTIONS, results):
            verdict, notes = grade(q, r)
            cited = [c["citation"] for c in r["citations"]]
            rows.append({
                "config": label, "id": q["id"], "type": q["type"], "status": r["status"],
                "auto_verdict": verdict, "notes": notes, "citations": "; ".join(cited),
                "withdrawn_warning": any("withdrawn" in w for w in r["warnings"]),
                "retrieval_ms": r["timing"]["retrieval_ms"],
                "generation_ms": r["timing"]["generation_ms"],
                "total_ms": r["timing"]["total_ms"],
            })
            records[label].append({
                "id": q["id"], "type": q["type"], "question": q["question"],
                "expected_answer": q["expected_answer"], "status": r["status"],
                "auto_verdict": verdict, "notes": notes, "answer": r["answer"],
                "reason": r["reason"], "warnings": r["warnings"], "citations": cited,
                "retrieved": [f'{h["series"]} p.{h["page_start"]} (score {h["score"]})'
                              for h in r["passages"]],
                "timing": r["timing"], "model": r["model"], "backend": r["backend"],
            })
    return rows, records


def write_csv(path, rows):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--answers", action="store_true",
                        help="also generate and grade answers (calls the language model)")
    args = parser.parse_args()
    RESULTS.mkdir(parents=True, exist_ok=True)

    print(f"Retrieval evaluation on {sum(bool(q['expected_docs']) for q in QUESTIONS)} "
          f"answerable questions")
    summary, detail = evaluate_retrieval()
    write_csv(RESULTS / "retrieval_summary.csv", summary)
    write_csv(RESULTS / "retrieval_detail.csv", detail)
    print(f"{'mode':<9}{'size':>5}{'k':>4}{'Hit@k':>8}{'MRR':>7}{'P@k':>7}{'Cover':>7}{'ms':>8}")
    for r in summary:
        print(f"{r['mode']:<9}{r['chunk_size']:>5}{r['k']:>4}{r['hit_rate']:>8}{r['mrr']:>7}"
              f"{r['precision']:>7}{r['multi_doc_coverage']:>7}{r['mean_latency_ms']:>8}")

    if args.answers:
        print(f"\nAnswer evaluation on {len(QUESTIONS)} questions")
        rows, records = evaluate_answers()
        write_csv(RESULTS / "answers_summary.csv", rows)
        (RESULTS / "answers.json").write_text(json.dumps(records, indent=2))
        print(f"\n{'config':<17}{'correct':>8}{'partial':>8}{'incorrect':>10}{'mean total s':>14}")
        for label, *_ in ANSWER_CONFIGS:
            mine = [r for r in rows if r["config"] == label]
            count = lambda v: sum(r["auto_verdict"] == v for r in mine)  # noqa: E731
            mean_s = statistics.mean(r["total_ms"] for r in mine) / 1000
            print(f"{label:<17}{count('correct'):>8}{count('partial'):>8}"
                  f"{count('incorrect'):>10}{mean_s:>14.1f}")
    print(f"\nResults written to {RESULTS.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
