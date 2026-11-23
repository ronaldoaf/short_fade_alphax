"""Baixa candles DIÁRIOS do spot da Binance (pares USDT) para obter o volume em USDT.

Saída: data/cache/binance/spot_1d.csv.gz com colunas sym, t (ms), qv (volume em USDT)
Uso: python tools/download_spot_volume.py --start 2022-11 --end 2026-11-22
"""
import argparse, io, pathlib, re, sys, zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from download_binance import get, months, S3, DATA

OUT = pathlib.Path(__file__).resolve().parent.parent / "data/cache/binance"


def list_spot():
    syms, marker = [], ""
    while True:
        xml = get(f"{S3}?delimiter=/&prefix=data/spot/monthly/klines/&marker={marker}").decode()
        syms += re.findall(r"spot/monthly/klines/([^/<]+)/</Prefix>", xml)
        m = re.search(r"<NextMarker>([^<]+)</NextMarker>", xml)
        if not m:
            break
        marker = m.group(1)
    return sorted(s for s in syms if s.endswith("USDT"))


def read(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        df = pd.read_csv(io.BytesIO(z.read(z.namelist()[0])), header=None)
    if not str(df.iat[0, 0]).isdigit():
        df = df.iloc[1:]
    df = df.iloc[:, [0, 7]].apply(pd.to_numeric)
    df.columns = ["t", "qv"]
    df["t"] = df["t"].where(df["t"] < 1e14, df["t"] // 1000)  # alguns arquivos recentes vêm em microssegundos
    return df


def fetch(sym, mons, days):
    parts = []
    for mo in mons:
        raw = get(f"{DATA}data/spot/monthly/klines/{sym}/1d/{sym}-1d-{mo}.zip")
        if raw:
            parts.append(read(raw))
    for d in days:
        raw = get(f"{DATA}data/spot/daily/klines/{sym}/1d/{sym}-1d-{d}.zip")
        if raw:
            parts.append(read(raw))
    return pd.concat(parts).assign(sym=sym[:-4]) if parts else None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="2022-11")
    p.add_argument("--end", default="2026-11-22")
    a = p.parse_args()
    end = date.fromisoformat(a.end)
    lm = (end.year, end.month - 1) if end.month > 1 else (end.year - 1, 12)
    mons = months(a.start, lm)
    first = date(end.year, end.month, 1)
    days = [(first + timedelta(d)).isoformat() for d in range((end - first).days + 1)]
    syms = list_spot()
    print(len(syms), "pares spot USDT", flush=True)
    with ThreadPoolExecutor(24) as ex:
        res = [r for r in ex.map(lambda s: fetch(s, mons, days), syms) if r is not None]
    df = pd.concat(res).drop_duplicates(["sym", "t"])
    df.to_csv(OUT / "spot_1d.csv.gz", index=False, compression="gzip")
    print("ok", df.sym.nunique(), "ativos,", len(df), "linhas")


if __name__ == "__main__":
    main()
