"""Servidor do Painel de Ações: login, usuários, administração e carteira.

Para ligar o app:  python servidor.py   (ou dê dois cliques em iniciar.bat)
"""
import os
import re
import secrets
import sqlite3
import threading
import time
import webbrowser
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, g, jsonify, request, send_from_directory, session
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

import cotacoes

PASTA = Path(__file__).resolve().parent
CARTEIRA_INICIAL = ["PETR4", "ITUB4", "VALE3"]
MAX_ACOES = 8            # o gráfico tem 8 cores; mais que isso ficaria ilegível
TAMANHO_MIN_SENHA = 8
DURACAO_LOGIN = timedelta(hours=8)
TENTATIVAS_MAX = 5       # erros de senha seguidos antes de bloquear
BLOQUEIO_SEGUNDOS = 5 * 60

PADRAO_USUARIO = re.compile(r"^[a-z0-9._-]{3,30}$")
PADRAO_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Sem letras parecidas (0/O, 1/l/I) para a senha temporária ser fácil de ditar.
ALFABETO_SENHA = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"

# Rotas que quem ainda usa senha temporária pode acessar.
ROTAS_LIVRES_SENHA_TEMP = {"eu", "sair", "trocar_minha_senha"}

SQL_TABELAS = """
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    usuario TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL,
    senha_hash TEXT NOT NULL,
    admin INTEGER NOT NULL DEFAULT 0,
    trocar_senha INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS carteira (
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    codigo TEXT NOT NULL,
    posicao INTEGER NOT NULL,
    PRIMARY KEY (usuario_id, codigo)
);
"""


class ErroDeUso(Exception):
    """Erro com mensagem amigável, devolvido ao navegador em português."""

    def __init__(self, mensagem, status=400, codigo=None):
        super().__init__(mensagem)
        self.mensagem, self.status, self.codigo = mensagem, status, codigo


# ---------- Utilidades ----------
def gerar_senha_temporaria(tamanho=12):
    while True:
        senha = "".join(secrets.choice(ALFABETO_SENHA) for _ in range(tamanho))
        if any(c.isupper() for c in senha) and any(c.islower() for c in senha) and any(c.isdigit() for c in senha):
            return senha


def validar_senha_nova(senha):
    if not isinstance(senha, str) or len(senha) < TAMANHO_MIN_SENHA:
        raise ErroDeUso(f"A senha nova precisa ter pelo menos {TAMANHO_MIN_SENHA} caracteres.")
    if len(senha) > 128:
        raise ErroDeUso("A senha nova é longa demais (máximo de 128 caracteres).")


def texto(dados, campo):
    valor = dados.get(campo, "")
    return valor.strip() if isinstance(valor, str) else ""


def usuario_publico(linha, eu_id=None):
    return {
        "id": linha["id"],
        "nome": linha["nome"],
        "usuario": linha["usuario"],
        "email": linha["email"],
        "admin": bool(linha["admin"]),
        "trocar_senha": bool(linha["trocar_senha"]),
        "sou_eu": linha["id"] == eu_id,
    }


