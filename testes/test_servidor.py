"""Testes automáticos do servidor. Rodar:  python -m pytest testes -v

Os testes usam um banco temporário e cotações de mentira: não mexem nos seus dados
e não precisam de internet.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cotacoes  # noqa: E402
from servidor import criar_app  # noqa: E402

ADMIN = {"usuario": "chefe", "senha": "Senha-Do-Chefe-1", "nome": "Chefe Teste", "email": "chefe@teste.com"}


def yahoo_falso(codigo):
    if codigo == "ZZZZ9":
        raise cotacoes.ErroCotacao("inexistente", f"Não encontrei a ação {codigo} no Yahoo Finance. Confira se o código está certo.")
    if codigo == "FORA3":
        raise cotacoes.ErroCotacao("indisponivel", "Não consegui falar com o Yahoo Finance agora.")
    return ["2025-01-02", "2025-01-03"], [10.0, 11.0]


@pytest.fixture(autouse=True)
def sem_internet(monkeypatch):
    monkeypatch.setattr(cotacoes, "buscar_yahoo", yahoo_falso)
    cotacoes._cache.clear()


class Cliente:
    """Navegador de mentira que guarda cookies e envia o token de segurança."""

    def __init__(self, app):
        self.c = app.test_client()
        self.csrf = self.c.get("/api/eu").get_json()["csrf"]

    def _enviar(self, metodo, url, json=None):
        r = getattr(self.c, metodo)(url, json=json, headers={"X-CSRF-Token": self.csrf})
        return r

    def get(self, url):
        return self.c.get(url)

    def post(self, url, json=None):
        return self._enviar("post", url, json)

    def delete(self, url):
        return self._enviar("delete", url)

    def entrar(self, usuario, senha):
        r = self.post("/api/entrar", {"usuario": usuario, "senha": senha})
        if r.status_code == 200:
            self.csrf = r.get_json()["csrf"]
        return r


@pytest.fixture
def app(tmp_path):
    return criar_app(tmp_path / "teste.db", admin_inicial=ADMIN)


@pytest.fixture
def admin(app):
    c = Cliente(app)
    assert c.entrar("chefe", ADMIN["senha"]).status_code == 200
    return c


def criar_usuario(admin, usuario="ana", nome="Ana Souza", email="ana@teste.com"):
    r = admin.post("/api/admin/usuarios", {"nome": nome, "usuario": usuario, "email": email})
    assert r.status_code == 201, r.get_json()
    return r.get_json()


# ---------- Login ----------
def test_sem_login_nao_ve_nada(app):
    c = Cliente(app)
    for url in ["/api/carteira", "/api/cotacoes", "/api/admin/usuarios"]:
        r = c.get(url)
        assert r.status_code == 401
        assert "entrar" in r.get_json()["erro"]


def test_pagina_de_login_carrega_sem_login(app):
    assert app.test_client().get("/").status_code == 200


def test_login_certo_e_errado(app):
    c = Cliente(app)
    r = c.entrar("chefe", "senha-errada")
    assert r.status_code == 401 and r.get_json()["erro"] == "Usuário ou senha incorretos."
    r = c.entrar("naoexiste", "qualquer")
    assert r.get_json()["erro"] == "Usuário ou senha incorretos."  # mesma mensagem: não revela quem existe
    assert c.entrar("CHEFE", ADMIN["senha"]).status_code == 200    # maiúsculas não importam no usuário
    assert c.get("/api/eu").get_json()["logado"] is True


def test_login_persiste_e_sair_funciona(app):
    c = Cliente(app)
    c.entrar("chefe", ADMIN["senha"])
    # "F5": a mesma sessão continua logada
    assert c.get("/api/eu").get_json()["logado"] is True
    assert c.get("/api/carteira").status_code == 200
    # cookie é permanente (sobrevive a fechar o navegador)
    cookie = [h for h in c.c.get("/api/eu").headers.getlist("Set-Cookie")]
    assert any("Expires" in h or "Max-Age" in h for h in cookie)
    assert c.post("/api/sair").status_code == 200
    assert c.get("/api/eu").get_json()["logado"] is False
    assert c.get("/api/carteira").status_code == 401


def test_bloqueio_apos_muitas_tentativas(app):
    c = Cliente(app)
    for _ in range(5):
        assert c.entrar("chefe", "errada").status_code == 401
    r = c.entrar("chefe", ADMIN["senha"])  # até a senha certa fica bloqueada por um tempo
    assert r.status_code == 429


def test_post_sem_token_csrf_e_recusado(app):
    r = app.test_client().post("/api/entrar", json={"usuario": "chefe", "senha": ADMIN["senha"]})
    assert r.status_code == 400


def test_senha_nao_fica_em_texto_legivel(app, tmp_path):
    Cliente(app)
    conteudo = (tmp_path / "teste.db").read_bytes()
    assert ADMIN["senha"].encode() not in conteudo


def test_primeiro_admin_criado_e_nao_duplica(tmp_path):
    caminho = tmp_path / "x.db"
    criar_app(caminho, admin_inicial=ADMIN)
    app2 = criar_app(caminho, admin_inicial={**ADMIN, "usuario": "outro"})  # segunda vez: não cria de novo
    c = Cliente(app2)
    assert c.entrar("outro", ADMIN["senha"]).status_code == 401
    assert c.entrar("chefe", ADMIN["senha"]).status_code == 200


def test_sem_dados_do_admin_o_app_explica(tmp_path, monkeypatch):
    monkeypatch.delenv("ADMIN_USUARIO", raising=False)
    monkeypatch.delenv("ADMIN_SENHA", raising=False)
    monkeypatch.setattr("servidor.load_dotenv", lambda *a, **k: None)
    with pytest.raises(SystemExit) as erro:
        criar_app(tmp_path / "y.db")
    assert ".env" in str(erro.value)


# ---------- Administração ----------
def test_usuario_comum_nao_acessa_admin(admin, app):
    dados = criar_usuario(admin)
    comum = Cliente(app)
    comum.entrar("ana", dados["senha_temporaria"])
    # ainda com senha temporária: bloqueado por isso; troca a senha e testa de novo
    comum.post("/api/minha-senha", {"atual": dados["senha_temporaria"], "nova": "NovaSenha123"})
    r = comum.get("/api/admin/usuarios")
    assert r.status_code == 403
    assert comum.post("/api/admin/usuarios", {"nome": "X Y", "usuario": "xy", "email": "a@b.co"}).status_code == 403


def test_criar_usuario_e_lista(admin):
    dados = criar_usuario(admin)
    assert len(dados["senha_temporaria"]) >= 8
    lista = admin.get("/api/admin/usuarios").get_json()["usuarios"]
    ana = next(u for u in lista if u["usuario"] == "ana")
    assert ana == {"id": ana["id"], "nome": "Ana Souza", "usuario": "ana", "email": "ana@teste.com", "admin": False, "trocar_senha": True, "sou_eu": False}
    assert "senha" not in str(lista).lower().replace("trocar_senha", "")


def test_criar_usuario_valida_campos(admin):
    criar_usuario(admin)
    assert admin.post("/api/admin/usuarios", {"nome": "Outra Ana", "usuario": "ana", "email": "o@t.com"}).status_code == 409
    assert admin.post("/api/admin/usuarios", {"nome": "", "usuario": "bia", "email": "b@t.com"}).status_code == 400
    assert admin.post("/api/admin/usuarios", {"nome": "Bia Lima", "usuario": "b ia!", "email": "b@t.com"}).status_code == 400
    assert admin.post("/api/admin/usuarios", {"nome": "Bia Lima", "usuario": "bia", "email": "nao-e-email"}).status_code == 400


def test_senha_temporaria_obriga_trocar(admin, app):
    dados = criar_usuario(admin)
    c = Cliente(app)
    assert c.entrar("ana", dados["senha_temporaria"]).status_code == 200
    assert c.get("/api/eu").get_json()["usuario"]["trocar_senha"] is True
    for url in ["/api/carteira", "/api/cotacoes"]:
        r = c.get(url)
        assert r.status_code == 403 and r.get_json()["codigo"] == "trocar_senha"
    # regras da senha nova
    assert c.post("/api/minha-senha", {"atual": "errada", "nova": "NovaSenha123"}).status_code == 400
    assert c.post("/api/minha-senha", {"atual": dados["senha_temporaria"], "nova": "curta"}).status_code == 400
    assert c.post("/api/minha-senha", {"atual": dados["senha_temporaria"], "nova": dados["senha_temporaria"]}).status_code == 400
    assert c.post("/api/minha-senha", {"atual": dados["senha_temporaria"], "nova": "NovaSenha123"}).status_code == 200
    assert c.get("/api/carteira").status_code == 200
    # senha antiga não funciona mais; a nova sim
    c2 = Cliente(app)
    assert c2.entrar("ana", dados["senha_temporaria"]).status_code == 401
    assert c2.entrar("ana", "NovaSenha123").status_code == 200


def test_troca_voluntaria_de_senha(admin):
    assert admin.post("/api/minha-senha", {"atual": ADMIN["senha"], "nova": "OutraSenha456"}).status_code == 200
    assert admin.get("/api/carteira").status_code == 200


def test_redefinir_senha(admin, app):
    dados = criar_usuario(admin)
    c = Cliente(app)
    c.entrar("ana", dados["senha_temporaria"])
    c.post("/api/minha-senha", {"atual": dados["senha_temporaria"], "nova": "NovaSenha123"})
    nova = admin.post(f"/api/admin/usuarios/{dados['usuario']['id']}/redefinir-senha").get_json()["senha_temporaria"]
    c2 = Cliente(app)
    assert c2.entrar("ana", "NovaSenha123").status_code == 401
    assert c2.entrar("ana", nova).status_code == 200
    assert c2.get("/api/carteira").status_code == 403  # voltou a ter que trocar
    # o admin não redefine a própria senha por aqui
    meu_id = next(u["id"] for u in admin.get("/api/admin/usuarios").get_json()["usuarios"] if u["sou_eu"])
    assert admin.post(f"/api/admin/usuarios/{meu_id}/redefinir-senha").status_code == 400


def test_promover_e_rebaixar(admin):
    ana = criar_usuario(admin)["usuario"]["id"]
    r = admin.post(f"/api/admin/usuarios/{ana}/tipo", {"admin": True})
    assert r.get_json()["usuario"]["admin"] is True
    r = admin.post(f"/api/admin/usuarios/{ana}/tipo", {"admin": False})
    assert r.get_json()["usuario"]["admin"] is False


def test_nao_rebaixa_ultimo_administrador(admin):
    meu_id = next(u["id"] for u in admin.get("/api/admin/usuarios").get_json()["usuarios"] if u["sou_eu"])
    r = admin.post(f"/api/admin/usuarios/{meu_id}/tipo", {"admin": False})
    assert r.status_code == 400 and "último administrador" in r.get_json()["erro"]
    # com um segundo admin, aí pode
    ana = criar_usuario(admin)["usuario"]["id"]
    admin.post(f"/api/admin/usuarios/{ana}/tipo", {"admin": True})
    assert admin.post(f"/api/admin/usuarios/{meu_id}/tipo", {"admin": False}).status_code == 200


def test_nao_exclui_a_si_mesmo(admin):
    meu_id = next(u["id"] for u in admin.get("/api/admin/usuarios").get_json()["usuarios"] if u["sou_eu"])
    r = admin.delete(f"/api/admin/usuarios/{meu_id}")
    assert r.status_code == 400 and "a si mesmo" in r.get_json()["erro"]


def test_excluir_usuario_derruba_login_e_apaga_carteira(admin, app):
    dados = criar_usuario(admin)
    c = Cliente(app)
    c.entrar("ana", dados["senha_temporaria"])
    assert admin.delete(f"/api/admin/usuarios/{dados['usuario']['id']}").status_code == 200
    assert c.get("/api/eu").get_json()["logado"] is False
    assert Cliente(app).entrar("ana", dados["senha_temporaria"]).status_code == 401
    assert admin.delete(f"/api/admin/usuarios/{dados['usuario']['id']}").status_code == 404


# ---------- Carteira ----------
def codigos(c):
    return [a["codigo"] for a in c.get("/api/carteira").get_json()["acoes"]]


def test_carteira_comeca_com_tres_acoes(admin):
    assert codigos(admin) == ["PETR4", "ITUB4", "VALE3"]


def test_adicionar_e_remover(admin):
    assert admin.post("/api/carteira", {"codigo": " wege3 "}).status_code == 201
    assert codigos(admin) == ["PETR4", "ITUB4", "VALE3", "WEGE3"]
    assert admin.delete("/api/carteira/PETR4").status_code == 200
    assert codigos(admin) == ["ITUB4", "VALE3", "WEGE3"]
    assert admin.delete("/api/carteira/PETR4").status_code == 404


def test_adicionar_erros_amigaveis(admin):
    r = admin.post("/api/carteira", {"codigo": "ZZZZ9"})
    assert r.status_code == 404 and "Não encontrei" in r.get_json()["erro"]
    r = admin.post("/api/carteira", {"codigo": "FORA3"})
    assert r.status_code == 503 and "Yahoo" in r.get_json()["erro"]
    assert admin.post("/api/carteira", {"codigo": "??"}).status_code == 400
    assert admin.post("/api/carteira", {"codigo": "PETR4"}).status_code == 409
    assert codigos(admin) == ["PETR4", "ITUB4", "VALE3"]


def test_limite_de_acoes(admin):
    for c in ["WEGE3", "BBAS3", "ABEV3", "RENT3", "SUZB3"]:
        assert admin.post("/api/carteira", {"codigo": c}).status_code == 201
    assert admin.post("/api/carteira", {"codigo": "B3SA3"}).status_code == 400


def test_carteiras_sao_separadas_e_ficam_salvas(admin, app):
    dados = criar_usuario(admin)
    admin.post("/api/carteira", {"codigo": "WEGE3"})
    ana = Cliente(app)
    ana.entrar("ana", dados["senha_temporaria"])
    ana.post("/api/minha-senha", {"atual": dados["senha_temporaria"], "nova": "NovaSenha123"})
    assert codigos(ana) == ["PETR4", "ITUB4", "VALE3"]
    ana.delete("/api/carteira/ITUB4")
    # sai, entra de novo e de "outro navegador": continua como deixou
    ana2 = Cliente(app)
    ana2.entrar("ana", "NovaSenha123")
    assert codigos(ana2) == ["PETR4", "VALE3"]
    assert "WEGE3" in codigos(admin)


def test_dados_persistem_ao_reiniciar(tmp_path):
    caminho = tmp_path / "p.db"
    app1 = criar_app(caminho, admin_inicial=ADMIN)
    c = Cliente(app1)
    c.entrar("chefe", ADMIN["senha"])
    criar_usuario(c)
    c.post("/api/carteira", {"codigo": "WEGE3"})
    app2 = criar_app(caminho, admin_inicial=ADMIN)   # "fechou e abriu o app"
    c2 = Cliente(app2)
    c2.entrar("chefe", ADMIN["senha"])
    assert "ana" in [u["usuario"] for u in c2.get("/api/admin/usuarios").get_json()["usuarios"]]
    assert "WEGE3" in codigos(c2)
    # e o login anterior continua valendo (a chave de assinatura também foi guardada)
    assert c.get("/api/eu").get_json()["logado"] is True


# ---------- Publicação na internet ----------
def test_saude_responde_sem_login(app):
    r = app.test_client().get("/saude")
    assert r.status_code == 200 and r.get_data(as_text=True) == "ok"


def test_chave_secreta_vem_da_variavel_e_nao_de_arquivo(tmp_path, monkeypatch):
    monkeypatch.setenv("CHAVE_SECRETA", "chave-de-teste-123")
    app = criar_app(tmp_path / "n.db", admin_inicial=ADMIN)
    assert app.config["SECRET_KEY"] == "chave-de-teste-123"
    assert not (tmp_path / "n.chave").exists()


def test_cria_a_pasta_do_banco_se_nao_existir(tmp_path):
    criar_app(tmp_path / "disco" / "novo" / "d.db", admin_inicial=ADMIN)
    assert (tmp_path / "disco" / "novo" / "d.db").exists()


def test_cookie_so_por_https_quando_configurado(tmp_path, monkeypatch):
    monkeypatch.setenv("COOKIE_SEGURO", "1")
    app = criar_app(tmp_path / "s.db", admin_inicial=ADMIN)
    cookie = app.test_client().get("/api/eu").headers.get("Set-Cookie", "")
    assert "Secure" in cookie and "HttpOnly" in cookie


def test_bloqueio_usa_o_ip_real_atras_do_proxy(tmp_path, monkeypatch):
    monkeypatch.setenv("CONFIAR_PROXY", "1")
    app = criar_app(tmp_path / "p.db", admin_inicial=ADMIN)
    a, b = Cliente(app), Cliente(app)
    for _ in range(5):
        a.c.post("/api/entrar", json={"usuario": "chefe", "senha": "x"}, headers={"X-CSRF-Token": a.csrf, "X-Forwarded-For": "1.1.1.1"})
    r = a.c.post("/api/entrar", json={"usuario": "chefe", "senha": ADMIN["senha"]}, headers={"X-CSRF-Token": a.csrf, "X-Forwarded-For": "1.1.1.1"})
    assert r.status_code == 429                         # o atacante (1.1.1.1) ficou bloqueado...
    r = b.c.post("/api/entrar", json={"usuario": "chefe", "senha": ADMIN["senha"]}, headers={"X-CSRF-Token": b.csrf, "X-Forwarded-For": "2.2.2.2"})
    assert r.status_code == 200                         # ...mas o dono, de outro IP, entra normalmente


# ---------- Cotações ----------
def test_cotacoes_devolve_dados_e_erros_sem_quebrar(admin):
    admin.post("/api/carteira", {"codigo": "WEGE3"})
    dados = admin.get("/api/cotacoes").get_json()
    assert [i["codigo"] for i in dados["itens"]] == ["PETR4", "ITUB4", "VALE3", "WEGE3"]
    assert dados["itens"][0]["fechamento"] == [10.0, 11.0] and dados["erros"] == []


def test_cotacoes_com_yahoo_fora_mostra_mensagem(admin, monkeypatch):
    def fora(_codigo):
        raise cotacoes.ErroCotacao("indisponivel", "Não consegui falar com o Yahoo Finance agora.")
    monkeypatch.setattr(cotacoes, "buscar_yahoo", fora)
    r = admin.get("/api/cotacoes")
    assert r.status_code == 200
    dados = r.get_json()
    assert dados["itens"] == [] and len(dados["erros"]) == 3 and "Yahoo" in dados["erros"][0]["mensagem"]


def test_cache_de_15_minutos(admin, monkeypatch):
    chamadas = []

    def contando(codigo):
        chamadas.append(codigo)
        return yahoo_falso(codigo)
    monkeypatch.setattr(cotacoes, "buscar_yahoo", contando)
    admin.get("/api/cotacoes")
    admin.get("/api/cotacoes")
    assert len(chamadas) == 3                      # 3 ações, buscadas uma vez só
    for item in cotacoes._cache.values():          # "passam-se 16 minutos"
        item["quando"] -= 16 * 60
    admin.get("/api/cotacoes")
    assert len(chamadas) == 6


def test_dados_antigos_servem_quando_yahoo_cai(admin, monkeypatch):
    admin.get("/api/cotacoes")
    for item in cotacoes._cache.values():
        item["quando"] -= 16 * 60

    def fora(_codigo):
        raise cotacoes.ErroCotacao("indisponivel", "fora")
    monkeypatch.setattr(cotacoes, "buscar_yahoo", fora)
    dados = admin.get("/api/cotacoes").get_json()
    assert len(dados["itens"]) == 3 and dados["itens"][0]["desatualizado"] is True


def test_erro_inesperado_nao_mostra_tela_tecnica(admin, monkeypatch):
    def quebra(_codigos):
        raise RuntimeError("segredo interno")
    monkeypatch.setattr(cotacoes, "obter_varias", quebra)
    r = admin.get("/api/cotacoes")
    assert r.status_code == 500
    assert "segredo interno" not in r.get_data(as_text=True)
    assert "Algo deu errado" in r.get_json()["erro"]


def test_normalizar_codigo():
    assert cotacoes.normalizar_codigo("wege3.sa") == "WEGE3"
    assert cotacoes.normalizar_codigo("BOVA11") == "BOVA11"
    assert cotacoes.normalizar_codigo("PETR") is None
    assert cotacoes.normalizar_codigo("../etc") is None
    assert cotacoes.normalizar_codigo(None) is None
