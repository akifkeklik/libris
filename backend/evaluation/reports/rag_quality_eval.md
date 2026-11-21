# RAG quality evaluation (live) - 2026-11-22T00:24:46+0300

Embedding profile `models/gemini-embedding-2;dim=3072;text=canonical_v1;task=RETRIEVAL_DOCUMENT`, query format `legacy`; vector port `SupabaseBookDataPort`; LLM `gemini-3.5-flash-lite`. Labels: see `label_tiers` in the dataset; human-verified intents: none.

## Retrieval (rule_derived)

| group | system | n | Hit@5 | R@5 | R@10 | P@5 | P@10 | MRR@5 | MRR@10 | nDCG@5 | nDCG@10 | empty |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all | production_top5 | 19 | 1.0 | 0.979 | – | 0.474 | – | 1.0 | – | 0.982 | – | 0.0 |
| all | semantic_rpc_top10 | 19 | 1.0 | 0.979 | 0.974 | 0.474 | 0.384 | 0.974 | 0.974 | 0.965 | 0.96 | 0.0 |
| all | semantic_exact_top10 | 19 | 1.0 | 0.979 | 0.974 | 0.474 | 0.384 | 0.974 | 0.974 | 0.965 | 0.96 | 0.0 |
| en | production_top5 | 8 | 1.0 | 0.975 | – | 0.475 | – | 1.0 | – | 0.979 | – | 0.0 |
| en | semantic_rpc_top10 | 8 | 1.0 | 0.975 | 0.963 | 0.475 | 0.375 | 1.0 | 1.0 | 0.979 | 0.97 | 0.0 |
| en | semantic_exact_top10 | 8 | 1.0 | 0.975 | 0.963 | 0.475 | 0.375 | 1.0 | 1.0 | 0.979 | 0.97 | 0.0 |
| tr (Turkish letters) | production_top5 | 8 | 1.0 | 0.975 | – | 0.475 | – | 1.0 | – | 0.979 | – | 0.0 |
| tr (Turkish letters) | semantic_rpc_top10 | 8 | 1.0 | 0.975 | 0.975 | 0.475 | 0.388 | 0.938 | 0.938 | 0.937 | 0.935 | 0.0 |
| tr (Turkish letters) | semantic_exact_top10 | 8 | 1.0 | 0.975 | 0.975 | 0.475 | 0.388 | 0.938 | 0.938 | 0.937 | 0.935 | 0.0 |
| tr (ASCII-typed) | production_top5 | 3 | 1.0 | 1.0 | – | 0.467 | – | 1.0 | – | 1.0 | – | 0.0 |
| tr (ASCII-typed) | semantic_rpc_top10 | 3 | 1.0 | 1.0 | 1.0 | 0.467 | 0.4 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| tr (ASCII-typed) | semantic_exact_top10 | 3 | 1.0 | 1.0 | 1.0 | 0.467 | 0.4 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |

## Retrieval (proposed)

| group | system | n | Hit@5 | R@5 | R@10 | P@5 | P@10 | MRR@5 | MRR@10 | nDCG@5 | nDCG@10 | empty |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all | production_top5 | 21 | 0.952 | 0.586 | – | 0.457 | – | 0.786 | – | 0.605 | – | 0.0 |
| all | semantic_rpc_top10 | 21 | 0.905 | 0.538 | 0.67 | 0.41 | 0.338 | 0.655 | 0.671 | 0.53 | 0.6 | 0.0 |
| all | semantic_exact_top10 | 21 | 0.905 | 0.538 | 0.67 | 0.41 | 0.338 | 0.655 | 0.671 | 0.53 | 0.6 | 0.0 |
| en | production_top5 | 10 | 0.9 | 0.56 | – | 0.44 | – | 0.717 | – | 0.569 | – | 0.0 |
| en | semantic_rpc_top10 | 10 | 0.9 | 0.5 | 0.647 | 0.38 | 0.35 | 0.608 | 0.625 | 0.486 | 0.577 | 0.0 |
| en | semantic_exact_top10 | 10 | 0.9 | 0.5 | 0.647 | 0.38 | 0.35 | 0.608 | 0.625 | 0.486 | 0.577 | 0.0 |
| tr (Turkish letters) | production_top5 | 10 | 1.0 | 0.62 | – | 0.5 | – | 0.833 | – | 0.64 | – | 0.0 |
| tr (Turkish letters) | semantic_rpc_top10 | 10 | 0.9 | 0.58 | 0.66 | 0.46 | 0.34 | 0.667 | 0.683 | 0.567 | 0.602 | 0.0 |
| tr (Turkish letters) | semantic_exact_top10 | 10 | 0.9 | 0.58 | 0.66 | 0.46 | 0.34 | 0.667 | 0.683 | 0.567 | 0.602 | 0.0 |
| tr (ASCII-typed) | production_top5 | 1 | 1.0 | 0.5 | – | 0.2 | – | 1.0 | – | 0.613 | – | 0.0 |
| tr (ASCII-typed) | semantic_rpc_top10 | 1 | 1.0 | 0.5 | 1.0 | 0.2 | 0.2 | 1.0 | 1.0 | 0.613 | 0.818 | 0.0 |
| tr (ASCII-typed) | semantic_exact_top10 | 1 | 1.0 | 0.5 | 1.0 | 0.2 | 0.2 | 1.0 | 1.0 | 0.613 | 0.818 | 0.0 |

