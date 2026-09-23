"""Busca cotações no Yahoo Finance e guarda o resultado por 15 minutos.

Assim o app não consulta o Yahoo a cada clique, e todos os usuários
aproveitam a mesma consulta.
"""
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

VALIDADE_SEGUNDOS = 15 * 60
PADRAO_CODIGO = re.compile(r"^[A-Z]{4}[0-9]{1,2}$")  # ex.: PETR4, BBAS3, BOVA11

NOMES = {
    "PETR4": "Petrobras", "PETR3": "Petrobras", "ITUB4": "Itaú", "ITUB3": "Itaú",
    "VALE3": "Vale", "WEGE3": "WEG", "BBAS3": "Banco do Brasil", "BBDC4": "Bradesco",
    "BBDC3": "Bradesco", "ABEV3": "Ambev", "B3SA3": "B3", "RENT3": "Localiza",
    "SUZB3": "Suzano", "ELET3": "Eletrobras", "ITSA4": "Itaúsa", "RADL3": "RaiaDrogasil",
    "LREN3": "Lojas Renner", "MGLU3": "Magazine Luiza", "JBSS3": "JBS", "GGBR4": "Gerdau",
    "CSNA3": "CSN", "EMBR3": "Embraer", "PRIO3": "PRIO", "RAIL3": "Rumo",
    "SBSP3": "Sabesp", "BBSE3": "BB Seguridade", "CMIG4": "Cemig", "EQTL3": "Equatorial",
    "HAPV3": "Hapvida", "KLBN11": "Klabin", "BOVA11": "ETF Ibovespa",
}


class ErroCotacao(Exception):
    """Erro com mensagem já pronta para mostrar ao usuário."""

    def __init__(self, tipo, mensagem):
        super().__init__(mensagem)
        self.tipo = tipo  # "inexistente" ou "indisponivel"
        self.mensagem = mensagem


def normalizar_codigo(texto):
    """'  wege3.sa ' -> 'WEGE3'. Devolve None se não parecer um código válido."""
    codigo = (texto or "").strip().upper()
    if codigo.endswith(".SA"):
        codigo = codigo[:-3]
    return codigo if PADRAO_CODIGO.match(codigo) else None


def nome_da_empresa(codigo):
    return NOMES.get(codigo, codigo)


def _yahoo_responde():
    import requests
    try:
        requests.get("https://query1.finance.yahoo.com", timeout=5)
        return True
    except Exception:
        return False


def buscar_yahoo(codigo):
    """Baixa todo o histórico diário de fechamento. Devolve (datas, fechamentos)."""
    import yfinance as yf

    indisponivel = ErroCotacao(
        "indisponivel",
        "Não consegui falar com o Yahoo Finance agora. Verifique sua internet ou tente de novo em alguns minutos.",
    )
    try:
        # auto_adjust=False: preço de fechamento "puro" (como na corretora), sem dividendos
        df = yf.Ticker(codigo + ".SA").history(period="max", auto_adjust=False)
    except Exception:
        raise indisponivel
    if df is None or df.empty:
        if not _yahoo_responde():
            raise indisponivel
        raise ErroCotacao("inexistente", f"Não encontrei a ação {codigo} no Yahoo Finance. Confira se o código está certo.")
    df = df.dropna(subset=["Close"])
    datas = [d.strftime("%Y-%m-%d") for d in df.index]
    fechamento = [round(float(v), 2) for v in df["Close"]]
    return datas, fechamento


_cache = {}  # codigo -> {"quando": segundos, "datas": [...], "fechamento": [...]}
_trava = threading.Lock()


def obter(codigo):
    """Devolve os dados do cache se estiverem frescos; senão busca de novo.

    Se a busca falhar mas houver dados antigos, devolve os antigos (desatualizado=True).
    """
    agora = time.time()
    with _trava:
        item = _cache.get(codigo)
    if item and agora - item["quando"] < VALIDADE_SEGUNDOS:
        return {**item, "desatualizado": False}
    try:
        datas, fechamento = buscar_yahoo(codigo)
    except ErroCotacao as erro:
        if item and erro.tipo == "indisponivel":
            return {**item, "desatualizado": True}
        raise
    novo = {"quando": agora, "datas": datas, "fechamento": fechamento}
    with _trava:
        _cache[codigo] = novo
    return {**novo, "desatualizado": False}


def obter_varias(codigos):
    """Busca várias ações ao mesmo tempo. Devolve (itens, erros)."""
    if not codigos:
        return [], []

    def uma(codigo):
        try:
            return codigo, obter(codigo), None
        except ErroCotacao as erro:
            return codigo, None, erro

    with ThreadPoolExecutor(max_workers=min(len(codigos), 8)) as pool:
        resultados = list(pool.map(uma, codigos))

    itens, erros = [], []
    for codigo, dados, erro in resultados:
        if erro:
            erros.append({"codigo": codigo, "mensagem": erro.mensagem})
        else:
            itens.append({
                "codigo": codigo,
                "nome": nome_da_empresa(codigo),
                "datas": dados["datas"],
                "fechamento": dados["fechamento"],
                "desatualizado": dados["desatualizado"],
                "atualizado_em": int(dados["quando"]),
            })
    return itens, erros
