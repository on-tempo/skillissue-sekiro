"""Integration tests for a disposable local PostgreSQL database, never production.

Set TEST_DATABASE_URL explicitly. Only loopback hosts and database names beginning
with skillissue_test_ are accepted. Each run creates and removes its own schema.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from fastapi.testclient import TestClient


def test_url():
    value = os.environ.get('TEST_DATABASE_URL', '')
    if not value:
        raise RuntimeError('Set TEST_DATABASE_URL to a disposable local test database.')
    try:
        config = conninfo_to_dict(value)
    except Exception:
        raise RuntimeError('Invalid TEST_DATABASE_URL.') from None
    if (config.get('host') not in {'127.0.0.1', 'localhost', '::1'}
            or not config.get('dbname', '').startswith('skillissue_test_')
            or any(key in config for key in ('hostaddr', 'service', 'options'))):
        raise RuntimeError('Only loopback skillissue_test_* databases are allowed.')
    # Drop ambient libpq overrides before opening any connection.
    for key in list(os.environ):
        if key.startswith('PG'):
            del os.environ[key]
    return make_conninfo(value, connect_timeout=10)


def main():
    url = test_url()
    schema = 'api_test_' + uuid4().hex
    for key in ('RAILWAY_ENVIRONMENT', 'RAILWAY_ENVIRONMENT_ID', 'APP_ENV'):
        os.environ.pop(key, None)
    os.environ['DEVICE_SECRET'] = uuid4().hex + uuid4().hex
    os.environ['MAX_PER_HOUR'] = '60'
    os.environ['RETENTION_DAYS'] = '90'
    os.environ['DATABASE_URL'] = make_conninfo(url, options=f'-c search_path={schema} -c statement_timeout=15000')
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        try:
            import app as backend
            import db
            run = dict(boss='isshin', heals=2, revives=0, charmless=False,
                       bell=False, prosthetic=True, art=False, cleared=True)

            # Concurrent first connections exercise schema initialization too.
            def connect_once(_):
                conn = db.connect()
                try:
                    assert conn.pg
                    assert conn.execute('SELECT COUNT(*) FROM submissions').fetchone()[0] == 0
                finally:
                    conn.close()
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(connect_once, range(8)))

            with TestClient(backend.app) as client:
                assert client.get('/healthz').json() == {'ok': True, 'storage': 'postgresql'}
                first = client.post('/api/submit', json=run)
                assert first.status_code == 200, first.text
                assert first.json()['score'] == 90
                assert first.json()['submission'] == 'saved'
                repeat = client.post('/api/submit', json=run)
                assert repeat.json()['submission'] == 'duplicate'
                cookie = client.cookies.get(backend.COOKIE)

            # Check persistence through a separate physical connection.
            with psycopg.connect(os.environ['DATABASE_URL']) as observer:
                assert observer.execute('SELECT score FROM submissions').fetchall() == [(90,)]

            def race(payloads):
                barrier = Barrier(len(payloads))
                def send(payload):
                    with TestClient(backend.app) as client:
                        client.cookies.set(backend.COOKIE, cookie)
                        barrier.wait(timeout=15)
                        return client.post('/api/submit', json=payload)
                with ThreadPoolExecutor(max_workers=len(payloads)) as pool:
                    return list(pool.map(send, payloads))

            responses = race([dict(run, heals=3)] * 8)
            assert all(r.status_code == 200 for r in responses)
            assert sum(r.json()['submission'] == 'saved' for r in responses) == 1

            # Bring this visitor to 59 records, then race for the last available slot.
            with TestClient(backend.app) as client:
                client.cookies.set(backend.COOKIE, cookie)
                for heals in range(4, 61):
                    assert client.post('/api/submit', json=dict(run, heals=heals)).status_code == 200
            responses = race([dict(run, heals=heals) for heals in range(100, 108)])
            assert sum(r.status_code == 200 for r in responses) == 1
            assert sum(r.status_code == 429 for r in responses) == 7

            with TestClient(backend.app) as client:
                client.cookies.set(backend.COOKIE, cookie)
                assert client.post('/api/submit', json=run).json()['submission'] == 'duplicate'
                ranking = client.get('/api/percentile', params={'boss': 'isshin', 'score': 90}).json()
                assert ranking['status'] == 'ok' and ranking['n'] == 60, ranking
                assert ranking['top_percent'] == 2, ranking
                for _ in range(5):
                    assert client.get('/api/percentile', params={'boss': 'isshin', 'score': 0}).json()['top_percent'] == 32
                separate = client.get('/api/percentile', params={'boss': 'isshin', 'score': 90, 'charmless': True}).json()
                assert separate == {'status': 'collecting', 'n': 0, 'min_n': 20}
            with psycopg.connect(os.environ['DATABASE_URL']) as observer:
                assert observer.execute('SELECT COUNT(*) FROM submissions').fetchone()[0] == 60
            print('PostgreSQL: persistence, duplicate race, quota race, free lookup and cohort isolation passed.')
        finally:
            # Only the randomly named schema created by this test is removed.
            admin.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


if __name__ == '__main__':
    main()
