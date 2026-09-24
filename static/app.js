// Painel de Ações: conversa com o servidor, controla login, menu e as páginas.
// As funções de formatação (el, reais, etc.) e a página "Ações" estão no acoes.js.

let csrf = "";          // token de segurança enviado em toda ação que altera dados
let eu = null;          // dados de quem está logado
let limparPagina = null; // limpeza da página aberta (para timers e gráficos)

const $ = (id) => document.getElementById(id);

// ---------- Conversa com o servidor ----------
async function api(metodo, url, corpo) {
  let resposta;
  try {
    resposta = await fetch(url, {
      method: metodo,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
      body: corpo === undefined ? undefined : JSON.stringify(corpo),
    });
  } catch {
    throw new Error("Não consegui falar com o servidor. Confira se a janela preta do app continua aberta e tente de novo.");
  }
  let dados = {};
  try { dados = await resposta.json(); } catch { /* resposta sem conteúdo */ }
  if (!resposta.ok) await reagirAoErro(resposta, dados);
  if (dados.csrf) csrf = dados.csrf;
  return dados;
}

// Erros de sessão, segurança e senha temporária são tratados igual em todas as chamadas.
async function reagirAoErro(resposta, dados) {
  if (dados.codigo === "nao_logado" && eu) {
    eu = null;
    mostrarLogin("Sua sessão terminou. Entre de novo.");
  } else if (dados.codigo === "csrf") {
    try { csrf = (await (await fetch("/api/eu", { credentials: "same-origin" })).json()).csrf; } catch { /* segue */ }
  } else if (dados.codigo === "trocar_senha" && eu && !eu.trocar_senha) {
    eu.trocar_senha = true;
    ir();
  }
  throw new Error(dados.erro || "Algo deu errado. Tente de novo.");
}

// Como api(), mas a resposta chega aos poucos (uma linha JSON por evento): usado na Análise do Dia.
async function apiFluxo(url, corpo, aoEvento, sinal) {
  let resposta;
  try {
    resposta = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      signal: sinal,
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
      body: JSON.stringify(corpo),
    });
  } catch (erro) {
    if (erro.name === "AbortError") throw erro;
    throw new Error("Não consegui falar com o servidor. Confira sua internet e tente de novo.");
  }
  if (!resposta.ok) {
    let dados = {};
    try { dados = await resposta.json(); } catch { /* sem conteúdo */ }
    await reagirAoErro(resposta, dados);
  }
  const leitor = resposta.body.getReader();
  const decodificador = new TextDecoder();
  let resto = "";
  for (;;) {
    const { done, value } = await leitor.read();
    if (done) break;
    resto += decodificador.decode(value, { stream: true });
    const linhas = resto.split("\n");
    resto = linhas.pop();
    for (const linha of linhas) if (linha.trim()) aoEvento(JSON.parse(linha));
  }
  if (resto.trim()) aoEvento(JSON.parse(resto));
}

const mensagem = (caixa, texto, tipo = "erro") => {
  caixa.className = tipo;
  caixa.textContent = texto;
  caixa.hidden = !texto;
};

// Desativa o botão enquanto a ação roda, para não clicar duas vezes.
async function comBotao(botao, textoEnquanto, funcao) {
  const original = botao.textContent;
  botao.disabled = true;
  if (textoEnquanto) botao.textContent = textoEnquanto;
  try { return await funcao(); } finally { botao.disabled = false; botao.textContent = original; }
}

// ---------- Telas: carregando, entrada e app ----------
function mostrarTela(nome) {
  for (const id of ["tela-carregando", "tela-login", "tela-app"]) $(id).hidden = id !== nome;
}

function mostrarLogin(aviso) {
  if (limparPagina) { limparPagina(); limparPagina = null; }
  $("conteudo").replaceChildren();
  mostrarTela("tela-login");
  $("login-senha").value = "";
  mensagem($("login-erro"), aviso || "");
  document.title = "Entrar · Painel de Ações";
  $("login-usuario").focus();
}

function mostrarApp() {
  $("nome-usuario").textContent = eu.nome;
  $("tipo-usuario").textContent = eu.admin ? "Administrador" : "Usuário";
  $("menu-admin").hidden = !eu.admin;
  mostrarTela("tela-app");
  ir();
}

