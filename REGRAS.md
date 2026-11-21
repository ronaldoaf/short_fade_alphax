# Regras provisórias (atualizadas conforme os exemplos)

Médias = SMA sobre o fechamento (igual ao app da AlphaX): MA5, MA10, MA30.

## Universo
- Ativos ordenados pelo pior retorno de 24h.
- Liquidez: referência de volume 24h >= 50K USDT. **Fase de teste (aposta de $1): filtro flexível**,
  aceita menos se a configuração for muito boa. Endurecer quando o tamanho aumentar.

## 4h (tendência principal)
1. Preço < MA30 e MA5 < MA10 < MA30.
2. MA30 caindo (ex.: menor que 10 velas atrás). Nos ❌ PROS e SPCH ela ainda subia.
3. Sem candle de alta grande nas últimas ~10 velas (amplitude > ~4x a média). Ex.: ZIL.
4. Vela(s) de baixa muito grande(s) nas últimas ~3 velas de 4h (queda > ~2,5–3x a amplitude média): você recusa (SPCH 2,9x, TWLO 3,7x; AGPU 1,8x aprovado). **No backtest esse filtro não melhorou o resultado** (`--bigdn`), então por ora fica desligado.
5. Estar esticado para baixo (até -22% da MA30) **não** impediu entrada.

## 15m (confirmação)
5. Preço < MA30 e MA30 caindo. MA5 < MA10 **não** é obrigatório: no ✅ MUBARAK a MA5 estava
   levemente acima da MA10 (lateralização curta abaixo da MA30).
6. Sem candle de alta grande no 15m nas últimas 10 velas (amplitude > **4x** a média). AKE (❌) tinha 13,4x; todos os ✅ ≤ 2,2x. No backtest: +8,5% → **+10,0%** por trade e menos liquidações.
7. Sem repique em andamento (preço voltando acima da MA30). Ex.: ZIL.

## Placar
19 exemplos (10 ✅, 9 ❌; inclui 5 do scanner), regra acerta os 14 com print. Ainda poucos dados.

## Reentrada
- Permitida no mesmo ativo sempre que a configuração continuar válida. O resultado da operação anterior não influencia (MUBARAK).

## Execução (atual)
- Short, alavancagem 10x, margem isolada, ~$1 por operação.
- TP: +100% sobre a margem = queda de **10%** no preço.
- Sem SL: a margem é liquidada numa alta de ~**9–10%** (10% menos a margem de manutenção).
- Payoff ≈ 1:1 → é preciso acertar **mais de ~50%** (mais um pouco por causa do funding) para lucrar.
- Saída por tempo: se nem TP nem liquidação ocorrerem em **24h**, fecha a mercado (resultado = variação do preço x10).

## Observações testadas e sem efeito no backtest (por ora)
- Rompimento da mínima de 20 velas de 4h (SOXL, MVLL citam "rompeu a mínima com momentum"): mesmo resultado médio com ou sem (`--brk`).
- Exigir que a tendência de queda no 4h já existisse 2 velas antes (`--pre`): piorou o backtest (+7,2%) e reprovaria o SOXL (✅). Descartado.
- Exigir MA5 < MA10 no 15m (`--m15 1`): +10,0% → +11,0% por trade, mas reprovaria o MUBARAK (✅). Diferença pequena; em observação. O NVDL (❌, "15m subindo") tinha MA5 > MA10 e preço voltando acima da MA30.

## Uso do scanner
- Coluna `agora` reavalia com o candle de 15m em formação (exige também MA5 < MA10). Confirme no gráfico antes de entrar: o sinal pode mudar dentro do candle.
