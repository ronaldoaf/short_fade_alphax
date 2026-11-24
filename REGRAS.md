# Estratégia Short Fade AlphaX

> **Regra em uso: C6** (adotada no scanner em 23/11/2026). Resumo:
> 5 piores de 24h (vol ≥ 50k; top 5 adotado em 23/11 — teste +2,7%/trade vs +3,1% no top 3, com ~50% mais trades) · 4h: preço < MA30, MA5 < MA10 < MA30, MA30 caindo ·
> 15m: preço < MA30, MA30 caindo, MA5 < MA10, no máx. 20% abaixo da MA30 ·
> **filtro de mercado: só operar com a volatilidade de 7d do índice cripto (30 maiores, pesos iguais) abaixo da mediana de 90 dias** (adotado em 24/11) ·
> short 10x, alvo −15%, stop 1 ATR(14) do 4h, saída em 48h.
> Backtest C6 top 5 + filtro (taxa 0): treino +8,3%, validação +12,8%, teste +4,7% por trade.
> As seções abaixo documentam a regra original (v1) e o histórico de testes.

## Regra original (v1)

Médias = SMA sobre o fechamento (igual ao app da AlphaX): MA5, MA10, MA30.
O candle em formação entra no cálculo (como no app).

## 1. Universo
- Perpétuos USDT da AlphaX ordenados pelo **pior retorno de 24h**.
- Considerar os **10 piores** (os 5 piores deram resultado melhor por trade no backtest).
- **Volume 24h >= 50.000 USDT**. Na fase de teste ($1 por trade) o limite é flexível.

## 2. Gráfico de 4h: tendência (decide SE o ativo serve)
1. Preço **abaixo da MA30**.
2. Médias em ordem de queda: **MA5 < MA10 < MA30**.
3. **MA30 caindo**: menor que a MA30 de 10 velas atrás.
4. **Sem candle de alta grande** nas últimas 10 velas: nenhuma vela verde com amplitude > **4x** a amplitude média do ativo.

## 3. Gráfico de 15m: momento (decide QUANDO entrar)
5. Preço **abaixo da MA30**.
6. **MA30 caindo** (menor que 10 velas atrás).
7. **Sem candle de alta grande** nas últimas 10 velas: nenhuma vela verde com amplitude > **4x** a média.
   - MA5 < MA10 é desejável (coluna `agora` do scanner), mas não obrigatório.

## 4. Execução
- **Short**, alavancagem **10x**, margem **isolada**.
- **Alvo: +100% da margem** (queda de 10% no preço).
- **Sem stop**: liquidação numa alta de ~9,5%.
- **Saída por tempo: 24h** (fecha a mercado).
- **Reentrada** no mesmo ativo permitida sempre que a configuração continuar válida.

## Resultado no backtest (15/10 a 20/11/2026, com funding)
| Universo | Trades | Alvo | Liquidação | Tempo | Média/trade |
|---|---|---|---|---|---|
| 10 piores | 523 | 33% | 26% | 41% | +10,0% |
| 5 piores | 312 | 44% | 31% | 25% | +14,5% |

Ressalva: só ~1 mês de dados, período de mercado em queda.

## Testados e descartados / sem efeito
- Rompimento da mínima de 20 velas de 4h (`--brk`): sem efeito.
- Vela de baixa grande recente no 4h (`--bigdn`): não melhorou.
- Tendência de 4h já existente 2 velas antes (`--pre`): piorou.
- Remover o 15m (`--no15`): piora muito (+10,0% → +6,6%).
- Alvos de 125% a 200% (`--tp`): resultado total parecido; mantido 100%.
- Funding: impacto médio desprezível (< 0,2% da margem), mas casos extremos de até -30%.
- Preço muito esticado abaixo da MA30 do 15m (`--maxdist15`, ex.: queda repentina do ACE −31%, AKE −24%; ✅ sempre ≤ 8%): casos raros (~1%), sem efeito no resultado (+10,0% → +10,3% com limite de 20%). Pode ser usado como filtro discricionário sem custo.
- Versão long espelhada (`--long`): perde (-11,6%/trade).

## Ferramentas
- `python tools/scan.py`: sinais ao vivo.
- `python tools/backtest.py`: backtest (opções acima).

