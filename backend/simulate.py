"""Synthetic data + evaluation. Lets you test the detector BEFORE you have real users.
Ground truth is known here, so we can measure recall and false positives.
Caveat: results are only as realistic as the generator below. Re-tune on real data."""

import os, sys, tempfile
import numpy as np
import db, detect

rng = np.random.default_rng(42)
BOSSES = ["genichiro", "ape", "isshin"]
LAMBDA = {"genichiro": 4, "ape": 6, "isshin": 8}  # mean healing uses by boss (made up)
T0 = 1_760_000_000
label = {}


def one_run(boss, skill=1.0):
    heals = int(rng.poisson(LAMBDA[boss] * skill))
    revives = int(rng.poisson(0.4 * skill))
    return dict(
        boss=boss,
        heals=heals,
        revives=revives,
        charmless=bool(rng.random() < 0.1),
        bell=bool(rng.random() < 0.15),
        prosthetic=bool(rng.random() < 0.8),
        art=bool(rng.random() < 0.7),
    )


def add(conn, dev, kind, ts, run):
    label[dev] = kind
    db.insert(conn, ts=int(ts), device=dev, **run)


def gen(conn):
    # --- legit players ---
    for i in range(1500):
        n = 1 + min(int(rng.geometric(0.55)) - 1, 5)  # mostly 1-3 submissions
        skill = float(rng.choice([0.2, 0.6, 1.0, 1.4], p=[0.05, 0.25, 0.5, 0.2]))
        t = T0 + rng.uniform(0, 30 * 86400)
        for _ in range(n):
            add(conn, f"n{i}", "normal", t, one_run(rng.choice(BOSSES), skill))
            t += rng.lognormal(mean=9, sigma=1.5)  # median ~2h, heavy tail
    for i in range(40):  # enthusiasts: 6-12 runs, quick gaps
        t = T0 + rng.uniform(0, 25 * 86400)
        for _ in range(int(rng.integers(6, 13))):
            add(conn, f"p{i}", "normal", t, one_run(rng.choice(BOSSES), skill=0.5))
            t += rng.lognormal(mean=7.5, sigma=1.0)
    for i in range(30):  # legit skilled: some 0/0 runs
        t = T0 + rng.uniform(0, 25 * 86400)
        for _ in range(int(rng.integers(3, 6))):
            r = one_run(rng.choice(BOSSES), 0.1)
            add(conn, f"s{i}", "normal", t, r)
            t += rng.lognormal(mean=10, sigma=1.0)
    # --- cheaters ---
    for i in range(20):  # spam bot: 30 perfect runs in 10 min
        t = T0 + rng.uniform(0, 25 * 86400)
        for _ in range(30):
            add(
                conn,
                f"spam{i}",
                "spammer",
                t,
                dict(one_run(rng.choice(BOSSES)), heals=0, revives=0),
            )
            t += rng.uniform(5, 30)
    for i in range(15):  # re-submitter: same record repeatedly
        t = T0 + rng.uniform(0, 25 * 86400)
        r = dict(one_run("isshin"), heals=0, revives=0)
        for _ in range(12):
            add(conn, f"dup{i}", "resubmit", t, r)
            t += rng.uniform(600, 7200)
    for i in range(15):  # slow farmer: always perfect, varied bosses
        t = T0 + rng.uniform(0, 20 * 86400)
        for _ in range(8):
            add(
                conn,
                f"farm{i}",
                "farmer",
                t,
                dict(one_run(rng.choice(BOSSES)), heals=0, revives=0),
            )
            t += rng.uniform(3600, 86400)
    for i in range(100):  # one-shot perfect score
        add(
            conn,
            f"one{i}",
            "stealth",
            T0 + rng.uniform(0, 30 * 86400),
            dict(one_run("isshin"), heals=0, revives=0),
        )


if __name__ == "__main__":
    path = os.path.join(tempfile.mkdtemp(), "sim.db")
    conn = db.connect(path)
    gen(conn)
    conn.commit()
    flagged = detect.run(
        conn, contamination=float(sys.argv[1]) if len(sys.argv) > 1 else 0.10
    )
    hit = set(flagged.index)
    kinds = sorted(set(label.values()))
    print(f"{'type':10s} {'devices':>8s} {'flagged':>8s} {'rate':>7s}")
    for k in kinds:
        d = [x for x, v in label.items() if v == k]
        f = sum(x in hit for x in d)
        print(f"{k:10s} {len(d):8d} {f:8d} {f/len(d):7.0%}")
    tp = sum(label[x] not in ("normal", "stealth") for x in hit)
    fp = sum(label[x] == "normal" for x in hit)
    print(
        f"\nprecision (flagged that were real cheaters): "
        f"{tp/max(1,len(hit)):.0%}   false positives: {fp}"
    )
