# short_fade_alphax

Objetivo: transformar em regras objetivas uma estratégia discricionária de short na AlphaX:
pegar os ativos com pior retorno de 24h e operar quando estão em tendência de queda **no 4h e no 15m ao mesmo tempo**.

## Estrutura
- `examples/examples.jsonl`: um exemplo rotulado por linha (`yes` = operaria, `no` = não operaria)
- `examples/screens/`: prints enviados
- `data/<id>/{4h,15m,1h}.json`: candles da AlphaX até o momento de cada exemplo
- `tools/alphax.py`: cliente da API pública
- `tools/snapshot.py`: registra exemplo + baixa candles; `--ranking` mostra os piores de 24h agora

## Como enviar um exemplo
Prints de 4h e 15m, ✅/❌, ticker, data/hora (com fuso), posição no ranking de 24h, motivo em uma frase e, se operou, o resultado.

## Backtest
```
python tools/download.py      # baixa/atualiza 15m de todos os perpétuos (data/cache, fora do git)
python tools/download_funding.py  # histórico de funding
python tools/backtest.py      # opções: --top 10 --vol 50000 --liq 9.5 --big 4
```
Trades da regra são salvos em `data/backtest_trades.csv`.