## Testes de saída (`python tools/exits.py`) — ATR(14) 4h mediano nas entradas: 6,4%
| Variante | Trades | Média | Soma | Liq |
|---|---|---|---|---|
| Atual: alvo 10% | 515 | +11,0% | +56 | 25% |
| Alvo 2 ATR | 451 | +13,5% | +61 | 24% |
| Alvo 10% + stop 1 ATR | 547 | +11,8% | +64 | 12% |
| Trailing 1,5 ATR ativa após 1 ATR | 428 | +13,4% | +57 | 20% |
| Trailing fixo 5% sem alvo | 702 | +10,0% | +70 | 0% |
| Sem alvo, 48h | 301 | +26,4% | +80 | 29% |
Conclusão: diferenças de média dentro do ruído; stop/trailing reduzem muito as liquidações. Nenhuma mudança adotada ainda.

## Validação com dados da Binance (1 ano, 893 perpétuos, nov/2025 a nov/2026)
| | Trades | Média/trade (sem taxa) | Com taxa 0,05%/lado |
|---|---|---|---|
| Regra (top 10) | 6622 | +1,3% | ≈ +0,3% |
| Só ranking | 20703 | −0,1% | ≈ −1,1% |
Meses alternam entre positivos e negativos. Funding na Binance custa −1,0%/trade em média (na AlphaX ~0).
Na Binance a vantagem da regra é pequena e some com taxas; na AlphaX (0 taxas, outro universo) foi +10%/trade em 1 mês.

## Comparação com o backtest do outro agente (`outro_agente/`)
- Simuladores concordam: nas 640 operações idênticas (mesmo ativo e horário) as saídas batem, exceto onde ele usa stop de 1 ATR.
- Preços AlphaX = Binance: as 466 operações do backtest AlphaX repetidas com candles da Binance dão +10,6% (AlphaX +10,0%).
- Diferenças são de definição, não de dados nem de bug:
  1. Universo do ranking: ele ranqueia só 315 criptos da AlphaX com par na Binance; eu, todos os 893 da Binance (ou 969 da AlphaX, com ações).
  2. Avaliação a cada hora (ele) x a cada 15m (eu).
  3. Ele adiciona stop de 1 ATR do 4h; a estratégia original não tem stop.
  4. Taxa 0,05%/lado no cenário principal dele (−1%/trade).
- Último mês (22/10–21/11) no backtest dele: +2,7%/trade com taxa, +3,7% sem — positivo.
- 12 meses, taxa zero: ele +0,5%/trade; eu (Binance, todos ativos) +0,4%. Conclusão comum: **vantagem pequena, perto de zero ao longo de um ano**; o +10% em 1 mês de AlphaX foi um período favorável.

## Otimização com Binance (jan/2023–nov/2026): treino / validação / teste (`tools/opt.py`)
Treino jan/23–jun/24 · Validação jul/24–jun/25 · Teste jul/25–nov/26 (avaliado uma única vez).
Custos: funding real + taxa 0 (AlphaX) ou 0,05%/lado.

**Regra candidata (C6)** — mudanças em relação à atual:
- Universo: só os **3 piores** de 24h (era 10). Volume mínimo não fez diferença na Binance.
- 15m: exigir **MA5 < MA10** e preço no máximo **20% abaixo da MA30**.
- Filtros de candle de alta grande (4h e 15m): sem efeito → removidos.
- Saída: alvo **−15%** no preço (+150% da margem), **stop em 1 ATR(14) do 4h**, tempo máximo **48h**.

| Período | Atual (taxa 0) | C6 (taxa 0) | C6 (taxa 0,05%) |
|---|---|---|---|
| Treino | −1,3% (5595) | +4,8% (1764) | +3,8% |
| Validação | +2,6% (5039) | +4,7% (1696) | +3,8% |
| Teste | +0,4% (8356) | **+3,1% (2924)** | **+2,3%** |
Meses positivos C6: treino 10/18, validação 7/12, teste 9/17. Pior drawdown: −57 margens (soma de todos os trades).
Vizinhos (alvo 10–20%, top 3–5, 24–48h, stop 1 ATR) também positivos em treino e validação.
Ressalvas: resultado depende de poucos meses fortes; quando o ATR passa de 9,5% o stop vira liquidação.

