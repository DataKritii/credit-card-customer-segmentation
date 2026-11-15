"""
segmentation.py
===============
Reusable code for the customer segmentation in
notebooks/credit_card_segmentation_kmeans.ipynb, and the export of the tables
the Power BI report is built on.

Steps (identical to the notebook):
    1. Load the data, drop the one row with no credit limit, cap cash-advance frequency at 1
    2. Build 10 behavioural features: 6 log-transformed amounts, 3 frequencies/shares, utilization
    3. Standardise, then K-means with k = 6
    4. Name each segment with rules on its median behaviour (robust to cluster numbering)
    5. Export star-schema tables for Power BI

Regenerate the Power BI tables from the project folder with:
    python -m src.segmentation
"""

from __future__ import annotations

import os
import urllib.request
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

RANDOM_STATE = 42
K = 6
DATA_FILE = "CC GENERAL.csv"
DATA_URL = "https://raw.githubusercontent.com/rohitdileep/Credit-Card-Segmentation-using-Kmeans/main/CC_GENERAL.csv"

LOG_AMOUNTS = ["BALANCE", "ONEOFF_PURCHASES", "INSTALLMENTS_PURCHASES", "CASH_ADVANCE", "CREDIT_LIMIT", "PAYMENTS"]
FEATURES = ([f"log_{c.lower()}" for c in LOG_AMOUNTS]
            + ["purchases_frequency", "cash_advance_frequency", "prc_full_payment", "utilization"])

# Segment names, descriptions and suggested actions, keyed by the rule-based name
PERSONAS = {
    "Transactors": {
        "order": 1, "color": "#2E7D5B",
        "description": "Buy often and pay the full balance almost every month; carry almost no balance.",
        "action": "Rewards and premium card upgrades; little interest income, so keep them through value, not price.",
        "risk": "Low",
    },
    "High-limit spenders": {
        "order": 2, "color": "#2C3E50",
        "description": "High credit limits and the largest purchases, but use only a small part of their limit.",
        "action": "Spend-based offers and instalment plans for large purchases; good candidates for retention efforts.",
        "risk": "Low to moderate",
    },
    "Light users": {
        "order": 3, "color": "#95A5A6",
        "description": "Small balances and occasional small purchases; the card isn't their main one.",
        "action": "Activation campaigns (first-purchase bonus, digital wallet set-up); review dormant accounts.",
        "risk": "Low",
    },
    "Heavy all-rounders": {
        "order": 4, "color": "#D4A20B",
        "description": "The highest balances: they buy regularly, take cash advances and carry a balance.",
        "action": "Most profitable but exposed; balance-transfer and instalment offers, with close credit monitoring.",
        "risk": "Moderate to high",
    },
    "Near-limit revolvers": {
        "order": 5, "color": "#B9603A",
        "description": "Low limits used almost to the maximum, carrying a balance month to month.",
        "action": "Early-warning monitoring and payment-plan outreach; review before any limit increase.",
        "risk": "High",
    },
    "Cash-advance reliant": {
        "order": 6, "color": "#7B5EA7",
        "description": "Rarely buy anything; use the card mainly to withdraw cash, at high interest.",
        "action": "Offer lower-cost alternatives (personal loan, overdraft); monitor for financial stress.",
        "risk": "High",
    },
}

METRICS = [  # column, label, description, unit, sort order (used in the Power BI profile matrix)
    ("BALANCE", "Balance", "Average balance over the period", "amount", 1),
    ("PURCHASES", "Purchases", "Total purchases over the period", "amount", 2),
    ("ONEOFF_PURCHASES", "One-off purchases", "Purchases paid in one go", "amount", 3),
    ("INSTALLMENTS_PURCHASES", "Instalment purchases", "Purchases paid in instalments", "amount", 4),
    ("CASH_ADVANCE", "Cash advances", "Cash withdrawn on the card", "amount", 5),
    ("CREDIT_LIMIT", "Credit limit", "Credit limit", "amount", 6),
    ("PAYMENTS", "Payments", "Total payments made", "amount", 7),
    ("utilization", "Utilization", "Balance ÷ credit limit", "percent", 8),
    ("PURCHASES_FREQUENCY", "Purchase frequency", "Share of months with purchases", "percent", 9),
    ("CASH_ADVANCE_FREQUENCY", "Cash-advance frequency", "Share of months with a cash advance", "percent", 10),
    ("PRC_FULL_PAYMENT", "Full-payment rate", "Share of months the full balance was paid", "percent", 11),
    ("PURCHASES_TRX", "Purchase transactions", "Number of purchase transactions", "count", 12),
]