## Retrieval (automatic_candidate)

| group | system | n | Hit@5 | R@5 | R@10 | P@5 | P@10 | MRR@5 | MRR@10 | nDCG@5 | nDCG@10 | empty |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all | production_top5 | 60 | 0.883 | 0.703 | – | 0.41 | – | 0.717 | – | 0.661 | – | 0.0 |
| all | semantic_rpc_top10 | 60 | 0.95 | 0.677 | 0.719 | 0.4 | 0.372 | 0.734 | 0.738 | 0.655 | 0.674 | 0.0 |
| all | semantic_exact_top10 | 60 | 0.95 | 0.677 | 0.719 | 0.4 | 0.372 | 0.734 | 0.738 | 0.655 | 0.674 | 0.0 |
| en | production_top5 | 30 | 0.867 | 0.707 | – | 0.413 | – | 0.756 | – | 0.683 | – | 0.0 |
| en | semantic_rpc_top10 | 30 | 0.967 | 0.697 | 0.699 | 0.42 | 0.367 | 0.761 | 0.761 | 0.682 | 0.681 | 0.0 |
| en | semantic_exact_top10 | 30 | 0.967 | 0.697 | 0.699 | 0.42 | 0.367 | 0.761 | 0.761 | 0.682 | 0.681 | 0.0 |
| tr (Turkish letters) | production_top5 | 30 | 0.9 | 0.7 | – | 0.407 | – | 0.678 | – | 0.638 | – | 0.0 |
| tr (Turkish letters) | semantic_rpc_top10 | 30 | 0.933 | 0.657 | 0.739 | 0.38 | 0.377 | 0.707 | 0.716 | 0.628 | 0.668 | 0.0 |
| tr (Turkish letters) | semantic_exact_top10 | 30 | 0.933 | 0.657 | 0.739 | 0.38 | 0.377 | 0.707 | 0.716 | 0.628 | 0.667 | 0.0 |

"–" = not applicable: production answers with at most 5 books, so it has no @10 metrics.

## Dataset composition

120 queries in the dataset, 120 in this run; 20 have no labelled set and are judged by behaviour only.

```json
{
 "by_category": {
  "ambiguous": 8,
  "author": 15,
  "exact_title": 17,
  "genre": 12,
  "insufficient_info": 6,
  "mood": 4,
  "multi_constraint": 6,
  "no_relevant": 6,
  "semantic_description": 17,
  "similar": 14,
  "topic": 15
 },
 "by_language": {
  "en": 58,
  "tr": 62
 },
 "by_tier": {
  "automatic_candidate": 76,
  "open": 4,
  "proposed": 21,
  "rule_derived": 19
 },
 "by_difficulty": {
  "easy": 20,
  "hard": 24,
  "medium": 32,
  "unrated": 44
 },
 "by_expected_behavior": {
  "abstain_not_in_catalog": 6,
  "no_fabrication": 6,
  "open_judgment": 8,
  "retrieve_relevant": 100
 },
 "by_dataset": {
  "base": 44,
  "expansion": 76
 }
}
```

## By category (all tiers mixed; see the per-query CSV for each row's tier)

