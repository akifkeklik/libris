"""The API runs on several threads: connections, catalog changes and slow requests must not collide."""

import threading
import time
from pathlib import Path

import pytest
from backend.infrastructure.ml.recommender import BookRecommender
from backend.infrastructure.persistence import postgres_adapters as pg

pytestmark = pytest.mark.unit


class Conn:
    closed = 0
    autocommit = False


def test_each_thread_gets_its_own_connection_and_reuses_it(monkeypatch):
    monkeypatch.setattr(pg.psycopg2, "connect", lambda uri: Conn())
    repo = pg.PostgresNoteRepository("postgresql://test/threads")
    seen, barrier = [], threading.Barrier(4)

    def work():
        barrier.wait()
        first = repo._get_connection()
        seen.append((first, repo._get_connection() is first, first.autocommit))

    threads = [threading.Thread(target=work) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len({id(c) for c, _, _ in seen}) == 4
    assert all(same and auto for _, same, auto in seen)


def test_closed_connection_is_replaced_and_injected_connection_is_kept(monkeypatch):
    monkeypatch.setattr(pg.psycopg2, "connect", lambda uri: Conn())
    repo = pg.PostgresBookDataPort("postgresql://test/closed")
    first = repo._get_connection()
    first.closed = 1
    assert repo._get_connection() is not first
    injected = Conn()
    assert pg.PostgresNoteRepository(injected)._get_connection() is injected


def test_recommendations_survive_books_being_added_at_the_same_time():
    rec = BookRecommender()
    rec.load_from_dicts([{"isbn13": f"978{i:010d}", "title": f"Title {i}", "authors": f"Author {i % 40}",
                          "categories": "Fiction" if i % 2 else "History", "description": f"story {i % 30} of rivers and maps",
                          "thumbnail": "", "average_rating": 4, "ratings_count": 10, "published_date": "2000", "page_count": 100}
                         for i in range(300)])
    rec.fit()
    errors, stop = [], threading.Event()

    def read():
        while not stop.is_set():
            try:
                assert rec.recommend("Title 5", top_n=5)
                rec.lexical_search("rivers", limit=5)
            except Exception as exc:
                errors.append(repr(exc))
                return

    readers = [threading.Thread(target=read) for _ in range(4)]
    [t.start() for t in readers]
    for k in range(25):
        rec.add_book({"isbn13": f"979{k:010d}", "title": f"Added {k}", "authors": "New", "categories": "Fiction",
                      "description": "rivers", "thumbnail": "", "average_rating": 0, "ratings_count": 0,
                      "published_date": "2020", "page_count": 10})
    stop.set()
    [t.join() for t in readers]
    assert errors == []
    assert len(rec.df) == rec.tfidf_matrix.shape[0] == 325


def test_a_slow_request_does_not_block_the_others():
    """What the thread setting buys: with one thread /fast waits for /slow, with threads it does not."""
    import requests
    from flask import Flask
    from werkzeug.serving import make_server

    app = Flask(__name__)
    entered = threading.Event()

    @app.get("/slow")
    def slow():
        entered.set()
        time.sleep(1.5)
        return "ok"

    @app.get("/fast")
    def fast():
        return "ok"

    def fast_latency(threaded):
        entered.clear()
        server = make_server("127.0.0.1", 0, app, threaded=threaded)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_port}"
        t = threading.Thread(target=requests.get, args=(base + "/slow",))
        t.start()
        assert entered.wait(5)
        start = time.perf_counter()
        requests.get(base + "/fast", timeout=10)
        took = time.perf_counter() - start
        t.join()
        server.shutdown()
        return took

    assert fast_latency(False) > 0.8
    assert fast_latency(True) < 0.8


def test_container_runs_several_threads():
    cmd = (Path(__file__).parent.parent / "Dockerfile").read_text(encoding="utf-8")
    assert "--worker-class gthread" in cmd and "WEB_THREADS:-4" in cmd
