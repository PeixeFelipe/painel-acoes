"""Análise do Dia: prepara o resumo numérico da carteira e pede o texto à IA da Anthropic.

A IA nunca vê gráficos nem busca nada na internet: ela só recebe os números calculados aqui.
As instruções dela ficam no arquivo instrucoes_analista.md (pode ser editado sem mexer no código).
"""
import hashlib
import logging
import math
import os
import statistics
import threading
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import anthropic

import cotacoes

PASTA = Path(__file__).resolve().parent
ARQUIVO_INSTRUCOES = PASTA / "instrucoes_analista.md"

# O modelo mais barato da Anthropic. Dá para trocar sem mexer no código: variável MODELO_IA.
MODELO_PADRAO = "claude-haiku-4-5-20251001"
MAX_TOKENS_SAIDA = 900          # o texto tem no máximo 250 palavras; sobra folga
VALIDADE_SEGUNDOS = 15 * 60     # mesma carteira + mesmo período: reaproveita a análise
LIMITE_POR_HORA = 10            # análises NOVAS por pessoa (as reaproveitadas não contam)
BRASILIA = timezone(timedelta(hours=-3))  # o Brasil não tem mais horário de verão

# id -> (rótulo, meses para trás). "ano" e "max" têm regra própria.
PERIODOS = {
    "1m": ("1 mês", 1),
    "3m": ("3 meses", 3),
    "6m": ("6 meses", 6),
    "ano": ("No ano", None),
    "1a": ("1 ano", 12),
    "max": ("Máximo", None),
}

log = logging.getLogger("analise")
_trava = threading.Lock()
_cache = {}      # chave -> {"texto", "quando", "periodo", "de", "ate"}
_historico = {}  # id do usuário -> horários das análises novas


# ---------- Formatação brasileira ----------
def _numero(n, casas=2):
    return f"{n:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _reais(n):
    return "R$ " + _numero(n)


def _pct(fracao):
    return f"{fracao * 100:+.1f}%".replace(".", ",")


def _data(iso):
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}"


def _limpo(texto, limite=60):
    """Texto que vai para dentro do bloco de dados: sem quebras de linha nem sinais < >."""
    return " ".join(str(texto).replace("<", " ").replace(">", " ").split())[:limite]


