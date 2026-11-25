"""Separa cripto de não cripto (ações, ETFs, índices, forex, commodities) nos perpétuos da AlphaX e da Binance.

A API da AlphaX não tem campo de categoria (todos os ativos, exceto BTC, vêm como 'STOCK_INDEX').
Regra, na ordem:
  1. Lista manual de ativos tradicionais (ouro, forex, índices, ações com nome sem termo de empresa) -> não cripto
  2. Listado no spot da Binance (que só lista cripto) -> cripto
  3. Nome completo com termo de empresa/fundo (Inc, Corp, ETF, Ltd, 2X, Pre-IPO...) -> não cripto
  4. Preço quase parado no fim de semana: movimento médio sáb/dom < 65% do de seg-sex -> não cripto
     (ações e índices seguem o mercado tradicional; cripto se move igual nos 7 dias)
  5. Caso contrário -> cripto
"""
import json, pathlib, re, time, urllib.request

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
NOMES = ROOT / "data/cache/alphax_symbols.json"
CLASSE = ROOT / "data/cache/alphax_classe.json"
URL = "https://mapi.alphax.com/api/v1/basic/config_v2?type=futures"
LIMIAR_FDS = 0.65

TERMOS = re.compile(
    r"\b(Inc|Incorporated|Corp|Corporation|ETF|ETN|Ltd|Limited|Holdings?|Trust|plc|Group|Company|Co\.|N\.V\.|"
    r"S\.A\.|S\.P\.A\.|SA/NV|PBC|Technologies|Shares|ProShares|Direxion|GraniteShares|iShares|SPDR|VanEck|Tradr|"
    r"Daily|[23]X|Preferred Stock|Index Fund|Pre-IPO|US Dollar|Stock Average|Industrial Average|Index|Crude Oil|"
    r"Natural Gas|Gold|Silver|Copper|Palladium|Platinum|Aluminum|Nickel)\b", re.I)
TRADICIONAIS = {
    "PAXG", "XAUT", "XAU", "XAG", "XPD", "XPT", "XAL", "XCU", "XNI", "XPB", "COPPER", "NATGAS", "NG", "CL", "BZ",
    "WTI", "BRENT", "USO", "AUS200", "US30", "US500", "US2000", "NAS100", "SPX500", "UK100", "GER40", "JPN225",
    "NIKKEI225", "KR200", "KR200INDEX", "NIFTY50", "NIFTYBANK", "VOLX", "GVZ",
    "AAPL", "AMZN", "ABBV", "ADBE", "AMAT", "ASML", "ASTS", "AXTI", "AAOI", "BABA", "BAC", "BBX", "BRKB", "BX",
    "CAT", "COST", "CRDO", "CRM", "CRWD", "CVNA", "DDOG", "DELL", "DKNG", "EBAY", "FWDI", "GLW", "GME", "GS", "HD",
    "HIMS", "HPE", "HYUNDAI", "IBM", "JPM", "KO", "MELI", "META", "MU", "NFLX", "NKE", "NOK", "NOW", "NVDA",
    "NVO", "ONDS", "PAYP", "PFE", "RIVN", "RKLB", "SAMSUNG", "SHOP", "SKHYNIX", "SNOW", "STXX", "TXN", "UBER", "V",
    "WEN", "WMT", "ZM", "AEHR", "ANTHROPIC", "ANTHROPICSTOCK", "APH", "BA", "BUD", "COP", "CRCLUSD", "CVNASTOCK",
    "FCX", "FN", "GE", "HON", "INFQ", "JNJ", "JUSUNG", "KIOXIA", "LMT", "MAR", "MCHP", "NEE", "PEP", "PG", "PL",
    "ROKU", "SPOT", "TMUS", "VRTX", "WFC", "MEITUAN", "BYD", "KUAISHOU", "OURA",
}
FOREX = re.compile(r"^(USD[A-Z]{3}|[A-Z]{3}USD)$")
MOEDAS = {"EUR", "GBP", "AUD", "NZD", "JPY", "CHF", "CAD", "BRL", "MXN", "CNH", "HKD", "SGD", "KRW", "INR", "TRY"}


def base_de(sym):
    b = sym.upper().replace("-SWAP-USDT", "")
    if b.endswith("USDT") and len(b) > 4:
        b = b[:-4]
    for pre in ("1000000", "1000"):
        if b.startswith(pre) and len(b) > len(pre):
            b = b[len(pre):]
    return b


def _spot_binance():
    f = ROOT / "data/cache/binance/spot_1d.csv.gz"
    return frozenset(pd.read_csv(f, usecols=["sym"])["sym"].unique()) if f.exists() else frozenset()