# --------------------------------------------------------------------------
# 1. Data and features
# --------------------------------------------------------------------------
def load_raw(data_dir: str) -> pd.DataFrame:
    path = os.path.join(data_dir, DATA_FILE)
    if not os.path.exists(path):
        os.makedirs(data_dir, exist_ok=True)
        urllib.request.urlretrieve(DATA_URL, path)
    return pd.read_csv(path)


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.dropna(subset=["CREDIT_LIMIT"]).reset_index(drop=True)          # 1 row without a limit
    df["CASH_ADVANCE_FREQUENCY"] = df["CASH_ADVANCE_FREQUENCY"].clip(upper=1)  # a share can't exceed 1
    df["utilization"] = (df["BALANCE"] / df["CREDIT_LIMIT"]).clip(upper=1.5)   # cap extreme over-limit values
    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    f = pd.DataFrame(index=df.index)
    for c in LOG_AMOUNTS:
        f[f"log_{c.lower()}"] = np.log1p(df[c])                                # log(1 + x): handles zeros, tames skew
    f["purchases_frequency"] = df["PURCHASES_FREQUENCY"]
    f["cash_advance_frequency"] = df["CASH_ADVANCE_FREQUENCY"]
    f["prc_full_payment"] = df["PRC_FULL_PAYMENT"]
    f["utilization"] = df["utilization"]
    return f


# --------------------------------------------------------------------------
# 2. Naming segments from their behaviour
# --------------------------------------------------------------------------
def name_segments(df: pd.DataFrame, labels: np.ndarray) -> dict[int, str]:
    """Assign persona names with simple rules on segment medians, so names don't
    depend on K-means' arbitrary cluster numbers."""
    med = df.assign(seg=labels).groupby("seg")[["BALANCE", "PURCHASES", "CASH_ADVANCE", "CREDIT_LIMIT",
                                                "PRC_FULL_PAYMENT", "utilization"]].median()
    names, left = {}, list(med.index)

    def take(seg, name):
        names[seg] = name
        left.remove(seg)

    take(med.loc[left, "PRC_FULL_PAYMENT"].idxmax(), "Transactors")                        # pays in full
    take(med.loc[left, "utilization"].idxmax(), "Near-limit revolvers")                    # highest utilization
    take((med.loc[left, "CASH_ADVANCE"] - med.loc[left, "PURCHASES"]).idxmax(), "Cash-advance reliant")
    take(med.loc[left, "BALANCE"].idxmin(), "Light users")                                 # smallest balance
    take(med.loc[left, "CASH_ADVANCE"].idxmax(), "Heavy all-rounders")                     # buys and withdraws cash
    take(left[0], "High-limit spenders")
    return names


# --------------------------------------------------------------------------
# 3. Fit
# --------------------------------------------------------------------------
@dataclass
class SegmentationResult:
    data: pd.DataFrame          # cleaned customers with segment columns
    X: np.ndarray               # standardised features
    kmeans: KMeans
    scaler: StandardScaler
    pca: PCA
    names: dict


def fit(data_dir: str, k: int = K) -> SegmentationResult:
    df = clean(load_raw(data_dir))
    feats = build_features(df)
    scaler = StandardScaler().fit(feats)
    X = scaler.transform(feats)
    km = KMeans(n_clusters=k, n_init=20, random_state=RANDOM_STATE).fit(X)
    names = name_segments(df, km.labels_)
    # Renumber segments 1..k in persona order, so ids are stable and meaningful
    order = {seg: PERSONAS[name]["order"] for seg, name in names.items()}
    df["segment_id"] = [order[s] for s in km.labels_]
    df["segment_name"] = [names[s] for s in km.labels_]
    df["distance_to_centre"] = np.linalg.norm(X - km.cluster_centers_[km.labels_], axis=1)
    pca = PCA(n_components=2, random_state=RANDOM_STATE).fit(X)
    df[["pca_1", "pca_2"]] = pca.transform(X)
    return SegmentationResult(data=df, X=X, kmeans=km, scaler=scaler, pca=pca, names=names)


