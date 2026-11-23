"""The catalog frame is shared by all request threads: answering a question must never write to it.

Regression: the AI catalog lookup added columns to it on first use; two simultaneous first chats
corrupted it and every recommendation failed until restart (seen in CI as "Length of values (17)
does not match length of index (16)" and "index 785 is out of bounds for axis 0 with size 7").
"""

import sys
import threading
from types import SimpleNamespace

import pandas as pd
import pytest
from backend.application.use_cases.ai_rag import ProcessRagQueryUseCase

pytestmark = pytest.mark.unit


def _catalog(n=300):
    return pd.DataFrame({"isbn13": [f"978{i:010d}" for i in range(n)], "title": [f"Title {i}" for i in range(n)],
                         "authors": [f"Author {i}" for i in range(n)], "description": [""] * n})


def _uc(df):
    uc = ProcessRagQueryUseCase.__new__(ProcessRagQueryUseCase)
    uc._recommender = SimpleNamespace(df=df)
    return uc


def test_lookup_does_not_modify_the_shared_catalog():
    df = _catalog()
    before = list(df.columns)
    assert _uc(df)._lookup_catalog_candidates("Title 7")[0]["title"] == "Title 7"
    assert list(df.columns) == before


def test_simultaneous_first_lookups_leave_the_catalog_readable():
    interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        for _ in range(25):
            df = _catalog()
            uc, barrier, errors = _uc(df), threading.Barrier(6), []

            def ask():
                barrier.wait()
                try:
                    assert uc._lookup_catalog_candidates("Title 7")
                except Exception as exc:  # collected: an error in a thread must fail the test
                    errors.append(exc)

            threads = [threading.Thread(target=ask) for _ in range(6)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            assert not errors
            assert len(df.iloc[[1, 2]].to_dict("records")) == 2 and df.iloc[299]["title"] == "Title 299"
    finally:
        sys.setswitchinterval(interval)


def test_a_book_contributed_after_the_first_question_is_found():
    uc = _uc(_catalog())
    assert uc._lookup_catalog_candidates("Title 7")
    new = pd.DataFrame([{"isbn13": "9790000000001", "title": "Whale Songs", "authors": "New Reader", "description": ""}])
    uc._recommender.df = pd.concat([uc._recommender.df, new], ignore_index=True)
    assert uc._lookup_catalog_candidates("Whale Songs")[0]["isbn13"] == "9790000000001"
