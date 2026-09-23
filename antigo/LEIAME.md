# Cotação de Petrobras, Itaú e Vale em 2025

Página simples que mostra o preço e a performance de PETR4, ITUB4 e VALE3 ao longo de 2025.

## Como abrir

Dê dois cliques em **index.html**. Precisa de internet só para carregar a biblioteca de gráficos (Chart.js).

## Arquivos

| Arquivo | Para que serve |
|---|---|
| `index.html` | A página: layout, cores e tabelas. É o arquivo que você abre. |
| `app.js` | Calcula a variação % e desenha cartões, gráficos e tabelas. |
| `dados.js` | Preços diários de fechamento de 2025 (gerado pelo script abaixo). |
| `baixar_dados.py` | Baixa os preços de novo do Yahoo Finance e reescreve o `dados.js`. |

## Como atualizar os dados (opcional)

No terminal, dentro desta pasta:

```
pip install yfinance
python baixar_dados.py
```

Depois recarregue a página (F5).

## Para mudar algo

- **Outras ações ou outro período:** edite a lista `EMPRESAS` e as datas `INICIO`/`FIM` no `baixar_dados.py` e rode-o de novo. O visual foi pensado para 3 ações.
- **Preços com dividendos:** no `baixar_dados.py`, troque `auto_adjust=False` por `auto_adjust=True`.

## Observações

- Os preços são de fechamento, sem dividendos.
- Fonte: Yahoo Finance. Pode haver diferença de centavos em relação à sua corretora.
