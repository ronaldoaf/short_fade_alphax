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
- Versão long espelhada (`--long`): perde (-11,6%/trade).

## Ferramentas
- `python tools/scan.py`: sinais ao vivo.
- `python tools/backtest.py`: backtest (opções acima).
