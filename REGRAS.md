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
4. Estar esticado para baixo (até -22% da MA30) **não** impediu entrada.

## 15m (confirmação)
5. Preço < MA30 e MA30 caindo. MA5 < MA10 **não** é obrigatório: no ✅ MUBARAK a MA5 estava
   levemente acima da MA10 (lateralização curta abaixo da MA30).
6. Sem repique em andamento (preço voltando acima da MA30). Ex.: ZIL.

## Placar
6 exemplos (3 ✅, 3 ❌), regra (com 15m relaxado) acerta 6/6. Ainda poucos dados.
