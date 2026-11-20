"""Baixa o histórico de funding (últimos ~500 registros) de todos os perpétuos em data/cache/funding/."""
import csv, pathlib, sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import alphax

OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "cache" / "funding"


def fetch(s):
    for attempt in range(3):
        try:
            rows = alphax.funding(s)
            break
        except Exception:
            rows = []
    with (OUT / f"{s}.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["t", "rate"])
        w.writeheader()
        w.writerows({"t": r["t"], "rate": r["rate"]} for r in rows)
    return len(rows)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    syms = sorted({r["s"] for r in alphax.tickers() if r["s"].endswith("-SWAP-USDT")})
    with ThreadPoolExecutor(8) as ex:
        n = list(ex.map(fetch, syms))
    print("ok", len(syms), "símbolos; vazios:", sum(1 for x in n if x == 0))