$("form-login").addEventListener("submit", async (e) => {
  e.preventDefault();
  const botao = e.submitter || e.target.querySelector("button");
  mensagem($("login-erro"), "");
  try {
    const r = await comBotao(botao, "Entrando…", () => api("POST", "/api/entrar", { usuario: $("login-usuario").value, senha: $("login-senha").value }));
    eu = r.usuario;
    $("login-senha").value = "";
    location.hash = "";
    mostrarApp();
  } catch (erro) {
    mensagem($("login-erro"), erro.message);
    $("login-senha").select();
  }
});

$("botao-sair").addEventListener("click", async () => {
  try { await api("POST", "/api/sair"); } catch { /* mesmo com erro, volta para a entrada */ }
  eu = null;
  location.hash = "";
  mostrarLogin();
});

// ---------- Roteamento pelas páginas do menu ----------
const PAGINAS = {
  acoes: { titulo: "Ações", desenhar: (raiz) => paginaAcoes(raiz, api, apiFluxo) },
  carteira: { titulo: "Minha carteira", desenhar: paginaCarteira },
  conta: { titulo: "Minha conta", desenhar: paginaConta },
  admin: { titulo: "Administração", desenhar: paginaAdmin, soAdmin: true },
};

function ir() {
  if (!eu) return;
  let nome = location.hash.replace(/^#\//, "");
  if (!PAGINAS[nome] || (PAGINAS[nome].soAdmin && !eu.admin)) nome = "acoes";
  if (eu.trocar_senha) nome = "conta"; // senha temporária: só a página "Minha conta"
  const alvo = "#/" + nome;
  if (location.hash !== alvo) { location.hash = alvo; return; } // dispara "hashchange" e volta aqui

  document.querySelectorAll("#menu a").forEach((a) => {
    a.classList.toggle("ativo", a.dataset.pagina === nome);
    a.classList.toggle("bloqueado", eu.trocar_senha && a.dataset.pagina !== "conta");
    if (a.dataset.pagina === nome) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
  document.title = `${PAGINAS[nome].titulo} · Painel de Ações`;
  if (limparPagina) limparPagina();
  const raiz = $("conteudo");
  raiz.replaceChildren();
  limparPagina = PAGINAS[nome].desenhar(raiz) || null;
  window.scrollTo(0, 0);
}
window.addEventListener("hashchange", ir);

// ---------- Janela da senha temporária ----------
function mostrarSenhaTemporaria(texto, senha) {
  $("dialogo-texto").textContent = texto;
  $("dialogo-codigo").textContent = senha;
  $("dialogo-copiar").textContent = "Copiar";
  $("dialogo-senha").showModal();
}
$("dialogo-copiar").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText($("dialogo-codigo").textContent);
    $("dialogo-copiar").textContent = "Copiado!";
  } catch {
    const faixa = document.createRange();
    faixa.selectNodeContents($("dialogo-codigo"));
    getSelection().removeAllRanges();
    getSelection().addRange(faixa);
    $("dialogo-copiar").textContent = "Selecionada: aperte Ctrl+C";
  }
});
$("dialogo-fechar").addEventListener("click", () => { $("dialogo-codigo").textContent = ""; $("dialogo-senha").close(); });
$("dialogo-senha").addEventListener("cancel", (e) => e.preventDefault()); // Esc não fecha: evita perder a senha sem querer

