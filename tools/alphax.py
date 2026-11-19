"""Cliente mínimo da API pública da AlphaX (sem dependências externas)."""
import json, time, urllib.request, urllib.parse

BASE = "https://mapi.alphax.com"
UA = {"User-Agent": "Mozilla/5.0"}


def _get(path, **params):
    url = f"{BASE}{path}?{urllib.parse.urlencode(params)}"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
                return json.load(r)["data"]
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def sym(s):
    s = s.upper()
    return s if s.endswith("-SWAP-USDT") else f"{s}-SWAP-USDT"


def klines(symbol, interval, limit=1000, to_ms=None):
    """Candles [{t,o,h,l,c,v}] em ordem crescente, terminando em to_ms (se dado)."""
    params = {"symbol": sym(symbol), "interval": interval, "limit": limit}
    if to_ms:
        params["to"] = int(to_ms)
    rows = _get("/api/quote/v1/klines", **params)
    out = [{"t": int(r["t"]), **{k: float(r[k]) for k in "ohlcv"}} for r in rows]
    return sorted(out, key=lambda r: r["t"])


def tickers():
    return _get("/api/quote/v1/broker/tickers")


def worst_24h(n=20):
    """Ranking atual dos piores retornos de 24h: [(symbol, retorno, quote_volume)]."""
    rows = [(r["s"], float(r["m24h"]), float(r.get("qv24h") or 0)) for r in tickers()
            if r["s"].endswith("-SWAP-USDT")]
    return sorted(rows, key=lambda x: x[1])[:n]