def nomes(max_age_h=24):
    """{base: nome completo} dos perpétuos USDT da AlphaX (cache de 24h)."""
    if NOMES.exists() and time.time() - NOMES.stat().st_mtime < max_age_h * 3600:
        return json.loads(NOMES.read_text())
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            fs = json.load(r)["futuresSymbol"]
    except Exception:
        return json.loads(NOMES.read_text()) if NOMES.exists() else {}
    out = {s["symbolId"].replace("-SWAP-USDT", ""): s.get("underlyingTokenFullName") or ""
           for s in fs if s["symbolId"].endswith("-SWAP-USDT") and not s["symbolId"].startswith("TEST")}
    NOMES.parent.mkdir(parents=True, exist_ok=True)
    NOMES.write_text(json.dumps(out, ensure_ascii=False))
    return out


def razao_fds(t_ms, c):
    """Movimento médio (|retorno|) no sábado/domingo dividido pelo de segunda a sexta. NaN se faltar dado."""
    c = np.asarray(c, dtype=float)
    r = np.abs(np.diff(np.log(c)))
    wd = pd.to_datetime(np.asarray(t_ms)[1:], unit="ms").weekday
    we = np.asarray(wd >= 5)
    if we.sum() < 24 or (~we).sum() < 24:
        return np.nan
    a, b = np.nanmean(r[we]), np.nanmean(r[~we])
    return a / b if b > 0 else np.nan


def eh_cripto(sym, nome="", spot=frozenset(), fds=np.nan):
    """True se cripto. `fds` = razao_fds do ativo (opcional)."""
    b = base_de(sym)
    if re.match(r"^1000", sym.upper()):  # prefixo 1000/1000000 só existe em memecoins (ex.: 1000CAT != Caterpillar)
        return True
    if b in TRADICIONAIS:
        return False
    if b in spot:
        return True
    if FOREX.match(b) and (b[:3] in MOEDAS or b[3:] in MOEDAS):
        return False
    if TERMOS.search(nome or ""):
        return False
    if np.isfinite(fds) and fds < LIMIAR_FDS:
        return False
    return True


def classe_alphax(symbols, klines=None, max_age_d=7):
    """{symbol: True se cripto} para símbolos da AlphaX. Usa candles de 1h (500) para o teste do fim de semana,
    com cache de 7 dias em data/cache/alphax_classe.json."""
    from concurrent.futures import ThreadPoolExecutor
    spot, nm = _spot_binance(), nomes()
    cache = json.loads(CLASSE.read_text()) if CLASSE.exists() else {}
    now = time.time()
    out, falta = {}, []
    for s in symbols:
        b = s.replace("-SWAP-USDT", "")
        if not eh_cripto(b, nm.get(b, ""), spot):
            out[s] = False
        elif base_de(b) in spot or b.startswith("1000"):
            out[s] = True
        elif b not in cache or now - cache[b]["ts"] > max_age_d * 86400:
            falta.append(s)

    def fds_de(s):
        try:
            k = klines(s, "1h", 500)
            return razao_fds([x["t"] for x in k], [x["c"] for x in k])
        except Exception:
            return np.nan

    mudou = bool(falta) and klines is not None
    if mudou:
        with ThreadPoolExecutor(8) as ex:
            for s, f in zip(falta, ex.map(fds_de, falta)):
                cache[s.replace("-SWAP-USDT", "")] = {"fds": None if not np.isfinite(f) else round(float(f), 3), "ts": now}
    for s in symbols:
        if s not in out:
            b = s.replace("-SWAP-USDT", "")
            f = cache.get(b, {}).get("fds")
            out[s] = eh_cripto(b, nm.get(b, ""), spot, np.nan if f is None else f)
    if mudou:
        CLASSE.parent.mkdir(parents=True, exist_ok=True)
        CLASSE.write_text(json.dumps(cache, indent=0))
    return out


def mascara_binance(P):
    """Array bool (um por coluna de P['names']): True se o perpétuo da Binance é cripto."""
    import opt
    spot, nm = _spot_binance(), nomes()
    out = []
    for j, s in enumerate(P["names"]):
        a = P["arrs"][s]["c"]
        t = P["tmin"] + (P["offs"][j] + np.arange(len(a), dtype=np.int64)) * opt.BAR
        out.append(eh_cripto(s, nm.get(base_de(s), ""), spot, razao_fds(t, a)))
    return np.array(out)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    import alphax
    syms = [r[0] for r in alphax.worst_24h(60)]
    c = classe_alphax(syms, alphax.klines)
    print("60 piores de 24h na AlphaX agora:")
    print("  cripto    :", ", ".join(s.replace("-SWAP-USDT", "") for s in syms if c[s]))
    print("  não cripto:", ", ".join(s.replace("-SWAP-USDT", "") for s in syms if not c[s]))
