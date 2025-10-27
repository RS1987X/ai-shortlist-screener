
import csv
from urllib.parse import urlparse
import statistics as stats

def _root(url: str) -> str:
    return urlparse(url).netloc

def compute_lar(asr_report_csv: str, soa_csv: str, dist_csv: str, service_csv: str, out_csv: str) -> None:
    # E/X from audit
    E, X = {}, {}
    per = {}
    with open(asr_report_csv, encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            k = _root(row["url"])
            e = float(row["product_score"]) * 0.8 + float(row["family_score"]) * 0.2
            x = (int(row.get("policies",0)) + int(row.get("specs_units",0))) * 50
            per.setdefault(k, {"E": [], "X": []})
            per[k]["E"].append(e)
            per[k]["X"].append(x)
    for k,v in per.items():
        E[k] = stats.mean(v["E"]) if v["E"] else 0.0
        X[k] = stats.mean(v["X"]) if v["X"] else 0.0

    def _load_simple(path):
        d = {}
        with open(path, encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                key = row.get("key") or row.get("domain") or row.get("brand")
                d[key] = float(row.get("value") or row.get("score") or row.get("soa") or 0)
        return d

    A = _load_simple(soa_csv)
    D = _load_simple(dist_csv)
    S = _load_simple(service_csv)

    out_rows = []
    keys = set(E) | set(A) | set(D) | set(S)
    for k in sorted(keys):
        e = E.get(k, 0.0)
        x = X.get(k, 0.0)
        a = A.get(k, 0.0)
        d = D.get(k, 0.0)
        s = S.get(k, 0.0)

        lar = 0.30*e + 0.20*x + 0.25*a + 0.15*d + 0.10*s
        if e < 60:
            lar = min(lar, 40.0)
        out_rows.append({"key": k, "E": round(e,2), "X": round(x,2), "A": a, "D": d, "S": s, "LAR": round(lar,2)})

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["key","E","X","A","D","S","LAR"])
        w.writeheader()
        for r in out_rows:
            w.writerow(r)
