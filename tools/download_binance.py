"""Baixa do arquivo público da Binance (data.binance.vision) candles de 15m e funding dos perpétuos USDT-M.

Inclui ativos já deslistados (evita viés de sobrevivência).
Saída: data/cache/binance/15m/<SYM>.csv.gz (t,o,h,l,c,v em USDT) e data/cache/binance/funding/<SYM>.csv
Uso: python tools/download_binance.py --start 2025-11 --end 2026-11-22
"""
import argparse, io, pathlib, re, urllib.request, zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data/cache/binance"
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
DATA = "https://data.binance.vision/"
COLS = ["t", "o", "h", "l", "c", "vb", "ct", "v", "n", "tb", "tq", "x"]


def get(url):
    for _ in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
        except Exception:
            pass
    return None


def list_symbols():
    syms, marker = [], ""
    while True:
        xml = get(f"{S3}?delimiter=/&prefix=data/futures/um/monthly/klines/&marker={marker}").decode()
        syms += re.findall(r"klines/([^/<]+)/</Prefix>", xml)
        m = re.search(r"<NextMarker>([^<]+)</NextMarker>", xml)
        if not m:
            break
        marker = m.group(1)
    return sorted(s for s in syms if s.endswith("USDT"))


def read_zip(raw, cols):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        txt = z.read(z.namelist()[0]).decode()
    df = pd.read_csv(io.StringIO(txt), header=None)
    if not str(df.iat[0, 0]).lstrip("-").isdigit():  # cabeçalho
        df = df.iloc[1:]
    df = df.iloc[:, :len(cols)]
    df.columns = cols
    return df.apply(pd.to_numeric)


def months(a, b):
    y, m = map(int, a.split("-"))
    out = []
    while (y, m) <= b:
        out.append(f"{y}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def fetch(sym, mons, days):
    p = OUT / "15m" / f"{sym}.csv.gz"
    if p.exists():
        return sym, -1
    parts = []
    for mo in mons:
        raw = get(f"{DATA}data/futures/um/monthly/klines/{sym}/15m/{sym}-15m-{mo}.zip")
        if raw:
            parts.append(read_zip(raw, COLS))
    for d in days:
        raw = get(f"{DATA}data/futures/um/daily/klines/{sym}/15m/{sym}-15m-{d}.zip")
        if raw:
            parts.append(read_zip(raw, COLS))
    if parts:
        df = pd.concat(parts).drop_duplicates("t").sort_values("t")
        df[["t", "o", "h", "l", "c", "v"]].to_csv(p, index=False, compression="gzip")
    fr = []
    for mo in mons:
        raw = get(f"{DATA}data/futures/um/monthly/fundingRate/{sym}/{sym}-fundingRate-{mo}.zip")
        if raw:
            fr.append(read_zip(raw, ["t", "interval", "rate"]))
    if fr:
        f = pd.concat(fr).drop_duplicates("t").sort_values("t")
        f[["t", "rate"]].to_csv(OUT / "funding" / f"{sym}.csv", index=False)
    return sym, sum(len(x) for x in parts)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="2025-11")
    p.add_argument("--end", default="2026-11-22")
    p.add_argument("--workers", type=int, default=16)
    a = p.parse_args()
    end = date.fromisoformat(a.end)
    last_month = (end.year, end.month - 1) if end.month > 1 else (end.year - 1, 12)
    mons = months(a.start, last_month)
    first = date(end.year, end.month, 1)
    days = [(first + timedelta(d)).isoformat() for d in range((end - first).days + 1)]
    (OUT / "15m").mkdir(parents=True, exist_ok=True)
    (OUT / "funding").mkdir(parents=True, exist_ok=True)
    syms = list_symbols()
    print(len(syms), "símbolos;", mons[0], "a", a.end, flush=True)
    with ThreadPoolExecutor(a.workers) as ex:
        for k, (s, n) in enumerate(ex.map(lambda s: fetch(s, mons, days), syms), 1):
            if k % 50 == 0:
                print(k, "/", len(syms), flush=True)
    print("ok")


if __name__ == "__main__":
    main()
