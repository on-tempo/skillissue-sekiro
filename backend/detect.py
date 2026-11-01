"""Offline anomaly detection. Run on a schedule:  python detect.py [--dry-run]

Design: ML proposes, rules confirm, humans can override.
  1. Build per-DEVICE behaviour features from the raw log.
  2. Isolation Forest scores how unusual each device is vs. the crowd.
  3. A device is flagged only if it is an ML outlier AND shows >=1 hard, explainable signal.
  4. Flagged submissions get excluded=1 (hidden from percentiles, not deleted/banned).
Re-running is idempotent: old 'ml' flags are cleared first.
'manual'/'duplicate' flags are untouched.
"""

import argparse
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

import db

# Devices with fewer submissions can't be judged by behaviour
# (only the realtime rules in app.py apply to them).
MIN_SUBS = 3
FEATURES = [
    "log_n",
    "max_per_hour",
    "frac_perfect",
    "dup_share",
    "n_bosses",
    "log_median_gap",
    "mean_score",
    "std_score",
]


def build_features(conn) -> pd.DataFrame:
    cols = [
        "device",
        "ts",
        "boss",
        "heals",
        "revives",
        "charmless",
        "bell",
        "prosthetic",
        "art",
        "score",
    ]
    rows_ = conn.execute(
        "SELECT " + ", ".join(cols) + " FROM submissions "
        "WHERE flag_reason IS NULL OR flag_reason='ml' OR flag_reason LIKE 'ml:%'"
    ).fetchall()
    df = pd.DataFrame(rows_, columns=cols)
    rows = []
    for dev, g in df.groupby("device"):
        g = g.sort_values("ts")
        n = len(g)
        if n < MIN_SUBS:
            continue
        ts = g["ts"].to_numpy()
        # busiest 1-hour window (two-pointer via searchsorted)
        per_hour = np.searchsorted(ts, ts + 3600, side="right") - np.arange(n)
        gaps = np.diff(ts)
        key = (
            g[["boss", "heals", "revives", "charmless", "bell", "prosthetic", "art"]]
            .astype(str)
            .agg("|".join, axis=1)
        )
        rows.append(
            {
                "device": dev,
                "n": n,
                "log_n": np.log1p(n),
                "max_per_hour": int(per_hour.max()),
                "frac_perfect": float(((g.heals == 0) & (g.revives == 0)).mean()),
                "dup_share": float(key.value_counts().iloc[0] / n),
                "n_bosses": g.boss.nunique(),
                "log_median_gap": float(np.log1p(np.median(gaps))),
                "mean_score": float(g.score.mean()),
                "std_score": float(g.score.std(ddof=0)),
            }
        )
    return (
        pd.DataFrame(rows).set_index("device")
        if rows
        else pd.DataFrame(columns=FEATURES)
    )


def hard_signal(r) -> str | None:
    """Explainable rules. Gives a human-readable reason for every flag."""
    if r.max_per_hour >= 5:
        return f"burst: {int(r.max_per_hour)} submissions within 1h"
    if r.dup_share >= 0.6 and r.n >= 4:
        return f"repeated identical record ({r.dup_share:.0%} of {int(r.n)})"
    if r.frac_perfect >= 0.9 and r.n >= 5:
        return f"{r.frac_perfect:.0%} of {int(r.n)} runs are 0 heals / 0 revives"
    return None


def run(conn, contamination=0.10, dry=False, seed=0) -> pd.DataFrame:
    feats = build_features(conn)
    if len(feats) < 30:
        print(
            f"Only {len(feats)} devices with >= {MIN_SUBS} submissions; "
            "not enough to model. Skipping."
        )
        return pd.DataFrame()
    model = IsolationForest(
        n_estimators=300, contamination=contamination, random_state=seed
    )
    model.fit(feats[FEATURES])
    feats["anomaly"] = -model.score_samples(feats[FEATURES])  # higher = weirder
    feats["is_outlier"] = model.predict(feats[FEATURES]) == -1
    feats["reason"] = [hard_signal(r) for r in feats.itertuples()]
    flagged = feats[feats.is_outlier & feats.reason.notna()].sort_values(
        "anomaly", ascending=False
    )

    if not dry:
        conn.execute(
            "UPDATE submissions SET excluded=0, flag_reason=NULL WHERE flag_reason='ml' OR flag_reason LIKE 'ml:%'"
        )
        conn.executemany(
            "UPDATE submissions SET excluded=1, flag_reason=? "
            "WHERE device=? AND flag_reason IS NULL",
            [("ml:" + row.reason, device) for device, row in flagged.iterrows()],
        )
        conn.commit()
    return flagged


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--db", default=None, help="sqlite path; default: DATABASE_URL or DB_PATH"
    )
    ap.add_argument("--contamination", type=float, default=0.10)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    conn = db.connect(a.db)
    out = run(conn, a.contamination, a.dry_run)
    print(f"{'(dry run) ' if a.dry_run else ''}flagged {len(out)} devices")
    if len(out):
        print(
            out[["n", "max_per_hour", "frac_perfect", "dup_share", "anomaly", "reason"]]
            .round(2)
            .to_string()
        )