### Filtro de mercado (BTC/ETH) — testado e descartado
Testados sobre a C6: BTC/ETH abaixo da MA30 do 4h, da MA20 e MA50 diárias, queda em 24h e 7 dias, ambos/algum, e amplitude (% de ativos caindo).
Nenhum melhorou treino **e** validação. O efeito troca de sinal entre os períodos (ex.: BTC abaixo da MA30 4h: treino +3,0% vs +9,2% com mercado em alta; validação +6,5% vs +1,7%). Sem filtro de mercado.

### Filtro com índice cripto (30 maiores por volume spot, pesos iguais, rebalanceio semanal)
No treino e na validação, operar só com o índice abaixo da MA20 diária melhorou (C6 +4,8%→+6,3% e +4,7%→+6,1%).
**No teste falhou: +3,1% → −0,9%** (com taxa 0,05%: +2,3% → −1,6%). O filtro não generaliza → descartado.
Conclusão geral: nenhum filtro de regime de mercado (BTC, ETH ou índice) se mostrou estável.

### Filtro de volatilidade do índice cripto (`tools/vol_regime.py`) — APROVADO no teste
Volatilidade = desvio-padrão dos retornos de 15m do índice (30 maiores, pesos iguais) numa janela; limiar = mediana móvel dos últimos 90 dias (sem olhar o futuro).
Operar **só quando a volatilidade de 7 dias do índice está ABAIXO da mediana de 90 dias** (~49% do tempo).

| C6 top 5, taxa 0 | Treino | Validação | Teste |
|---|---|---|---|
| Sem filtro | +1,9% (2735) | +3,8% (2609) | +2,7% (4419) |
| Vol 7d baixa | **+8,3%** (1439) | **+12,8%** (1329) | **+4,7%** (2193) |
| Vizinho vol 3d baixa | +6,8% | +9,5% | +6,7% |
| Vizinho vol 1d baixa | +9,2% | +6,9% | +5,6% |
Com taxa 0,05%: teste +1,9% → +3,9%/trade. Soma no teste parecida (+85 nos dois), com metade dos trades.
Meses positivos: treino 9/16, validação 10/12, teste 11/14. Pior drawdown −46 margens (sem filtro −57 no top 3).
Escolha feita em treino+validação (efeito consistente em todas as janelas com mediana de 90d); teste rodado uma vez.

### Long espelhado da C6 (`tools/opt_long.py`) — sem vantagem
Melhores de 24h, tendência de alta no 4h e 15m, alvo +15%, stop 1 ATR, 48h. Taxa 0:
| | Treino | Validação | Teste |
|---|---|---|---|
| Top 3 sem filtro | +1,5% | −1,6% | +0,2% |
| Top 3 vol baixa | −0,2% | −1,8% | +0,9% |
| Top 5 sem filtro | +0,1% | −1,6% | −1,1% |
| Top 10 sem filtro | −1,4% | −1,8% | −2,5% |
Filtro de volatilidade não ajuda o long de forma consistente. Com taxa 0,05% quase tudo negativo. Long descartado.

### Índice alternativo: 10 maiores por valor de mercado (`tools/vol_mcap.py`)
Pesos iguais, sem stablecoins, composição aproximada por semestre (sem histórico de market cap nos dados).
| C6, taxa 0 | Treino | Validação | Teste |
|---|---|---|---|
| Top 5, vol baixa, 30 por volume | +8,4% | +12,9% | +4,8% |
| Top 5, vol baixa, 10 por mkt cap | +8,7% | +10,2% | +5,5% |
| Top 10, vol baixa, 30 por volume | +7,8% | +10,9% | +2,6% |
| Top 10, vol baixa, 10 por mkt cap | +8,3% | +7,9% | +4,0% |
Resultados equivalentes (o filtro é robusto à escolha do índice). Mantido o índice de 30 por volume.

### Índice alternativo: 10 maiores por volume spot (`tools/vol_top10.py`)
Mesma construção do índice de 30 (8 semanas, rebalanceio semanal), com n=10.
| C6, taxa 0 | Treino | Validação | Teste |
|---|---|---|---|
| Top 5, vol baixa, 30 por volume | +8,4% | +12,9% | +4,8% |
| Top 5, vol baixa, 10 por volume | +10,0% | +10,5% | +5,4% |
| Top 10, vol baixa, 30 por volume | +7,8% | +10,9% | +2,6% |
| Top 10, vol baixa, 10 por volume | +9,3% | +8,8% | +2,4% |
Equivalentes dentro do ruído. Mantido o índice de 30.
