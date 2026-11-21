"""
Offline analysis of a saved live RAG run (reports/rag_quality_eval.json + _queries.csv).

    python -m backend.scripts.analyze_live_rag_eval  ->  reports/rag_live_analysis.json

No network, no database. Adds what run_rag_quality_eval's report does not: list diversity,
catalog coverage, repeated books, top/bottom queries, failure/fallback rates and the
retrieval-vs-answer split. Metric values come from the harness CSV (labels: see label_tier).
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.evaluation.retrieval import Catalog  # noqa: E402
from backend.utils.preprocess import normalize_isbn  # noqa: E402

REPORTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "evaluation", "reports")


def main() -> None:
    run = json.load(open(os.path.join(REPORTS, "rag_quality_eval.json"), encoding="utf-8"))
    rows = {r["id"]: r for r in csv.DictReader(open(os.path.join(REPORTS, "rag_quality_eval_queries.csv"), encoding="utf-8"))}
    cat = Catalog()
    df = cat.df
    by_isbn = {normalize_isbn(i): r for i, r in zip(df["isbn13"], df.to_dict("records"))}

    out: dict = {"run_at": run["run_at"], "git_sha": run.get("git_sha"), "catalog_size": len(df)}
    queries = run["queries"]
    statuses = Counter(q["cold"]["status"] for q in queries)
    sources = Counter(q["cold"]["source"] for q in queries)
    degraded = [q["id"] for q in queries if q["cold"].get("degraded")]
    errors = [q["id"] for q in queries if q["cold"].get("error")]
    http = run["evaluation"]["performance"]["http_calls"]
    out["reliability"] = {
        "n_queries": len(queries), "statuses": statuses, "sources": sources,
        "degraded_queries": degraded, "errored_queries": errors,
        "fallback_rate": round(sum(1 for q in queries if q["cold"]["source"] != "rag_llm") / len(queries), 4),
        "degraded_rate": round(len(degraded) / len(queries), 4),
        "gemini_generate_failure_rate": round(http["generate"]["non_200"] / http["generate"]["attempts"], 4),
        "gemini_embed_failure_rate": round(http["embed"]["non_200"] / http["embed"]["attempts"], 4),
        "http_calls": http,
    }

    # Diversity and coverage of what production showed (top 5 per query).
    seen, ild_cat, authors = Counter(), [], []
    for q in queries:
        books = [by_isbn.get(normalize_isbn(b)) for b in q["cold"]["books"]]
        books = [b for b in books if b]
        for b in books:
            seen[normalize_isbn(b["isbn13"])] += 1
        if len(books) >= 2:
            cats = [str(b.get("categories") or "").split(",")[0].strip().lower() for b in books]
            firsts = [str(b.get("authors") or "").split(",")[0].strip().lower() for b in books]
            ild_cat.append(len(set(cats)) / len(cats))
            authors.append(len(set(firsts)) / len(firsts))
    out["diversity"] = {
        "distinct_primary_category_share@5_mean": round(sum(ild_cat) / len(ild_cat), 3),
        "distinct_first_author_share@5_mean": round(sum(authors) / len(authors), 3),
    }
    out["coverage"] = {
        "distinct_books_shown": len(seen), "slots": sum(seen.values()),
        "catalog_coverage": round(len(seen) / len(df), 4),
    }
    out["most_repeated_books"] = [
        {"isbn13": i, "title": by_isbn[i]["title"], "queries": n} for i, n in seen.most_common(10)]

    # Per-query quality (scored queries only), production top 5.
    scored = [(qid, float(r["production_top5.ndcg@5"]), r) for qid, r in rows.items()
              if r.get("production_top5.ndcg@5") not in ("", None)]
    scored.sort(key=lambda t: (t[1], t[0]))
    fmt = lambda t: {"id": t[0], "category": t[2]["category"], "tier": t[2]["label_tier"], "ndcg@5": t[1],  # noqa: E731
                     "recall@5": float(t[2]["production_top5.recall@5"] or 0)}
    out["bottom_10"] = [fmt(t) for t in scored[:10]]
    out["top_10"] = [fmt(t) for t in sorted(scored, key=lambda t: (-t[1], t[0]))[:10]]
    out["n_scored"] = len(scored)

    # Retrieval fine but answer problematic, and answer fine but retrieval weak.
    qmap = {q["id"]: q for q in queries}
    answer_issues = []
    for q in queries:
        g = q["cold"].get("grounding") or {}
        flags = [k for k in ("language_mismatch", "unsupported") if g.get(k)]
        if g.get("foreign_author_names"):
            flags.append("foreign_author_names")
        if flags:
            nd = rows.get(q["id"], {}).get("production_top5.ndcg@5")
            answer_issues.append({"id": q["id"], "flags": flags, "ndcg@5": float(nd) if nd else None})
    out["answer_issues"] = answer_issues
    out["gemini_answer_but_weak_retrieval"] = [
        {"id": qid, "ndcg@5": v, "category": r["category"], "tier": r["label_tier"]}
        for qid, v, r in scored if v < 0.3 and qmap[qid]["cold"]["source"] == "rag_llm"]
    out["adversarial"] = run["evaluation"].get("answer_reliability", {}).get("adversarial")
    path = os.path.join(REPORTS, "rag_live_analysis.json")
    json.dump(out, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=dict)
    print(json.dumps(out, indent=1, ensure_ascii=False, default=dict))


if __name__ == "__main__":
    main()
