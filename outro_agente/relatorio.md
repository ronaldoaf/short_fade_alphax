# Short nos piores de 24h (estratégia manual AlphaX), backtest com dados Binance

**Resultado: não tem vantagem.** Com os custos reais o valor esperado por operação é negativo em todas as variantes, no treino e no teste. Ficar só nos 5 piores **não** foi melhor que nos 10.

## Dados e regras
- Klines de 15m dos perps USDT-M da Binance (data.binance.vision), de jan/2025 a out/2026. São 324 ativos da lista AlphaX com par na Binance (CRYPTO + XAU + CL/WTI). US100 não existe na Binance.
- Funding real da Binance (o short recebe o funding positivo). Taxas em dois cenários: 0,05% por lado e taxa zero (a promoção atual da AlphaX).
- A cada hora cheia: ranking pelo retorno de 24h, com volume 24h ≥ 50k USDT, e N piores (5 ou 10).
- No 4h, com a vela em formação usando o fechamento do momento: preço < MA30, MA5 < MA10 < MA30, MA30 < MA30 de 10 velas atrás, e nenhuma vela verde com amplitude > 4× a média (100 velas) nas últimas 10.
- No 15m: preço < MA30, MA30 caindo, e nenhuma vela verde grande nas últimas 10. A variante `ma5<ma10_15m` exige também MA5 < MA10.
- Short 10x isolado, entrada no fechamento. TP com queda de 10%. SL = entrada + 1 ATR(14) do 4h. Saída após 24h. Se SL e TP caem na mesma vela de 15m, conta o SL. Uma posição por ativo, e reentrada permitida assim que fecha.
- Liquidação isolada com alta de ~9,5%: quando o ATR é maior que isso, a posição é liquidada antes do SL e perde 100% da margem.
- Treino = 2025, teste = 2026.

## Resultados (por operação, em % da margem de $1)
| Variante | Período | Custos | Ops | Win % | EV/op | Soma ($) | Max DD ($) |
|---|---|---|---|---|---|---|---|
| 5 piores | treino | 0,05% + funding | 2326 | 46,0 | -1,61% | -37,5 | -77 |
| 5 piores | teste | 0,05% + funding | 2666 | 46,4 | -1,33% | -35,4 | -70 |
| 5 piores | teste | taxa 0 + funding | 2666 | 46,5 | -0,33% | -8,8 | -63 |
| 10 piores | treino | 0,05% + funding | 4098 | 44,8 | -1,14% | -46,6 | -150 |
| 10 piores | teste | 0,05% + funding | 4515 | 45,7 | -1,35% | -61,0 | -112 |
| 10 piores | teste | taxa 0 + funding | 4515 | 46,0 | -0,35% | -15,8 | -92 |

A tabela completa, com a variante MA5<MA10 no 15m, está em `resumo.csv`. Essa exigência muda pouco: a melhor célula é 10 piores no treino com taxa 0, em +0,16%/op, e no teste dá -0,37%.

## Por que não funciona
- Como as saídas se distribuem (5 piores): TP 30% (+97%), saída por tempo 26% (+14%), SL 26% (-58%), **liquidação 19% (-100%)**.
- Nos piores de 24h o ATR de 4h passa com frequência de 9,5%, então o "SL de 1 ATR" vira liquidação. Isso pesa sozinho cerca de -19 p.p. por operação.
- O funding médio é levemente contra o short (-0,7% da margem por operação): esses ativos costumam ter funding negativo.
- Por mês, o resultado alterna entre positivo e negativo sem tendência. Os meses bons (nov/25, jan/26) não compensam out/25 e abr/26.
- XAU, BTC e ETH quase nunca entram no ranking (BTC 1 op, ETH 1, CL 7), então não há amostra para eles.

Arquivos: `trades_N5.csv`, `trades_N10.csv` (cada operação), scripts `dl.py`, `sim.py`, `bt.py`, `an.py`.
