"""Filtro de volatilidade do índice cripto, ao vivo (usado pelo scanner).

Índice: pesos iguais entre as 30 criptos com maior volume spot na Binance nas 8 semanas anteriores
(rebalanceado toda segunda 00:00 UTC; BTC e ETH sempre incluídos; sem stablecoins/ouro/wrapped/alavancados),
mesma definição do backtest (tools/opt.py: crypto_index).
Filtro: volatilidade de 7 dias (desvio-padrão dos retornos de 15m) <= mediana dos últimos 90 dias -> LIBERADO.

Dados: arquivos públicos da Binance (atualizados aqui de forma incremental até ontem)
       + candles da AlphaX para as últimas horas (os preços coincidem com a Binance).
"""
import io, pathlib, sys, time, zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import alphax
from download_binance import get, DATA

ROOT = pathlib.Path(__file__).resolve().parent.parent
B = ROOT / "data/cache/binance"
BAR = 15 * 60 * 1000
EXCLUIR = {"USDC", "FDUSD", "TUSD", "BUSD", "DAI", "USDP", "PAX", "USDS", "USDSB", "UST", "USTC", "EUR", "GBP",
           "AUD", "TRY", "BRL", "AEUR", "EURI", "USDE", "USD1", "RLUSD", "PYUSD", "XUSD", "BFUSD", "U", "SUSD",
           "PAXG", "XAUT", "WBTC", "WBETH", "BETH", "BKRW", "BIDR", "IDRT", "BVND", "NGN", "RUB", "UAH", "ZAR"}
N, WEEKS, VOL_W, MED_L = 30, 8, 672, 90 * 96


