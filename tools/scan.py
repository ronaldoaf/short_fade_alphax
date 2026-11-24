"""Scanner ao vivo da regra C6 na AlphaX.

Regra C6 (otimizada com treino/validação/teste em dados da Binance, ver REGRAS.md):
  Universo : 5 piores retornos de 24h com volume 24h >= 50.000 USDT
  4h       : preço < MA30, MA5 < MA10 < MA30, MA30 caindo (vs 10 velas atrás)
  15m      : preço < MA30, MA30 caindo (vs 10 velas atrás), MA5 < MA10, preço no máx. 20% abaixo da MA30
  Mercado  : só opera se a volatilidade de 7d do índice cripto (30 maiores, pesos iguais) estiver
             abaixo da mediana dos últimos 90 dias (tools/market_vol.py)
  Saída    : short 10x isolado; alvo -15% no preço; stop = entrada + 1 ATR(14) do 4h; tempo máximo 48h

Uso: python tools/scan.py [--top 5] [--show 10] [--vol 50000]
  --show mostra mais posições do ranking para contexto (só as --top primeiras podem dar sinal).
"""
import argparse, pathlib, sys, time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import alphax
import market_vol
from opt import prep_symbol

BAR = 15 * 60 * 1000
TP, LIQ, MAXDIST = 0.15, 0.095, 0.20


def check(row):
    """True/False de cada condição na última linha de indicadores."""
    return dict(c4=bool(row.s4), c15=bool(row.s15), ord15=bool(row.ord15), dist=bool(row.dist15 <= MAXDIST))


def evaluate(sym):
    df = pd.DataFrame(alphax.klines(sym, "15m", 1000))
    df["v"] = df["v"] * df["c"]  # prep_symbol espera volume em USDT
    now = time.time() * 1000
    _, live = prep_symbol(df.copy(), None)
    closed = df[df["t"] + BAR <= now].reset_index(drop=True)
    _, f = prep_symbol(closed, None)
    return check(f.iloc[-1]), check(live.iloc[-1]), float(live["c"].iloc[-1]), float(live["atr4"].iloc[-1]), float(live["dist15"].iloc[-1])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--show", type=int, default=10)
    p.add_argument("--vol", type=float, default=50_000)
    p.add_argument("--sem-filtro", action="store_true", help="ignora o filtro de volatilidade do índice")
    a = p.parse_args()

    try:
        mv = market_vol.state()
        liberado = mv["liberado"] or a.sem_filtro
        print(f"Filtro de volatilidade do índice: vol 7d {mv['vol7d']*100:.3f}% vs mediana 90d {mv['mediana90d']*100:.3f}%"
              f" -> {'LIBERADO' if mv['liberado'] else 'BLOQUEADO (mercado agitado)'}"
              f"{' [ignorado por --sem-filtro]' if a.sem_filtro and not mv['liberado'] else ''}\n")
    except Exception as e:
        liberado = a.sem_filtro
        print(f"Filtro de volatilidade: não foi possível calcular ({e}); tratado como BLOQUEADO\n")

    rows = [r for r in alphax.worst_24h(200) if r[2] >= a.vol][:max(a.show, a.top)]
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda r: evaluate(r[0]), rows))

    print(f"Regra C6 | sinal só nos {a.top} piores de 24h com volume >= {a.vol:,.0f} USDT")
    print(f"{'#':>2} {'ativo':14} {'24h':>7} {'vol24h':>12}  4h  15m  ma5<10 dist<=20%  agora  sinal")
    sinais = []
    for i, ((s, m, qv), (cl, lv, px, atr, dist)) in enumerate(zip(rows, res), 1):
        ok = all(cl.values())
        agora = all(lv.values())
        sig = (("SHORT" if liberado else "(bloqueado: vol alta)") if ok else "") if i <= a.top else ("(fora do top)" if ok else "")
        nm = s.replace("-SWAP-USDT", "")
        print(f"{i:2d} {nm:14} {m*100:6.2f}% {qv:12,.0f}  {'ok' if cl['c4'] else '--':3} {'ok' if cl['c15'] else '--':4}"
              f" {'ok' if cl['ord15'] else '--':6} {'ok' if cl['dist'] else '--':9}  {'ok' if agora else '--':5}  {sig}")
        if ok and i <= a.top and liberado:
            sinais.append((nm, px, atr, agora))

    for nm, px, atr, agora in sinais:
        stop = px * (1 + atr) if np.isfinite(atr) else np.nan
        liq = px * (1 + LIQ)
        aviso = "  ATENÇÃO: stop acima da liquidação (ATR alto) -> perda máxima = margem" if stop >= liq else ""
        print(f"\n{nm}: preço {px:.6g} | alvo {px*(1-TP):.6g} (-15%) | stop {stop:.6g} (+{atr*100:.1f}%, 1 ATR 4h)"
              f" | liquidação ~{liq:.6g} | saída por tempo em 48h{'' if agora else ' | candle atual já não confirma'}{aviso}")
    if not sinais:
        print("\nNenhum sinal agora." if liberado else "\nFiltro de volatilidade bloqueando: não operar agora.")


if __name__ == "__main__":
    main()
