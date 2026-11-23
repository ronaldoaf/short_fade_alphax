# Estratégia Short Fade AlphaX: regras atuais

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