| category | n | production Hit@5 | production nDCG@5 | semantic nDCG@5 | semantic nDCG@10 |
|---|---|---|---|---|---|
| author | 15 | 1.0 | 0.977 | 0.947 | 0.943 |
| exact_title | 17 | 1.0 | 0.945 | 0.971 | 0.971 |
| genre | 12 | 1.0 | 0.505 | 0.539 | 0.546 |
| mood | 4 | 0.5 | 0.245 | 0.304 | 0.315 |
| multi_constraint | 6 | 0.167 | 0.022 | 0.176 | 0.184 |
| semantic_description | 17 | 1.0 | 0.913 | 0.861 | 0.878 |
| similar | 14 | 0.929 | 0.53 | 0.428 | 0.485 |
| topic | 15 | 1.0 | 0.678 | 0.578 | 0.669 |

## Paired EN vs TR (nDCG@5, same intent)

| intent | tier | production EN | production TR | semantic EN | semantic TR |
|---|---|---|---|---|---|
| author_asimov | automatic_candidate | 1.000 | 1.000 | 0.786 | 0.854 |
| author_christie | rule_derived | 1.000 | 1.000 | 1.000 | 1.000 |
| author_king | automatic_candidate | 1.000 | 1.000 | 0.869 | 1.000 |
| author_orwell | rule_derived | 1.000 | 1.000 | 1.000 | 1.000 |
| author_pratchett | automatic_candidate | 1.000 | 1.000 | 1.000 | 1.000 |
| author_tolkien | rule_derived | 0.830 | 0.830 | 0.830 | 0.869 |
| author_woolf | automatic_candidate | 1.000 | 1.000 | 1.000 | 1.000 |
| desc_alice | rule_derived | 1.000 | 1.000 | 1.000 | 1.000 |
| desc_dracula | automatic_candidate | 1.000 | 1.000 | 1.000 | 1.000 |
| desc_flies | automatic_candidate | 1.000 | 1.000 | 1.000 | 1.000 |
| desc_frankenstein | automatic_candidate | 0.631 | 0.631 | 0.000 | 0.000 |
| desc_hp | rule_derived | 1.000 | 1.000 | 1.000 | 0.631 |
| desc_kafka | rule_derived | 1.000 | 1.000 | 1.000 | 1.000 |
| desc_moby | automatic_candidate | 0.631 | 0.631 | 1.000 | 1.000 |
| desc_road | automatic_candidate | 1.000 | 1.000 | 1.000 | 1.000 |
| genre_comics | automatic_candidate | 0.515 | 0.491 | 0.170 | 0.301 |
| genre_cooking | automatic_candidate | 0.786 | 0.214 | 0.699 | 0.553 |
| genre_detective | proposed | 0.301 | 0.723 | 0.384 | 0.515 |
| genre_horror | proposed | 0.553 | 0.470 | 0.661 | 0.830 |
| genre_poetry | automatic_candidate | 0.684 | 0.854 | 0.640 | 0.655 |
| genre_scifi | automatic_candidate | 0.339 | 0.131 | 0.553 | 0.509 |
| mood_funny | automatic_candidate | 0.000 | 0.000 | 0.277 | 0.277 |
| mood_scary | automatic_candidate | 0.470 | 0.509 | 0.515 | 0.146 |
| multi_history_recent | automatic_candidate | 0.000 | 0.000 | 0.237 | 0.264 |
| multi_king_short | automatic_candidate | 0.000 | 0.000 | 0.277 | 0.146 |
| multi_poetry_short | automatic_candidate | 0.000 | 0.131 | 0.131 | 0.000 |
| sim_1984 | proposed | 0.363 | 0.363 | 0.363 | 0.363 |
| sim_austen | proposed | 0.655 | 0.530 | 0.384 | 0.491 |
| sim_dune | proposed | 0.000 | 0.339 | 0.000 | 0.000 |
| sim_handmaid | automatic_candidate | 0.170 | 0.131 | 0.447 | 0.131 |
| sim_hitchhiker | automatic_candidate | 1.000 | 0.869 | 1.000 | 0.830 |
| sim_hp | proposed | 0.515 | 0.661 | 0.146 | 0.301 |
| sim_sherlock | automatic_candidate | 0.830 | 1.000 | 0.869 | 0.661 |
| title_crime | rule_derived | 1.000 | 1.000 | 1.000 | 1.000 |
| title_fahrenheit | automatic_candidate | 1.000 | 0.631 | 1.000 | 1.000 |
| title_handmaid | automatic_candidate | 1.000 | 1.000 | 1.000 | 1.000 |
| title_hobbit | rule_derived | 1.000 | 1.000 | 1.000 | 1.000 |
| title_kite | automatic_candidate | 1.000 | 1.000 | 1.000 | 1.000 |
| title_little_prince | automatic_candidate | 1.000 | 1.000 | 1.000 | 1.000 |
| title_pride | automatic_candidate | 1.000 | 0.431 | 1.000 | 0.500 |
| title_rose | automatic_candidate | 1.000 | 1.000 | 1.000 | 1.000 |
| topic_buddhism | automatic_candidate | 0.447 | 0.491 | 0.146 | 0.170 |
| topic_cosmology | automatic_candidate | 0.786 | 0.786 | 0.616 | 0.470 |
| topic_habits | proposed | 0.967 | 1.000 | 0.967 | 1.000 |
| topic_robots | proposed | 0.723 | 0.699 | 0.339 | 0.553 |
| topic_rome | proposed | 0.613 | 0.613 | 0.613 | 0.613 |
| topic_stoic | proposed | 1.000 | 1.000 | 1.000 | 1.000 |
| topic_wwii | automatic_candidate | 0.214 | 0.214 | 0.214 | 0.360 |