def criar_app(caminho_banco=None, admin_inicial=None):
    """Monta o app. Nos testes, passamos um banco temporário e o admin inicial."""
    load_dotenv(PASTA / ".env")
    app = Flask(__name__, static_folder=None)
    banco = Path(caminho_banco or os.environ.get("CAMINHO_BANCO") or PASTA / "dados.db")
    banco.parent.mkdir(parents=True, exist_ok=True)  # na internet o banco fica num disco (ex.: /data)
    app.config["CAMINHO_BANCO"] = banco
    # Na internet a chave vem das configurações do servidor (CHAVE_SECRETA); no seu computador, de um arquivo.
    app.config["SECRET_KEY"] = os.environ.get("CHAVE_SECRETA") or _chave_secreta(banco)
    if os.environ.get("CONFIAR_PROXY") == "1":
        # Atrás do Railway, o endereço real de quem acessa vem num cabeçalho do proxy dele.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    app.config.update(
        PERMANENT_SESSION_LIFETIME=DURACAO_LOGIN,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SEGURO") == "1",  # só com https
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_NAME="painel_sessao",
        MAX_CONTENT_LENGTH=64 * 1024,
    )
    falhas_login = {}          # (usuario, ip) -> horários dos erros recentes
    trava_login = threading.Lock()

    # ---------- Banco ----------
    def db():
        if "db" not in g:
            g.db = sqlite3.connect(banco)
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
        return g.db

    @app.teardown_appcontext
    def fechar_db(_erro):
        conexao = g.pop("db", None)
        if conexao:
            conexao.close()

    def iniciar_banco():
        conexao = sqlite3.connect(banco)
        conexao.row_factory = sqlite3.Row
        conexao.execute("PRAGMA foreign_keys = ON")
        conexao.executescript(SQL_TABELAS)
        if conexao.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 0:
            dados = admin_inicial or {
                "usuario": os.environ.get("ADMIN_USUARIO", ""),
                "senha": os.environ.get("ADMIN_SENHA", ""),
                "nome": os.environ.get("ADMIN_NOME", "Administrador"),
                "email": os.environ.get("ADMIN_EMAIL", ""),
            }
            usuario = (dados["usuario"] or "").strip().lower()
            if not PADRAO_USUARIO.match(usuario) or len(dados["senha"] or "") < TAMANHO_MIN_SENHA:
                conexao.close()
                raise SystemExit(
                    "\nNão existe nenhum usuário ainda e não consegui criar o primeiro administrador.\n"
                    "Confira ADMIN_USUARIO (3 a 30 letras/números) e ADMIN_SENHA "
                    f"(mínimo {TAMANHO_MIN_SENHA} caracteres). No seu computador, eles ficam no arquivo .env;\n"
                    "no Railway, na aba Variables do serviço. Depois ligue o app de novo.\n"
                )
            cursor = conexao.execute(
                "INSERT INTO usuarios (nome, usuario, email, senha_hash, admin, trocar_senha) VALUES (?,?,?,?,1,0)",
                (dados.get("nome") or "Administrador", usuario, dados.get("email") or "", generate_password_hash(dados["senha"])),
            )
            _carteira_inicial(conexao, cursor.lastrowid)
            conexao.commit()
            print(f"Primeiro administrador criado: {usuario}")
        conexao.commit()
        conexao.close()

    iniciar_banco()

    # ---------- Segurança em toda requisição ----------
    def usuario_logado():
        if "usuario_id" not in session:
            return None
        if not hasattr(g, "eu"):
            g.eu = db().execute("SELECT * FROM usuarios WHERE id = ?", (session["usuario_id"],)).fetchone()
            if g.eu is None:  # usuário foi excluído: derruba o login
                session.clear()
        return g.eu

    @app.before_request
    def proteger():
        if not request.path.startswith("/api/"):
            return None
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            enviado = request.headers.get("X-CSRF-Token", "")
            esperado = session.get("csrf", "")
            if not esperado or not secrets.compare_digest(enviado, esperado):
                raise ErroDeUso("Sua sessão expirou. Atualize a página (F5) e tente de novo.", 400, "csrf")
        endpoint = request.endpoint or ""
        if endpoint in ("eu", "entrar"):
            return None
        eu = usuario_logado()
        if eu is None:
            raise ErroDeUso("Você precisa entrar para continuar.", 401, "nao_logado")
        if eu["trocar_senha"] and endpoint not in ROTAS_LIVRES_SENHA_TEMP:
            raise ErroDeUso("Crie uma senha nova antes de usar o restante do app.", 403, "trocar_senha")
        if endpoint.startswith("admin_") and not eu["admin"]:
            raise ErroDeUso("Só administradores podem fazer isso.", 403, "sem_permissao")
        return None

    @app.after_request
    def cabecalhos(resposta):
        resposta.headers["X-Content-Type-Options"] = "nosniff"
        resposta.headers["X-Frame-Options"] = "DENY"
        resposta.headers["Referrer-Policy"] = "same-origin"
        resposta.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        )
        if request.path.startswith("/api/") or request.path == "/":
            resposta.headers["Cache-Control"] = "no-store"
        return resposta

    @app.errorhandler(ErroDeUso)
    def erro_de_uso(erro):
        return jsonify({"erro": erro.mensagem, "codigo": erro.codigo}), erro.status

    @app.errorhandler(404)
    def nao_encontrado(_erro):
        if request.path.startswith("/api/"):
            return jsonify({"erro": "Não encontrei o que você pediu."}), 404
        return "Página não encontrada. Volte para o início: http://localhost:5000", 404

    @app.errorhandler(413)
    def grande_demais(_erro):
        return jsonify({"erro": "Os dados enviados são grandes demais."}), 413

    @app.errorhandler(Exception)
    def erro_inesperado(erro):
        if hasattr(erro, "code") and isinstance(erro.code, int) and erro.code < 500:
            return jsonify({"erro": "Pedido inválido."}), erro.code
        app.logger.exception("Erro inesperado")
        return jsonify({"erro": "Algo deu errado por aqui. Tente de novo; se continuar, avise o administrador."}), 500

    def corpo():
        dados = request.get_json(silent=True)
        return dados if isinstance(dados, dict) else {}

    # ---------- Páginas ----------
    @app.get("/saude")
    def saude():
        """O Railway visita este endereço para saber se o app está de pé."""
        return "ok"

    @app.get("/")
    def pagina_inicial():
        return send_from_directory(PASTA / "static", "index.html")

    @app.get("/static/<path:arquivo>")
    def arquivos_estaticos(arquivo):
        return send_from_directory(PASTA / "static", arquivo)

    # ---------- Login ----------
    @app.get("/api/eu")
    def eu():
        linha = usuario_logado()  # antes do csrf: se o usuário foi excluído, a sessão é limpa aqui
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(24)
        if linha is None:
            return jsonify({"logado": False, "csrf": session.get("csrf")})
        session.permanent = True
        return jsonify({"logado": True, "csrf": session["csrf"], "usuario": usuario_publico(linha, linha["id"])})

    @app.post("/api/entrar")
    def entrar():
        dados = corpo()
        usuario = texto(dados, "usuario").lower()
        senha = dados.get("senha") if isinstance(dados.get("senha"), str) else ""
        chave = (usuario, request.remote_addr)
        agora = time.time()
        with trava_login:
            recentes = [t for t in falhas_login.get(chave, []) if agora - t < BLOQUEIO_SEGUNDOS]
            falhas_login[chave] = recentes
            if len(recentes) >= TENTATIVAS_MAX:
                minutos = int((BLOQUEIO_SEGUNDOS - (agora - recentes[0])) // 60) + 1
                raise ErroDeUso(f"Muitas tentativas erradas. Aguarde {minutos} minuto(s) e tente de novo.", 429)
        linha = db().execute("SELECT * FROM usuarios WHERE usuario = ?", (usuario,)).fetchone()
        # Sempre confere um hash, mesmo se o usuário não existir, para não revelar quem existe.
        hash_conferido = linha["senha_hash"] if linha else _HASH_FALSO
        if not (check_password_hash(hash_conferido, senha) and linha):
            with trava_login:
                falhas_login.setdefault(chave, []).append(agora)
            raise ErroDeUso("Usuário ou senha incorretos.", 401)
        with trava_login:
            falhas_login.pop(chave, None)
        session.clear()  # novo "crachá" a cada login
        session["usuario_id"] = linha["id"]
        session["csrf"] = secrets.token_urlsafe(24)
        session.permanent = True
        return jsonify({"csrf": session["csrf"], "usuario": usuario_publico(linha, linha["id"])})

    @app.post("/api/sair")
    def sair():
        csrf = session.get("csrf")
        session.clear()
        session["csrf"] = csrf or secrets.token_urlsafe(24)
        return jsonify({"ok": True, "csrf": session["csrf"]})

    @app.post("/api/minha-senha")
    def trocar_minha_senha():
        dados = corpo()
        eu_ = usuario_logado()
        atual = dados.get("atual") if isinstance(dados.get("atual"), str) else ""
        nova = dados.get("nova") if isinstance(dados.get("nova"), str) else ""
        if not check_password_hash(eu_["senha_hash"], atual):
            raise ErroDeUso("A senha atual está incorreta.")
        validar_senha_nova(nova)
        if nova == atual:
            raise ErroDeUso("A senha nova precisa ser diferente da atual.")
        db().execute("UPDATE usuarios SET senha_hash = ?, trocar_senha = 0 WHERE id = ?", (generate_password_hash(nova), eu_["id"]))
        db().commit()
        return jsonify({"ok": True})

    # ---------- Administração ----------
    def contar_admins():
        return db().execute("SELECT COUNT(*) FROM usuarios WHERE admin = 1").fetchone()[0]

    def buscar_usuario(usuario_id):
        linha = db().execute("SELECT * FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
        if linha is None:
            raise ErroDeUso("Esse usuário não existe (talvez já tenha sido excluído). Atualize a página.", 404)
        return linha

    @app.get("/api/admin/usuarios")
    def admin_listar():
        linhas = db().execute("SELECT * FROM usuarios ORDER BY admin DESC, nome COLLATE NOCASE").fetchall()
        return jsonify({"usuarios": [usuario_publico(l, usuario_logado()["id"]) for l in linhas]})

    @app.post("/api/admin/usuarios")
    def admin_criar():
        dados = corpo()
        nome, usuario, email = texto(dados, "nome"), texto(dados, "usuario").lower(), texto(dados, "email")
        if len(nome) < 2 or len(nome) > 100:
            raise ErroDeUso("Informe o nome completo da pessoa.")
        if not PADRAO_USUARIO.match(usuario):
            raise ErroDeUso("O nome de usuário deve ter de 3 a 30 caracteres: letras sem acento, números, ponto, traço ou sublinhado.")
        if not PADRAO_EMAIL.match(email) or len(email) > 150:
            raise ErroDeUso("Informe um e-mail válido, como nome@empresa.com.br.")
        if db().execute("SELECT 1 FROM usuarios WHERE usuario = ?", (usuario,)).fetchone():
            raise ErroDeUso("Já existe alguém com esse nome de usuário. Escolha outro.", 409)
        senha = gerar_senha_temporaria()
        cursor = db().execute(
            "INSERT INTO usuarios (nome, usuario, email, senha_hash, admin, trocar_senha) VALUES (?,?,?,?,0,1)",
            (nome, usuario, email, generate_password_hash(senha)),
        )
        _carteira_inicial(db(), cursor.lastrowid)
        db().commit()
        return jsonify({"usuario": usuario_publico(buscar_usuario(cursor.lastrowid)), "senha_temporaria": senha}), 201

    @app.post("/api/admin/usuarios/<int:usuario_id>/redefinir-senha")
    def admin_redefinir_senha(usuario_id):
        alvo = buscar_usuario(usuario_id)
        if alvo["id"] == usuario_logado()["id"]:
            raise ErroDeUso("Para trocar a sua própria senha, use a página \"Minha conta\".")
        senha = gerar_senha_temporaria()
        db().execute("UPDATE usuarios SET senha_hash = ?, trocar_senha = 1 WHERE id = ?", (generate_password_hash(senha), alvo["id"]))
        db().commit()
        return jsonify({"senha_temporaria": senha, "usuario": alvo["usuario"]})

    @app.post("/api/admin/usuarios/<int:usuario_id>/tipo")
    def admin_mudar_tipo(usuario_id):
        alvo = buscar_usuario(usuario_id)
        virar_admin = corpo().get("admin")
        if not isinstance(virar_admin, bool):
            raise ErroDeUso("Pedido inválido.")
        if not virar_admin and alvo["admin"] and contar_admins() <= 1:
            raise ErroDeUso("Não é possível rebaixar o último administrador: o app não pode ficar sem nenhum.")
        db().execute("UPDATE usuarios SET admin = ? WHERE id = ?", (int(virar_admin), alvo["id"]))
        db().commit()
        return jsonify({"usuario": usuario_publico(buscar_usuario(alvo["id"]), usuario_logado()["id"])})

    @app.delete("/api/admin/usuarios/<int:usuario_id>")
    def admin_excluir(usuario_id):
        alvo = buscar_usuario(usuario_id)
        if alvo["id"] == usuario_logado()["id"]:
            raise ErroDeUso("Você não pode excluir a si mesmo.")
        if alvo["admin"] and contar_admins() <= 1:
            raise ErroDeUso("Não é possível excluir o último administrador.")
        db().execute("DELETE FROM usuarios WHERE id = ?", (alvo["id"],))
        db().commit()
        return jsonify({"ok": True})

    # ---------- Carteira ----------
    def codigos_da_carteira():
        linhas = db().execute("SELECT codigo FROM carteira WHERE usuario_id = ? ORDER BY posicao", (usuario_logado()["id"],)).fetchall()
        return [l["codigo"] for l in linhas]

    @app.get("/api/carteira")
    def ver_carteira():
        return jsonify({"acoes": [{"codigo": c, "nome": cotacoes.nome_da_empresa(c)} for c in codigos_da_carteira()], "maximo": MAX_ACOES})

    @app.post("/api/carteira")
    def adicionar_acao():
        codigo = cotacoes.normalizar_codigo(corpo().get("codigo"))
        if codigo is None:
            raise ErroDeUso("Esse código não parece válido. Use 4 letras e 1 ou 2 números, como WEGE3 ou BBAS3.")
        atuais = codigos_da_carteira()
        if codigo in atuais:
            raise ErroDeUso(f"{codigo} já está na sua carteira.", 409)
        if len(atuais) >= MAX_ACOES:
            raise ErroDeUso(f"Sua carteira já tem {MAX_ACOES} ações, que é o máximo. Remova uma para adicionar outra.")
        try:
            cotacoes.obter(codigo)  # confirma que existe no Yahoo (e já deixa no cache)
        except cotacoes.ErroCotacao as erro:
            raise ErroDeUso(erro.mensagem, 404 if erro.tipo == "inexistente" else 503)
        db().execute("INSERT INTO carteira (usuario_id, codigo, posicao) VALUES (?,?,?)", (usuario_logado()["id"], codigo, len(atuais)))
        db().commit()
        return jsonify({"ok": True, "codigo": codigo}), 201

    @app.delete("/api/carteira/<codigo>")
    def remover_acao(codigo):
        codigo = cotacoes.normalizar_codigo(codigo)
        eu_id = usuario_logado()["id"]
        cursor = db().execute("DELETE FROM carteira WHERE usuario_id = ? AND codigo = ?", (eu_id, codigo or ""))
        if cursor.rowcount == 0:
            raise ErroDeUso("Essa ação não está na sua carteira.", 404)
        for posicao, c in enumerate(codigos_da_carteira()):
            db().execute("UPDATE carteira SET posicao = ? WHERE usuario_id = ? AND codigo = ?", (posicao, eu_id, c))
        db().commit()
        return jsonify({"ok": True})

    # ---------- Cotações ----------
    @app.get("/api/cotacoes")
    def ver_cotacoes():
        itens, erros = cotacoes.obter_varias(codigos_da_carteira())
        return jsonify({"itens": itens, "erros": erros})

    return app


_HASH_FALSO = generate_password_hash("senha-que-ninguem-usa")


def _carteira_inicial(conexao, usuario_id):
    for posicao, codigo in enumerate(CARTEIRA_INICIAL):
        conexao.execute("INSERT INTO carteira (usuario_id, codigo, posicao) VALUES (?,?,?)", (usuario_id, codigo, posicao))


def _chave_secreta(banco):
    """Chave que assina o 'crachá' do login. Fica num arquivo ao lado do banco, nunca no código."""
    arquivo = banco.with_suffix(".chave")
    if not arquivo.exists():
        arquivo.write_text(secrets.token_hex(32), encoding="utf-8")
    return arquivo.read_text(encoding="utf-8").strip()


if __name__ == "__main__":
    from waitress import serve

    # Na internet o Railway define a variável PORT e o app precisa aceitar conexões de fora (0.0.0.0).
    # No seu computador ele escuta só em 127.0.0.1, ou seja, só você acessa.
    na_nuvem = "PORT" in os.environ
    PORTA = int(os.environ.get("PORT") or os.environ.get("PORTA") or 5000)
    HOST = "0.0.0.0" if na_nuvem else "127.0.0.1"
    aplicacao = criar_app()
    if not na_nuvem and os.environ.get("ABRIR_NAVEGADOR", "1") == "1":
        threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{PORTA}")).start()
    print(f"\nPainel de Ações rodando na porta {PORTA}", flush=True)
    if not na_nuvem:
        print(f"Abra: http://localhost:{PORTA}")
        print("Para desligar: feche esta janela ou aperte Ctrl+C.\n")
    serve(aplicacao, host=HOST, port=PORTA, threads=8)
