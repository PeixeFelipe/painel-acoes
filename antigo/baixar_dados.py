"""Baixa a cotação diária de 2025 de Petrobras, Itaú e Vale e salva em dados.js.

Uso:  python baixar_dados.py
Requer:  pip install yfinance
"""
import json
from pathlib import Path

import yfinance as yf

EMPRESAS = [
    {"codigo": "PETR4", "nome": "Petrobras", "ticker": "PETR4.SA"},
    {"codigo": "ITUB4", "nome": "Itaú", "ticker": "ITUB4.SA"},
    {"codigo": "VALE3", "nome": "Vale", "ticker": "VALE3.SA"},
]
INICIO = "2025-01-01"
FIM = "2026-01-01"  # o Yahoo trata o fim como exclusivo, então isso inclui 31/12/2025

saida = []
for e in EMPRESAS:
    # auto_adjust=False: preço de fechamento "puro" (como na corretora), sem somar dividendos
    df = yf.Ticker(e["ticker"]).history(start=INICIO, end=FIM, auto_adjust=False)
    if df.empty:
        raise SystemExit(f"Nenhum dado retornado para {e['ticker']}. Verifique a internet.")
    saida.append({
        "codigo": e["codigo"],
        "nome": e["nome"],
        "datas": [d.strftime("%Y-%m-%d") for d in df.index],
        "fechamento": [round(float(v), 2) for v in df["Close"]],
    })
    print(f"{e['codigo']}: {len(df)} pregões, {df.index[0]:%d/%m/%Y} a {df.index[-1]:%d/%m/%Y}")

conteudo = "// Gerado por baixar_dados.py — não edite à mão.\nconst DADOS = " + json.dumps(saida, ensure_ascii=False, indent=1) + ";\n"
Path(__file__).with_name("dados.js").write_text(conteudo, encoding="utf-8")
print("dados.js salvo.")