def k_selection(X: np.ndarray, ks=range(2, 11)) -> pd.DataFrame:
    rows = []
    for k in ks:
        km = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_STATE).fit(X)
        rows.append({"k": k, "inertia": km.inertia_, "silhouette": silhouette_score(X, km.labels_)})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# 4. Power BI export
# --------------------------------------------------------------------------
def powerbi_tables(res: SegmentationResult, k_table: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    d = res.data
    customers = pd.DataFrame({
        "customer_id": d["CUST_ID"], "segment_id": d["segment_id"],
        "balance": d["BALANCE"].round(2), "purchases": d["PURCHASES"].round(2),
        "oneoff_purchases": d["ONEOFF_PURCHASES"].round(2), "installment_purchases": d["INSTALLMENTS_PURCHASES"].round(2),
        "cash_advance": d["CASH_ADVANCE"].round(2), "credit_limit": d["CREDIT_LIMIT"].round(2),
        "payments": d["PAYMENTS"].round(2), "minimum_payments": d["MINIMUM_PAYMENTS"].round(2),
        "utilization": d["utilization"].round(4), "purchases_frequency": d["PURCHASES_FREQUENCY"].round(4),
        "cash_advance_frequency": d["CASH_ADVANCE_FREQUENCY"].round(4),
        "full_payment_rate": d["PRC_FULL_PAYMENT"].round(4), "purchase_transactions": d["PURCHASES_TRX"],
        "cash_advance_transactions": d["CASH_ADVANCE_TRX"], "tenure_months": d["TENURE"],
        "uses_cash_advance": (d["CASH_ADVANCE"] > 0).astype(int),
        "usually_pays_in_full": (d["PRC_FULL_PAYMENT"] >= 0.75).astype(int),
        "pca_1": d["pca_1"].round(4), "pca_2": d["pca_2"].round(4),
        "distance_to_centre": d["distance_to_centre"].round(4),
    })

    segments = pd.DataFrame([{"segment_id": p["order"], "segment_name": name, "description": p["description"],
                              "recommended_action": p["action"], "risk_view": p["risk"], "color_hex": p["color"]}
                             for name, p in PERSONAS.items()]).sort_values("segment_id")
    segments["customers"] = segments["segment_id"].map(d["segment_id"].value_counts()).astype(int)

    metrics = pd.DataFrame([{"metric_id": m[4], "metric": m[1], "description": m[2], "unit": m[3]} for m in METRICS])

    rows = []
    for col, label, _, _, mid in METRICS:
        overall_mean, overall_sd = d[col].mean(), d[col].std()
        for sid, g in d.groupby("segment_id"):
            rows.append({"segment_id": sid, "metric_id": mid, "segment_mean": g[col].mean(),
                         "segment_median": g[col].median(), "overall_mean": overall_mean,
                         "z_score": (g[col].mean() - overall_mean) / overall_sd})
    profile = pd.DataFrame(rows).round(4)

    tables = {"customers": customers, "segments": segments, "metrics": metrics, "segment_profile": profile}
    if k_table is not None:
        tables["k_selection"] = k_table.round(4)
    return tables


def export_powerbi(out_dir: str, tables: dict[str, pd.DataFrame]) -> None:
    os.makedirs(out_dir, exist_ok=True)
    for name, t in tables.items():
        t.to_csv(os.path.join(out_dir, f"{name}.csv"), index=False)


if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = fit(os.path.join(root, "data"))
    export_powerbi(os.path.join(root, "powerbi", "data"), powerbi_tables(result, k_selection(result.X)))
    print(result.data["segment_name"].value_counts())
