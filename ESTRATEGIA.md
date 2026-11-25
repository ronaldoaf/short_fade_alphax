# Estratégia Short Fade (regra C6 + filtro de volatilidade)

Short em perpétuos USDT que estão entre os que mais caíram em 24h, desde que estejam em tendência de queda
no 4h e no 15m, e só quando o mercado cripto está calmo.

## 1. Indicadores
- **Médias:** médias móveis simples (SMA) do **fechamento**: MA5, MA10, MA30.
- **Vela em formação:** o candle de 4h ainda aberto **entra** no cálculo, usando o preço atual como fechamento
  (igual ao que os apps de corretora mostram).
- **Avaliação:** a cada fechamento de candle de 15m.
- **ATR(14) do 4h:** média simples dos últimos 14 *true ranges* de velas de 4h **fechadas**, dividida pelo
  último fechamento de 4h (em fração do preço).

## 2. Universo
1. Todos os perpétuos USDT **de criptomoedas** da corretora. Ficam fora ações, ETFs (inclusive alavancados),
   índices, forex e commodities (ouro, petróleo etc.), mesmo quando negociados como perpétuos.
2. **Retorno de 24h** = fechamento atual ÷ fechamento de 24h atrás (96 candles de 15m) − 1.
3. **Volume de 24h ≥ 50.000 USDT.**
4. Ordenar do pior para o melhor retorno e considerar só os **5 piores**.

## 3. Filtro de mercado (volatilidade do índice cripto)
**Índice:**
- Pesos iguais entre as **30 criptos com maior volume no spot da Binance nas 8 semanas anteriores**.
- Rebalanceado toda **segunda-feira 00:00 UTC**, usando o volume dos 56 dias anteriores.
- BTC e ETH sempre incluídos.
- Excluídos: stablecoins (USDC, FDUSD, TUSD, DAI etc.), moedas fiduciárias, ouro (PAXG, XAUT),
  versões embrulhadas (WBTC, WBETH) e tokens alavancados (…UP/DOWN/BULL/BEAR).
- Retorno do índice a cada 15m = média simples dos retornos de 15m dos 30 membros.

**Regra:**
- **Volatilidade** = desvio-padrão dos retornos de 15m do índice nos últimos **7 dias** (672 candles).
- **Limiar** = mediana dessa volatilidade nos últimos **90 dias** (só dados passados).
- **Só operar se volatilidade ≤ limiar** (mercado calmo, cerca de metade do tempo).

## 4. Condições de entrada (todas obrigatórias)
**Gráfico de 4h:**
1. Preço < MA30.
2. MA5 < MA10 < MA30.
3. MA30 atual < MA30 de 10 velas de 4h atrás (MA30 caindo).

**Gráfico de 15m:**
4. Preço < MA30.
5. MA30 atual < MA30 de 10 candles atrás.
6. MA5 < MA10.
7. Preço no máximo **20% abaixo** da MA30, ou seja, preço ≥ 0,8 × MA30 (evita entrar no meio de um crash).

## 5. Execução
| Item | Valor |
|---|---|
| Lado | Short |
| Alavancagem | 10x fixo, margem isolada (alavancagem menor em ativos voláteis foi testada e piorou) |
| Entrada | Preço de fechamento do candle de 15m que gerou o sinal |
| Alvo | Queda de **15%** no preço (+150% da margem) |
| Stop | Entrada × (1 + ATR(14) do 4h) |
| Liquidação | Alta de cerca de 9,5%. Se o stop ficar acima disso, a perda máxima é a margem |
| Saída por tempo | **48h** após a entrada, a mercado |
| Posições | No máximo uma por ativo. Reentrada permitida assim que a anterior fechar |
| Tamanho | Igual em todas as operações |

## 6. Custos considerados no teste
- Funding real: o short recebe o funding positivo e paga o negativo.
- Taxa de negociação: 0% (cenário principal) e 0,05% por lado (cenário alternativo).

## 7. Resultado do backtest
Dados de 15m da Binance (cerca de 670 perpétuos USDT de cripto, incluindo deslistados), de jan/2023 a nov/2026.
Os parâmetros foram escolhidos no treino e na validação, e o teste foi rodado uma única vez.

| Período | Operações | Média por operação (taxa 0) | Média por operação (taxa 0,05%) |
|---|---|---|---|
| Treino (jan/23 a jun/24) | 1.390 | +8,4% | +7,4% |
| Validação (jul/24 a jun/25) | 1.273 | +12,9% | +12,0% |
| Teste (jul/25 a nov/26) | 2.140 | +4,4% | +3,6% |

Os valores estão em % da margem por operação.

- Saídas no teste: alvo 26%, stop 38%, liquidação 20%, tempo 16%.
- Meses positivos no teste: 11 de 16.
- Pior sequência de perdas: −44 margens (com 1 margem por operação).

## 8. Detalhes que mudam o resultado ao reproduzir
- **Ordem dentro do candle:** quando alvo e stop (ou liquidação) acontecem no mesmo candle de 15m, conte o stop
  ou a liquidação (hipótese conservadora).
- **Vela de 4h em formação:** inclua a vela de 4h ainda aberta nas médias. Usar só velas fechadas atrasa o sinal.
- **Frequência:** avalie a cada 15m. Avaliar só a cada hora muda bastante quais operações acontecem.
- **Universo:** o ranking é feito entre **todas** as criptos da corretora (não só as que existem em outra corretora).
  Com outro conjunto de ativos, os 5 piores mudam. Se a corretora não informar a categoria, separe ações/ETFs pelo
  nome (Inc, Corp, ETF...) e pelo comportamento no fim de semana (ações quase não se movem sáb/dom).
- **Volatilidade alta:** quando o ATR passa de cerca de 9,5%, o stop fica além da liquidação. Isso aconteceu
  em cerca de 20% das operações do teste.
- **Período:** o resultado varia muito de mês a mês. Use pelo menos um ano de dados para avaliar.