def _zip_csv(raw, cols, idx):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        df = pd.read_csv(io.BytesIO(z.read(z.namelist()[0])), header=None)
    if not str(df.iat[0, 0]).isdigit():
        df = df.iloc[1:]
    df = df.iloc[:, idx].apply(pd.to_numeric)
    df.columns = cols
    df["t"] = df["t"].where(df["t"] < 1e14, df["t"] // 1000)
    return df


def _days(after_ms):
    d0 = datetime.fromtimestamp(after_ms / 1000, timezone.utc).date() + timedelta(days=1)
    y = date.today() - timedelta(days=1)
    return [(d0 + timedelta(k)).isoformat() for k in range((y - d0).days + 1)]


def update_spot(top=120):
    """Completa o volume spot diário (até ontem) dos `top` ativos de maior volume recente."""
    f = B / "spot_1d.csv.gz"
    sp = pd.read_csv(f)
    last = sp["t"].max()
    days = _days(last)
    if not days:
        return sp
    recent = sp[sp["t"] > last - 60 * 86_400_000].groupby("sym")["qv"].sum().nlargest(top).index

    def one(sym):
        parts = []
        for d in days:
            raw = get(f"{DATA}data/spot/daily/klines/{sym}USDT/1d/{sym}USDT-1d-{d}.zip")
            if raw:
                parts.append(_zip_csv(raw, ["t", "qv"], [0, 7]).assign(sym=sym))
        return pd.concat(parts) if parts else None

    with ThreadPoolExecutor(16) as ex:
        new = [x for x in ex.map(one, recent) if x is not None]
    if new:
        sp = pd.concat([sp] + new).drop_duplicates(["sym", "t"])
        sp.to_csv(f, index=False, compression="gzip")
    return sp


def fut_map():
    m = {}
    for p in (B / "15m").glob("*.csv.gz"):
        name = p.name.split(".")[0]
        base = name[:-4]
        for pre in ("1000000", "1000"):
            if base.startswith(pre):
                base = base[len(pre):]
        m.setdefault(base, name)
    return m


def update_15m(name):
    """Completa os candles de 15m da Binance de um perpétuo até ontem."""
    f = B / "15m" / f"{name}.csv.gz"
    df = pd.read_csv(f)
    parts = []
    for d in _days(df["t"].max()):
        raw = get(f"{DATA}data/futures/um/daily/klines/{name}/15m/{name}-15m-{d}.zip")
        if raw:
            parts.append(_zip_csv(raw, ["t", "o", "h", "l", "c", "v"], [0, 1, 2, 3, 4, 7]))
    if parts:
        df = pd.concat([df] + parts).drop_duplicates("t").sort_values("t")
        df.to_csv(f, index=False, compression="gzip")
    return df


def membership(sp, fmap, since):
    sp = sp[~sp["sym"].isin(EXCLUIR) & ~sp["sym"].astype(str).str.contains(r"(?:UP|DOWN|BULL|BEAR)$")]
    vol = sp.pivot_table(index="t", columns="sym", values="qv", aggfunc="sum").sort_index()
    vol.index = pd.to_datetime(vol.index, unit="ms")
    vol = vol.asfreq("D").fillna(0)
    roll = vol.rolling(7 * WEEKS, min_periods=7 * WEEKS).sum().shift(1)
    out = []
    since = since.normalize()
    for d in pd.date_range(since - pd.Timedelta(days=since.weekday()), pd.Timestamp.now("UTC").tz_localize(None), freq="W-MON"):
        dv = d if d in roll.index else roll.index[roll.index <= d][-1]  # se faltar o dia, usa o último disponível
        rank = roll.loc[dv].dropna().sort_values(ascending=False)
        top = [s for s in rank.index if s in fmap][:N]
        for must in ("BTC", "ETH"):
            if must not in top and must in fmap:
                top = top[:-1] + [must]
        out.append((d, top))
    return out


def state(verbose=False):
    """Retorna dict com vol7d, mediana90d, liberado (bool) e membros atuais."""
    sp = update_spot()
    fmap = fut_map()
    now = pd.Timestamp.now("UTC").tz_localize(None)
    start = now - pd.Timedelta(days=100)
    mem = membership(sp, fmap, start)
    syms = sorted({s for _, top in mem for s in top})
    t0 = int(start.value // 10**6) // BAR * BAR
    grid = np.arange(t0, int(now.value // 10**6) // BAR * BAR, BAR)

    def rets(sym):
        name = fmap[sym]
        df = update_15m(name)
        r = df.set_index("t")["c"].reindex(grid).pct_change(fill_method=None)
        try:  # últimas horas pela AlphaX (preços equivalentes; usa só retornos)
            ax = pd.DataFrame(alphax.klines(sym, "15m", 300)).set_index("t")["c"]
            rax = ax.reindex(grid).pct_change(fill_method=None)
            r = r.fillna(rax)
        except Exception:
            pass
        return sym, r.to_numpy()

    with ThreadPoolExecutor(8) as ex:
        R = dict(ex.map(rets, syms))
    idx_r = np.full(len(grid), np.nan)
    ts = pd.to_datetime(grid, unit="ms")
    for k, (d, top) in enumerate(mem):
        end = mem[k + 1][0] if k + 1 < len(mem) else ts[-1] + pd.Timedelta("1D")
        sel = (ts >= d) & (ts < end)
        M = np.column_stack([R[s][sel] for s in top])
        with np.errstate(all="ignore"):
            idx_r[sel] = np.nanmean(M, axis=1)
    r = pd.Series(idx_r)
    vol = r.rolling(VOL_W, min_periods=VOL_W // 2).std()
    med = vol.rolling(MED_L, min_periods=MED_L // 2).median()
    v, m = float(vol.iloc[-1]), float(med.iloc[-1])
    return {"vol7d": v, "mediana90d": m, "liberado": bool(v <= m), "membros": mem[-1][1],
            "atualizado": str(ts[-1])}


if __name__ == "__main__":
    s = state()
    print(f"vol 7d = {s['vol7d']*100:.3f}%  mediana 90d = {s['mediana90d']*100:.3f}%  ->",
          "LIBERADO" if s["liberado"] else "BLOQUEADO", "| até", s["atualizado"], "UTC")
    print("membros:", ", ".join(s["membros"]))