# ---------- Resumo numérico ----------
def data_de_corte(periodo_id, ultima):
    """Mesma regra da página Ações: 'ano' começa em 1º de janeiro; os demais voltam N meses."""
    if periodo_id == "max":
        return ""
    ano, mes, dia = (int(p) for p in ultima.split("-"))
    if periodo_id == "ano":
        return f"{ano}-01-01"
    meses = PERIODOS[periodo_id][1]
    total = ano * 12 + (mes - 1) - meses
    primeiro_do_mes = date(total // 12, total % 12 + 1, 1)
    return (primeiro_do_mes + timedelta(days=dia - 1)).isoformat()  # transborda como o JavaScript faz


def resumir_acao(item, corte):
    """Números de uma ação, ou None se não houver dados suficientes no período."""
    datas, f = item["datas"], item["fechamento"]
    ini = next((i for i, d in enumerate(datas) if d >= corte), None)
    if ini is None or len(datas) - ini < 2:
        return None
    jd, jf = datas[ini:], f[ini:]
    preco = jf[-1]
    minimo, maximo = min(jf), max(jf)
    r = {
        "codigo": item["codigo"], "nome": item["nome"],
        "preco": preco, "data": jd[-1],
        "inicial": jf[0], "data_inicial": jd[0],
        "variacao": preco / jf[0] - 1,
        "minimo": minimo, "data_minimo": jd[jf.index(minimo)],
        "maximo": maximo, "data_maximo": jd[jf.index(maximo)],
        "abaixo_da_maxima": preco / maximo - 1,
        "var_5": f[-1] / f[-6] - 1 if len(f) >= 6 else None,
        "mm20": statistics.fmean(f[-20:]) if len(f) >= 20 else None,
        "mm50": statistics.fmean(f[-50:]) if len(f) >= 50 else None,
        "vol_anual": None, "oscilacao_dia": None,
    }
    retornos = [jf[i] / jf[i - 1] - 1 for i in range(1, len(jf))]
    if len(retornos) >= 5:
        dp = statistics.stdev(retornos)
        r["oscilacao_dia"], r["vol_anual"] = dp, dp * math.sqrt(252)
    return r


def _bloco(r):
    linhas = [
        f"ação: {r['codigo']} ({_limpo(r['nome'])})",
        f"  preço atual: {_reais(r['preco'])} em {_data(r['data'])}",
        f"  variação no período: {_pct(r['variacao'])} (de {_reais(r['inicial'])} em {_data(r['data_inicial'])})",
        f"  mínima do período: {_reais(r['minimo'])} em {_data(r['data_minimo'])}",
        f"  máxima do período: {_reais(r['maximo'])} em {_data(r['data_maximo'])}",
        f"  distância da máxima: o preço está {_numero(abs(r['abaixo_da_maxima']) * 100, 1)}% abaixo da máxima do período",
        "  variação nos últimos 5 pregões: " + (_pct(r["var_5"]) if r["var_5"] is not None else "sem dados suficientes"),
    ]
    if r["mm20"] is not None and r["mm50"] is not None:
        posicao = "ACIMA" if r["mm20"] > r["mm50"] else "ABAIXO" if r["mm20"] < r["mm50"] else "IGUAL"
        linhas.append(f"  tendência: média de 20 dias ({_reais(r['mm20'])}) {posicao} da média de 50 dias ({_reais(r['mm50'])})")
    else:
        linhas.append("  tendência: sem dados suficientes")
    if r["vol_anual"] is not None:
        linhas.append(f"  volatilidade: {_numero(r['vol_anual'] * 100, 1)}% ao ano (oscilação diária típica de {_numero(r['oscilacao_dia'] * 100, 1)}%)")
    else:
        linhas.append("  volatilidade: sem dados suficientes")
    return "\n".join(linhas)


def preparar_resumo(itens, codigos_sem_dados, periodo_id):
    """Devolve (bloco de texto, códigos sem dados, data inicial, data final). None se nada sobrou."""
    ultima = max(i["datas"][-1] for i in itens)
    corte = data_de_corte(periodo_id, ultima)
    resumos, sem_dados = [], list(codigos_sem_dados)
    for item in itens:
        r = resumir_acao(item, corte)
        if r is None:
            sem_dados.append(item["codigo"])
        else:
            resumos.append(r)
    if not resumos:
        return None
    blocos = [_bloco(r) for r in resumos]
    blocos += [f"ação: {_limpo(c, 10)} — sem dados" for c in sem_dados]
    return "\n\n".join(blocos), sem_dados, min(r["data_inicial"] for r in resumos), ultima


def montar_mensagem(nome, periodo_id, de, ate, bloco):
    rotulo = PERIODOS[periodo_id][0]
    hoje = datetime.now(BRASILIA).strftime("%d/%m/%Y")
    return (
        f"Data de hoje: {hoje}\n"
        f"Nome do usuário: {_limpo(nome)}\n"
        f"Período analisado: {rotulo} (de {_data(de)} a {_data(ate)})\n\n"
        f"<dados>\n{bloco}\n</dados>"
    )


# ---------- Mensagens amigáveis ----------
def mensagem_de_erro(erro, eh_admin):
    """Traduz erros da IA para o português, dizendo o que aconteceu e o que fazer. Nunca vaza detalhes técnicos."""
    status = getattr(erro, "status_code", None)
    texto = str(erro).lower()
    onde_admin = " No Railway: abra o serviço, aba Variables." if eh_admin else ""
    if isinstance(erro, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        return "A chave de acesso da IA está errada ou foi desativada. Peça ao administrador para conferir a chave (ANTHROPIC_API_KEY)." + onde_admin
    if status == 402 or (isinstance(erro, anthropic.BadRequestError) and "credit" in texto):
        return "O crédito da conta da IA acabou. Peça ao administrador para adicionar crédito em platform.claude.com, na área Billing (Cobrança)."
    if isinstance(erro, anthropic.NotFoundError):
        return "O modelo de IA configurado não está mais disponível. Avise o administrador para trocar o modelo (MODELO_IA)." + onde_admin
    if isinstance(erro, anthropic.RateLimitError):
        return "A IA está recebendo pedidos demais neste momento. Espere um minuto e clique de novo."
    if isinstance(erro, (anthropic.APIConnectionError, anthropic.APITimeoutError)):
        return "Não consegui falar com a IA agora. Verifique se o servidor está com internet e tente de novo em alguns minutos."
    if isinstance(erro, anthropic.InternalServerError) or (status or 0) >= 500:
        return "A IA está fora do ar ou sobrecarregada no momento. Tente de novo em alguns minutos."
    return "Não consegui gerar a análise agora. Tente de novo em alguns minutos; se continuar, avise o administrador."


def criar_cliente(chave):
    return anthropic.Anthropic(api_key=chave, timeout=60.0, max_retries=1)


def _ler_instrucoes():
    return ARQUIVO_INSTRUCOES.read_text(encoding="utf-8").strip()


# ---------- Cache e limite por hora ----------
def _chave_cache(nome, periodo_id, bloco):
    return hashlib.sha256(f"{nome}|{periodo_id}|{bloco}".encode("utf-8")).hexdigest()


def _pode_gerar(usuario_id, agora):
    """Registra a tentativa e diz se ainda está dentro do limite por hora."""
    with _trava:
        recentes = [t for t in _historico.get(usuario_id, []) if agora - t < 3600]
        if len(recentes) >= LIMITE_POR_HORA:
            _historico[usuario_id] = recentes
            return False
        recentes.append(agora)
        _historico[usuario_id] = recentes
        return True


def _guardar(chave, dados, agora):
    with _trava:
        for k in [k for k, v in _cache.items() if agora - v["quando"] >= VALIDADE_SEGUNDOS]:
            del _cache[k]
        if len(_cache) >= 300:
            del _cache[min(_cache, key=lambda k: _cache[k]["quando"])]
        _cache[chave] = dados


def _fatias(texto, tamanho=40):
    for i in range(0, len(texto), tamanho):
        yield texto[i:i + tamanho]


# ---------- Geração ----------
def gerar(usuario_id, nome, eh_admin, periodo_id, itens, codigos_sem_dados):
    """Gera eventos para o navegador: inicio, texto (vários), fim ou erro."""
    resumo = preparar_resumo(itens, codigos_sem_dados, periodo_id) if itens else None
    if resumo is None:
        yield {"tipo": "erro", "mensagem": "Não há dados suficientes das ações da sua carteira para analisar agora. Confira a página \"Minha carteira\" e tente de novo."}
        return
    bloco, _sem_dados, de, ate = resumo
    rotulo = PERIODOS[periodo_id][0]
    periodo = {"periodo": rotulo, "de": de, "ate": ate}
    agora = time.time()

    chave = _chave_cache(nome, periodo_id, bloco)
    with _trava:
        guardada = _cache.get(chave)
    if guardada and agora - guardada["quando"] < VALIDADE_SEGUNDOS:
        yield {"tipo": "inicio", **periodo, "gerada_em": int(guardada["quando"]), "em_cache": True}
        for fatia in _fatias(guardada["texto"]):
            yield {"tipo": "texto", "t": fatia}
        yield {"tipo": "fim"}
        return

    chave_api = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not chave_api:
        aonde = " (no Railway: aba Variables; no seu computador: arquivo .env)" if eh_admin else ""
        yield {"tipo": "erro", "mensagem": f"A Análise do Dia ainda não foi ativada: falta a chave de acesso da IA. Peça ao administrador para configurar a ANTHROPIC_API_KEY{aonde}."}
        return
    if not _pode_gerar(usuario_id, agora):
        yield {"tipo": "erro", "mensagem": f"Você já gerou {LIMITE_POR_HORA} análises novas na última hora. Espere um pouco e tente de novo; análises repetidas da mesma carteira e período não contam."}
        return

    modelo = os.environ.get("MODELO_IA") or MODELO_PADRAO
    texto = ""
    try:
        instrucoes = _ler_instrucoes()
        mensagem = montar_mensagem(nome, periodo_id, de, ate, bloco)
        cliente = criar_cliente(chave_api)
        yield {"tipo": "inicio", **periodo, "gerada_em": int(agora), "em_cache": False}
        with cliente.messages.stream(
            model=modelo, max_tokens=MAX_TOKENS_SAIDA, system=instrucoes,
            messages=[{"role": "user", "content": mensagem}],
        ) as fluxo:
            for pedaco in fluxo.text_stream:
                texto += pedaco
                yield {"tipo": "texto", "t": pedaco}
    except Exception as erro:  # noqa: BLE001 - qualquer falha vira mensagem amigável
        log.error("Falha na análise (%s, status %s)", type(erro).__name__, getattr(erro, "status_code", None))
        yield {"tipo": "erro", "mensagem": mensagem_de_erro(erro, eh_admin)}
        return
    if not texto.strip():
        yield {"tipo": "erro", "mensagem": "A IA não devolveu texto desta vez. Tente de novo em alguns minutos."}
        return
    _guardar(chave, {"texto": texto, "quando": agora}, agora)
    yield {"tipo": "fim"}
