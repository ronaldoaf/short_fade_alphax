"""Registra um exemplo e baixa os candles de 4h e 15m até o momento dele.

Uso:
  python tools/snapshot.py XYZ yes "2026-11-19 16:30" "topos descendentes" [--rank 3] [--ret -12.5] [--img arquivo.png]
  python tools/snapshot.py --ranking          # mostra os piores de 24h agora
Hora sem fuso é tratada como America/Sao_Paulo.
"""
import argparse, json, pathlib, sys
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import alphax

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG = ROOT / "examples" / "examples.jsonl"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("symbol", nargs="?")
    p.add_argument("label", nargs="?", choices=["yes", "no"])
    p.add_argument("when", nargs="?")
    p.add_argument("reason", nargs="?", default="")
    p.add_argument("--rank", type=int)
    p.add_argument("--ret", type=float, help="retorno 24h em %% mostrado na tela")
    p.add_argument("--img", action="append", default=[])
    p.add_argument("--tz", default="America/Sao_Paulo")
    p.add_argument("--ranking", action="store_true")
    a = p.parse_args()

    if a.ranking:
        for i, (s, m, qv) in enumerate(alphax.worst_24h(30), 1):
            print(f"{i:2d} {s:28s} {m*100:7.2f}%  vol {qv:,.0f}")
        return

    dt = datetime.fromisoformat(a.when)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(a.tz))
    ts = int(dt.timestamp() * 1000)
    s = alphax.sym(a.symbol)
    ex_id = f"{dt.astimezone(ZoneInfo('UTC')):%Y%m%dT%H%M}_{s.split('-')[0]}"

    out = ROOT / "data" / ex_id
    out.mkdir(parents=True, exist_ok=True)
    for iv in ("4h", "15m", "1h"):
        (out / f"{iv}.json").write_text(json.dumps(alphax.klines(s, iv, 500, ts)))

    rec = {"id": ex_id, "symbol": s, "label": a.label, "time_ms": ts, "time": dt.isoformat(),
           "reason": a.reason, "rank24h": a.rank, "ret24h_pct": a.ret, "images": a.img}
    with LOG.open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("ok", ex_id)


if __name__ == "__main__":
    main()