// ---------- Página: Minha carteira ----------
function paginaCarteira(raiz) {
  let acoes = [];
  let maximo = 8;
  let precos = new Map();
  let cancelado = false;

  const titulos = el("div");
  titulos.append(el("h1", "", "Minha carteira"), el("p", "sub", "As ações que você acompanha. A lista fica salva e é só sua."));

  const form = el("form", "painel");
  form.innerHTML = `<h2>Adicionar ação</h2>
    <div class="linha-form" style="margin-top:10px">
      <label>Código da ação
        <input id="novo-codigo" placeholder="Ex.: WEGE3 ou BBAS3" maxlength="10" autocomplete="off" autocapitalize="characters" spellcheck="false" required>
      </label>
      <button class="botao primario" type="submit">Adicionar</button>
    </div>`;
  const aviso = el("p", "erro");
  aviso.hidden = true;
  aviso.style.marginTop = "12px";
  form.append(aviso);

  const painelLista = el("section", "painel");
  const contagem = el("h2");
  const rolagem = el("div", "rolagem");
  const tabela = el("table", "lista");
  tabela.innerHTML = "<thead><tr><th>Código</th><th>Empresa</th><th>Último preço</th><th>Variação no dia</th><th></th></tr></thead><tbody></tbody>";
  rolagem.append(tabela);
  painelLista.append(contagem, rolagem);
  raiz.append(titulos, form, painelLista);

  function desenharLista() {
    contagem.textContent = `Suas ações (${acoes.length} de ${maximo})`;
    const corpo = tabela.querySelector("tbody");
    corpo.replaceChildren();
    if (!acoes.length) {
      const tr = el("tr");
      const td = el("td", "", "Sua carteira está vazia. Adicione uma ação acima.");
      td.colSpan = 5;
      tr.append(td);
      corpo.append(tr);
    }
    for (const a of acoes) {
      const p = precos.get(a.codigo);
      const tr = el("tr");
      const variacao = el("td", p && p.dia != null ? (p.dia >= 0 ? "alta" : "queda") : "", p ? (p.dia == null ? "—" : `${p.dia >= 0 ? "▲" : "▼"} ${porcento(p.dia)}`) : "…");
      const botao = el("button", "botao pequeno perigo", "Remover");
      botao.type = "button";
      botao.addEventListener("click", () => remover(a, botao));
      const celulaBotao = el("td", "celula-acoes");
      celulaBotao.append(botao);
      tr.append(el("td", "", a.codigo), el("td", "", a.nome), el("td", "", p ? (p.preco == null ? "indisponível" : reais(p.preco)) : "…"), variacao, celulaBotao);
      corpo.append(tr);
    }
  }

  async function carregarPrecos() {
    try {
      const r = await api("GET", "/api/cotacoes");
      if (cancelado) return;
      precos = new Map(r.itens.map((i) => {
        const f = i.fechamento;
        return [i.codigo, { preco: f[f.length - 1], dia: f.length > 1 ? f[f.length - 1] / f[f.length - 2] - 1 : null }];
      }));
      const semDado = r.erros.map((e) => e.codigo);
      if (semDado.length) mensagem(aviso, `Não consegui buscar o preço de ${semDado.join(", ")} agora. ${r.erros[0].mensagem}`);
      for (const a of acoes) if (!precos.has(a.codigo)) precos.set(a.codigo, { preco: null, dia: null });
      desenharLista();
    } catch (erro) {
      if (!cancelado) mensagem(aviso, erro.message);
    }
  }

  async function remover(acao, botao) {
    if (!confirm(`Remover ${acao.codigo} da sua carteira?`)) return;
    try {
      await comBotao(botao, "Removendo…", () => api("DELETE", `/api/carteira/${encodeURIComponent(acao.codigo)}`));
      acoes = acoes.filter((a) => a.codigo !== acao.codigo);
      mensagem(aviso, "");
      desenharLista();
    } catch (erro) {
      mensagem(aviso, erro.message);
    }
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const campo = $("novo-codigo");
    const botao = form.querySelector("button");
    mensagem(aviso, "");
    try {
      await comBotao(botao, "Verificando no Yahoo…", () => api("POST", "/api/carteira", { codigo: campo.value }));
      const r = await api("GET", "/api/carteira");
      acoes = r.acoes;
      campo.value = "";
      mensagem(aviso, "Ação adicionada!", "ok");
      desenharLista();
      carregarPrecos();
    } catch (erro) {
      mensagem(aviso, erro.message);
    }
  });

  (async () => {
    try {
      const r = await api("GET", "/api/carteira");
      if (cancelado) return;
      acoes = r.acoes;
      maximo = r.maximo;
      desenharLista();
      carregarPrecos();
    } catch (erro) {
      mensagem(aviso, erro.message);
    }
  })();

  return () => { cancelado = true; };
}

