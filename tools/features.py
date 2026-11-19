"""Calcula as features candidatas para todos os exemplos e imprime uma tabela."""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def sma(c, n, end=None):
    c = c[:end] if end else c
    return sum(c[-n:]) / n


def feats(rows):
    c = [r["c"] for r in rows]
    rng = [(r["h"] - r["l"]) / r["o"] for r in rows]
    base = sum(rng[-40:-10]) / 30
    big_up = max(((r["c"] - r["o"]) / r["o"], (r["h"] - r["l"]) / r["o"] / base)
                 for r in rows[-10:] if r["c"] > r["o"]) if any(r["c"] > r["o"] for r in rows[-10:]) else (0, 0)
    return {
        "px<ma30": c[-1] < sma(c, 30),
        "ma5<ma10<ma30": sma(c, 5) < sma(c, 10) < sma(c, 30),
        "ma30_slope10%": (sma(c, 30) / sma(c, 30, -10) - 1) * 100,
        "dist_ma30%": (c[-1] / sma(c, 30) - 1) * 100,
        "maior_alta_10v_xmedia": big_up[1],
    }


def main():
    for line in (ROOT / "examples" / "examples.jsonl").read_text().splitlines():
        e = json.loads(line)
        d = ROOT / "data" / e["id"]
        out = [f"{e['symbol'].split('-')[0]:8s} {e['label']:3s}"]
        for iv in ("4h", "15m"):
            f = feats(json.loads((d / f"{iv}.json").read_text()))
            out.append(f"{iv}: px<ma30={f['px<ma30']!s:5} ordem={f['ma5<ma10<ma30']!s:5} "
                       f"incl30={f['ma30_slope10%']:+6.1f}% dist={f['dist_ma30%']:+6.1f}% "
                       f"maxAltaRng={f['maior_alta_10v_xmedia']:.1f}x")
        print(" | ".join(out))


if __name__ == "__main__":
    main()