## Performance

```json
{
 "end_to_end_cold_all": {
  "n": 120,
  "p50": 2489.9,
  "p95": 3330.1,
  "max": 4653.3
 },
 "end_to_end_cold_gemini_answers": {
  "n": 119,
  "p50": 2489.9,
  "p95": 3330.1,
  "max": 4653.3
 },
 "end_to_end_cold_deterministic_catalog": {
  "n": 0,
  "p50": null,
  "p95": null,
  "max": null
 },
 "end_to_end_cold_llm_fallback": {
  "n": 0,
  "p50": null,
  "p95": null,
  "max": null
 },
 "end_to_end_warm_query_cache": {
  "n": 120,
  "p50": 0.4,
  "p95": 0.8,
  "max": 4761.5
 },
 "query_embedding": {
  "n": 120,
  "p50": 435.0,
  "p95": 534.5,
  "max": 1210.5
 },
 "vector_rpc": {
  "n": 120,
  "p50": 248.5,
  "p95": 619.0,
  "max": 1407.5
 },
 "gemini_generation": {
  "n": 120,
  "p50": 1097.7,
  "p95": 1763.8,
  "max": 3022.8
 },
 "http_calls": {
  "generate": {
   "attempts": 132,
   "non_200": 1,
   "status_counts": {
    "200": 131,
    "503": 1
   }
  },
  "embed": {
   "attempts": 134,
   "non_200": 3,
   "status_counts": {
    "200": 131,
    "429": 3
   }
  }
 },
 "model_versions": [
  "gemini-3.5-flash-lite"
 ],
 "tokens_generate": {
  "promptTokenCount": {
   "sum": 137467,
   "n_calls_with_usage": 131,
   "mean": 1049.4
  },
  "candidatesTokenCount": {
   "sum": 29680,
   "n_calls_with_usage": 131,
   "mean": 226.6
  },
  "thoughtsTokenCount": {
   "sum": 0,
   "n_calls_with_usage": 0,
   "mean": null
  },
  "totalTokenCount": {
   "sum": 167147,
   "n_calls_with_usage": 131,
   "mean": 1275.9
  }
 },
 "tokens_embed": {
  "promptTokenCount": {
   "sum": 1153,
   "n_calls_with_usage": 131,
   "mean": 8.8
  },
  "totalTokenCount": {
   "sum": 0,
   "n_calls_with_usage": 0,
   "mean": null
  }
 },
 "warm_served_from_cache": 119,
 "warm_http_calls": 3
}
```

## Answer reliability

```json
{
 "statuses": {
  "success": 119,
  "lexical_fallback": 1
 },
 "sources": {
  "rag_llm": 120
 },
 "gemini_answers": 120,
 "context_delivered_rate": 1.0,
 "answers_with_foreign_isbn": 0,
 "answers_with_foreign_catalog_title": 0,
 "answers_with_foreign_author": 3,
 "unsupported_claim_rate": 0.025,
 "answers_with_spans_for_review": 0,
 "answers_in_wrong_language": [
  "genre_cooking_en",
  "title_fahrenheit_en",
  "title_fahrenheit_tr"
 ],
 "source_attribution_errors": [],
 "adversarial": {
  "cases": 12,
  "all_checks_passed": 12,
  "failures": {}
 },
 "behaviour_checks": {
  "abstain_not_in_catalog": {
   "n": 6,
   "passed": 6,
   "failures": []
  },
  "no_fabrication": {
   "n": 6,
   "passed": 5,
   "failures": [
    "insuff_one_word_en"
   ]
  }
 }
}
```