// ---------- Página: Minha conta ----------
function paginaConta(raiz) {
  const titulos = el("div");
  titulos.append(el("h1", "", "Minha conta"), el("p", "sub", "Seus dados e a troca de senha."));
  raiz.append(titulos);

  if (eu.trocar_senha) {
    raiz.append(el("p", "aviso", "Você entrou com uma senha temporária. Crie uma senha nova abaixo para poder usar o restante do app."));
  }

  const dados = el("section", "painel");
  dados.append(el("h2", "", "Seus dados"));
  const lista = el("dl", "dados");
  for (const [nome, valor] of [["Nome", eu.nome], ["Usuário", eu.usuario], ["E-mail", eu.email], ["Tipo", eu.admin ? "Administrador" : "Usuário comum"]]) {
    lista.append(el("dt", "", nome), el("dd", "", valor));
  }
  dados.append(lista);

  const form = el("form", "painel");
  form.innerHTML = `<h2>Trocar senha</h2>
    <div class="form-coluna" style="margin-top:12px">
      <label>Senha atual <input id="senha-atual" type="password" autocomplete="current-password" required></label>
      <label>Senha nova (mínimo de 8 caracteres) <input id="senha-nova" type="password" autocomplete="new-password" minlength="8" required></label>
      <label>Repita a senha nova <input id="senha-nova2" type="password" autocomplete="new-password" minlength="8" required></label>
      <p id="conta-msg" hidden></p>
      <button class="botao primario" type="submit">Salvar senha nova</button>
    </div>`;
  raiz.append(dados, form);
  form.style.marginTop = "20px";

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const msg = form.querySelector("#conta-msg");
    mensagem(msg, "");
    if ($("senha-nova").value !== $("senha-nova2").value) return mensagem(msg, "As duas senhas novas não são iguais. Digite de novo.");
    const foiTemporaria = eu.trocar_senha;
    try {
      await comBotao(form.querySelector("button"), "Salvando…", () => api("POST", "/api/minha-senha", { atual: $("senha-atual").value, nova: $("senha-nova").value }));
      eu.trocar_senha = false;
      form.reset();
      if (foiTemporaria) { location.hash = "#/acoes"; ir(); return; }
      mensagem(msg, "Senha alterada com sucesso!", "ok");
    } catch (erro) {
      mensagem(msg, erro.message);
    }
  });
}

// ---------- Página: Administração ----------
function paginaAdmin(raiz) {
  let usuarios = [];
  let cancelado = false;

  const cab = el("div", "cabecalho-pagina");
  const titulos = el("div");
  titulos.append(el("h1", "", "Administração"), el("p", "sub", "Crie usuários, redefina senhas e defina quem é administrador."));
  const botaoNovo = el("button", "botao primario", "Novo usuário");
  botaoNovo.type = "button";
  cab.append(titulos, botaoNovo);

  const aviso = el("p");
  aviso.hidden = true;
  aviso.style.marginTop = "16px";

  const form = el("form", "painel");
  form.hidden = true;
  form.style.marginTop = "20px";
  form.innerHTML = `<h2>Novo usuário</h2>
    <p class="sub" style="margin-bottom:12px">O app cria uma senha temporária e mostra na tela uma única vez. Passe-a para a pessoa.</p>
    <div class="grade-form">
      <label>Nome completo <input id="nu-nome" maxlength="100" required></label>
      <label>Nome de usuário <input id="nu-usuario" maxlength="30" autocapitalize="none" spellcheck="false" placeholder="ex.: maria.silva" required></label>
      <label>E-mail <input id="nu-email" type="email" maxlength="150" required></label>
    </div>
    <p id="nu-msg" hidden></p>
    <button class="botao primario" type="submit">Criar usuário</button>`;

  const painel = el("section", "painel");
  const rolagem = el("div", "rolagem");
  const tabela = el("table", "lista");
  tabela.innerHTML = "<thead><tr><th>Nome completo</th><th>Usuário</th><th>E-mail</th><th>Tipo</th><th>Ações</th></tr></thead><tbody></tbody>";
  rolagem.append(tabela);
  painel.append(rolagem);
  raiz.append(cab, aviso, form, painel);

  function desenharTabela() {
    const corpo = tabela.querySelector("tbody");
    corpo.replaceChildren();
    for (const u of usuarios) {
      const tr = el("tr");
      const nome = el("td", "", u.nome);
      if (u.sou_eu) nome.append(el("span", "voce", "(você)"));
      const tipo = el("td");
      tipo.append(el("span", "etiqueta" + (u.admin ? " admin" : ""), u.admin ? "Administrador" : "Comum"));
      if (u.trocar_senha) tipo.append(el("span", "voce", "senha temporária"));

      const botoes = el("div", "acoes-linha");
      const novoBotao = (rotulo, classe, acao) => {
        const b = el("button", "botao pequeno " + classe, rotulo);
        b.type = "button";
        b.addEventListener("click", () => acao(b));
        botoes.append(b);
        return b;
      };
      if (!u.sou_eu) novoBotao("Redefinir senha", "", (b) => redefinir(u, b));
      novoBotao(u.admin ? "Rebaixar a comum" : "Promover a admin", "", (b) => mudarTipo(u, b));
      if (!u.sou_eu) novoBotao("Excluir", "perigo", (b) => excluir(u, b));
      const celula = el("td", "celula-acoes");
      celula.append(botoes);

      tr.append(nome, el("td", "", u.usuario), el("td", "", u.email), tipo, celula);
      corpo.append(tr);
    }
  }

  async function recarregar() {
    const r = await api("GET", "/api/admin/usuarios");
    if (cancelado) return;
    usuarios = r.usuarios;
    desenharTabela();
  }

  async function executar(botao, textoEnquanto, funcao, sucesso) {
    mensagem(aviso, "");
    try {
      await comBotao(botao, textoEnquanto, funcao);
      if (sucesso) mensagem(aviso, sucesso, "ok");
    } catch (erro) {
      mensagem(aviso, erro.message);
    }
    try { await recarregar(); } catch { /* o aviso acima já explica */ }
  }

  const redefinir = (u, b) => {
    if (!confirm(`Redefinir a senha de ${u.nome}? A senha atual deixa de funcionar.`)) return;
    return executar(b, "Gerando…", async () => {
      const r = await api("POST", `/api/admin/usuarios/${u.id}/redefinir-senha`);
      mostrarSenhaTemporaria(`Nova senha temporária de ${u.nome} (usuário: ${u.usuario}). No próximo acesso ela será obrigada a criar uma senha nova.`, r.senha_temporaria);
    });
  };
  const mudarTipo = (u, b) => {
    const virarAdmin = !u.admin;
    if (!confirm(virarAdmin ? `Promover ${u.nome} a administrador?` : `Rebaixar ${u.nome} a usuário comum?`)) return;
    return executar(b, "Salvando…", async () => {
      await api("POST", `/api/admin/usuarios/${u.id}/tipo`, { admin: virarAdmin });
      if (u.sou_eu && !virarAdmin) { eu.admin = false; mostrarApp(); }
    }, virarAdmin ? `${u.nome} agora é administrador.` : `${u.nome} agora é usuário comum.`);
  };
  const excluir = (u, b) => {
    if (!confirm(`Excluir ${u.nome}? Isso apaga o usuário e a carteira dele, e não dá para desfazer.`)) return;
    return executar(b, "Excluindo…", () => api("DELETE", `/api/admin/usuarios/${u.id}`), `${u.nome} foi excluído.`);
  };

  botaoNovo.addEventListener("click", () => {
    form.hidden = !form.hidden;
    if (!form.hidden) $("nu-nome").focus();
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const msg = form.querySelector("#nu-msg");
    mensagem(msg, "");
    msg.style.marginBottom = "14px";
    try {
      const r = await comBotao(form.querySelector("button[type=submit]"), "Criando…", () =>
        api("POST", "/api/admin/usuarios", { nome: $("nu-nome").value, usuario: $("nu-usuario").value, email: $("nu-email").value }));
      form.reset();
      form.hidden = true;
      mostrarSenhaTemporaria(`Usuário criado: ${r.usuario.nome} (usuário: ${r.usuario.usuario}). Passe a senha temporária abaixo para a pessoa. No primeiro acesso ela será obrigada a criar uma senha nova.`, r.senha_temporaria);
      mensagem(aviso, `${r.usuario.nome} foi criado.`, "ok");
      await recarregar();
    } catch (erro) {
      mensagem(msg, erro.message);
    }
  });

  recarregar().catch((erro) => mensagem(aviso, erro.message));
  return () => { cancelado = true; };
}

// ---------- Início ----------
(async function iniciar() {
  try {
    const r = await api("GET", "/api/eu");
    csrf = r.csrf;
    if (r.logado) { eu = r.usuario; mostrarApp(); } else mostrarLogin();
  } catch (erro) {
    mostrarLogin(erro.message);
  }
})();
