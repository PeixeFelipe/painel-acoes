// Utilidades de formatação e a página "Ações" (cards, gráficos, tabelas e CSV).
// Este arquivo é carregado antes do app.js, que usa as funções daqui.

const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const ATUALIZAR_A_CADA_MS = 15 * 60 * 1000;

const PERIODOS = [
  { id: "1m", rotulo: "1 mês", meses: 1 },
  { id: "3m", rotulo: "3 meses", meses: 3 },
  { id: "6m", rotulo: "6 meses", meses: 6 },
  { id: "ano", rotulo: "No ano" },
  { id: "1a", rotulo: "1 ano", meses: 12 },
  { id: "max", rotulo: "Máximo" },
];

// ---------- Formatação (padrão brasileiro) ----------
const numero = (n, casas = 2) =>
  n.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
const reais = (n) => "R$ " + numero(n);
const porcento = (fracao) => (fracao >= 0 ? "+" : "−") + numero(Math.abs(fracao * 100), 1) + "%";
const dataBR = (iso) => iso.split("-").reverse().join("/"); // 2025-01-02 -> 02/01/2025
const horaBR = (segundos) => new Date(segundos * 1000).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });

// Cria um elemento. Usa textContent, então nada digitado por alguém vira código na página.
function el(tag, classe, texto) {
  const e = document.createElement(tag);
  if (classe) e.className = classe;
  if (texto !== undefined) e.textContent = texto;
  return e;
}

// ---------- Períodos ----------
function dataDeCorte(periodo, ultimaData) {
  if (periodo.id === "max") return "";
  const [ano, mes, dia] = ultimaData.split("-").map(Number);
  if (periodo.id === "ano") return `${ano}-01-01`;
  return new Date(Date.UTC(ano, mes - 1 - periodo.meses, dia)).toISOString().slice(0, 10);
}

function textoDoPeriodo(periodo, ultimaData) {
  if (periodo.id === "ano") return `em ${ultimaData.slice(0, 4)}`;
  if (periodo.id === "max") return "desde o início";
  return `em ${periodo.rotulo}`;
}

// Recorta o histórico de cada ação para o período escolhido e calcula os números.
function prepararSeries(itens, periodo) {
  const ultima = itens.map((i) => i.datas[i.datas.length - 1]).sort().pop();
  const corte = dataDeCorte(periodo, ultima);
  const series = [];
  itens.forEach((item, pos) => {
    const ini = item.datas.findIndex((d) => d >= corte);
    if (ini < 0) return;
    const datas = item.datas.slice(ini);
    const f = item.fechamento.slice(ini);
    series.push({
      codigo: item.codigo,
      nome: item.nome,
      slot: (pos % 8) + 1, // a cor segue a posição na carteira
      datas,
      fechamento: f,
      inicial: f[0],
      final: f[f.length - 1],
      variacao: f[f.length - 1] / f[0] - 1,
      maxima: Math.max(...f),
      minima: Math.min(...f),
      indice: f.map((v) => (v / f[0]) * 100),
      porData: new Map(datas.map((d, i) => [d, i])),
    });
  });
  const datas = [...new Set(series.flatMap((s) => s.datas))].sort();
  return { series, datas, ultima, textoPeriodo: textoDoPeriodo(periodo, ultima) };
}

// Valores alinhados com a lista de datas (null onde a ação ainda não existia).
const alinhar = (s, datas, valores) => datas.map((d) => (s.porData.has(d) ? valores[s.porData.get(d)] : null));

// ---------- Cartões, tabelas e legendas ----------
function desenharCartoes(caixa, series, textoPeriodo) {
  caixa.replaceChildren();
  for (const s of series) {
    const cartao = el("article", "painel cartao");
    const titulo = el("h3");
    const traco = el("span", "traco");
    traco.style.setProperty("--cor", `var(--serie-${s.slot})`);
    titulo.append(traco, s.nome, " ", el("span", "codigo", s.codigo));
    const subiu = s.variacao >= 0;
    cartao.append(
      titulo,
      el("p", "valor", reais(s.final)),
      el("p", "variacao " + (subiu ? "alta" : "queda"), `${subiu ? "▲" : "▼"} ${porcento(s.variacao)} ${textoPeriodo}`),
      el("p", "detalhe", `${reais(s.inicial)} em ${dataBR(s.datas[0])} → ${reais(s.final)} em ${dataBR(s.datas[s.datas.length - 1])}`)
    );
    caixa.append(cartao);
  }
}

function desenharTabelaResumo(tabela, series) {
  const corpo = tabela.querySelector("tbody");
  corpo.replaceChildren();
  for (const s of series) {
    const tr = el("tr");
    tr.append(
      el("td", "", `${s.nome} (${s.codigo})`),
      el("td", "", reais(s.inicial)),
      el("td", "", reais(s.final)),
      el("td", s.variacao >= 0 ? "alta" : "queda", `${s.variacao >= 0 ? "▲" : "▼"} ${porcento(s.variacao)}`),
      el("td", "", reais(s.maxima)),
      el("td", "", reais(s.minima))
    );
    corpo.append(tr);
  }
}

function desenharTabelaDiaria(tabela, series, datas) {
  const cabeca = tabela.querySelector("thead");
  const corpo = tabela.querySelector("tbody");
  cabeca.replaceChildren();
  corpo.replaceChildren();
  const linhaCab = el("tr");
  linhaCab.append(el("th", "", "Data"));
  for (const s of series) linhaCab.append(el("th", "", s.codigo));
  cabeca.append(linhaCab);
  const colunas = series.map((s) => alinhar(s, datas, s.fechamento));
  const fragmento = document.createDocumentFragment();
  for (let i = datas.length - 1; i >= 0; i--) { // mais recente primeiro
    const tr = el("tr");
    tr.append(el("td", "", dataBR(datas[i])));
    for (const col of colunas) tr.append(el("td", "", col[i] == null ? "—" : numero(col[i])));
    fragmento.append(tr);
  }
  corpo.append(fragmento);
}

function desenharLegendas(raiz, series) {
  raiz.querySelectorAll("[data-legenda]").forEach((caixa) => {
    caixa.replaceChildren();
    for (const s of series) {
      const item = el("span");
      const traco = el("span", "traco");
      traco.style.setProperty("--cor", `var(--serie-${s.slot})`);
      item.append(traco, s.codigo);
      caixa.append(item);
    }
  });
}

// CSV para abrir no Excel brasileiro: separador ";", vírgula decimal e acentos corretos.
function baixarCsv(series, datas, periodo) {
  const colunas = series.map((s) => alinhar(s, datas, s.fechamento));
  const linhas = [["Data", ...series.map((s) => s.codigo)].join(";")];
  datas.forEach((d, i) => {
    linhas.push([dataBR(d), ...colunas.map((c) => (c[i] == null ? "" : String(c[i]).replace(".", ",")))].join(";"));
  });
  const blob = new Blob(["﻿" + linhas.join("\r\n")], { type: "text/csv;charset=utf-8" });
  const link = el("a");
  link.href = URL.createObjectURL(blob);
  link.download = `cotacoes-${periodo.id}-${datas[datas.length - 1]}.csv`;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

// ---------- Gráficos ----------
function lerCores() {
  const css = getComputedStyle(document.documentElement);
  const v = (nome) => css.getPropertyValue(nome).trim();
  return {
    superficie: v("--superficie"), tinta: v("--tinta"), tinta2: v("--tinta-2"),
    grade: v("--grade"), base: v("--base"), borda: v("--borda"),
    serie: [1, 2, 3, 4, 5, 6, 7, 8].map((n) => v(`--serie-${n}`)),
  };
}

// Linha vertical que acompanha o mouse.
const plugMira = {
  id: "mira",
  beforeDatasetsDraw(chart, _args, opcoes) {
    const ativos = chart.tooltip ? chart.tooltip.getActiveElements() : [];
    if (!ativos.length) return;
    const { ctx, chartArea } = chart;
    const x = ativos[0].element.x;
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(x, chartArea.top);
    ctx.lineTo(x, chartArea.bottom);
    ctx.lineWidth = 1;
    ctx.strokeStyle = opcoes.cor;
    ctx.stroke();
    ctx.restore();
  },
};

// Bolinha e nome da ação no fim de cada linha.
const plugRotuloFinal = {
  id: "rotuloFinal",
  afterDatasetsDraw(chart, _args, opcoes) {
    const { ctx } = chart;
    chart.data.datasets.forEach((ds, i) => {
      let ultimo = ds.data.length - 1;
      while (ultimo >= 0 && ds.data[ultimo] == null) ultimo--;
      const ponto = ultimo >= 0 ? chart.getDatasetMeta(i).data[ultimo] : null;
      if (!ponto) return;
      ctx.save();
      ctx.fillStyle = opcoes.superficie; // anel que separa o ponto da linha
      ctx.beginPath();
      ctx.arc(ponto.x, ponto.y, 6, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = ds.borderColor;
      ctx.beginPath();
      ctx.arc(ponto.x, ponto.y, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = opcoes.texto;
      ctx.font = "600 12px system-ui, sans-serif";
      ctx.textBaseline = "middle";
      ctx.fillText(ds.label, ponto.x + 12, ponto.y);
      ctx.restore();
    });
  },
};

function criarGrafico(canvas, series, datas, { valores, formatarEixo, formatarValor, destacarCem }) {
  const c = lerCores();
  const dias = (Date.parse(datas[datas.length - 1]) - Date.parse(datas[0])) / 86400000;
  const rotuloX = (iso) => (dias <= 100 ? dataBR(iso).slice(0, 5) : `${MESES[Number(iso.slice(5, 7)) - 1]}/${iso.slice(2, 4)}`);

  const datasets = series.map((s) => {
    const cor = c.serie[s.slot - 1];
    return {
      label: s.codigo,
      data: alinhar(s, datas, valores(s)),
      borderColor: cor,
      backgroundColor: cor,
      borderWidth: 2,
      borderJoinStyle: "round",
      borderCapStyle: "round",
      pointRadius: 0,
      pointHoverRadius: 4,
      pointHoverBackgroundColor: cor,
      pointHoverBorderColor: c.superficie,
      pointHoverBorderWidth: 2,
    };
  });

  return new Chart(canvas, {
    type: "line",
    data: { labels: datas, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      layout: { padding: { right: 64, top: 8 } },
      interaction: { mode: "index", intersect: false },
      scales: {
        x: {
          grid: { display: false },
          border: { color: c.base },
          ticks: {
            maxRotation: 0,
            maxTicksLimit: 8,
            color: c.tinta2,
            callback(valor) { return rotuloX(this.getLabelForValue(valor)); },
          },
        },
        y: {
          border: { display: false },
          grid: { lineWidth: 1, color: (ctx) => (destacarCem && ctx.tick && ctx.tick.value === 100 ? c.base : c.grade) },
          ticks: { color: c.tinta2, callback: (v) => formatarEixo(v) },
        },
      },
      plugins: {
        legend: { display: false }, // a legenda em HTML fica no topo do gráfico
        mira: { cor: c.base },
        rotuloFinal: { superficie: c.superficie, texto: c.tinta2 },
        tooltip: {
          filter: (item) => item.raw != null,
          itemSort: (a, b) => b.raw - a.raw,
          backgroundColor: c.superficie,
          borderColor: c.borda,
          borderWidth: 1,
          titleColor: c.tinta2,
          bodyColor: c.tinta,
          titleFont: { weight: "400" },
          bodyFont: { weight: "600" },
          padding: 10,
          usePointStyle: true,
          callbacks: {
            title: (itens) => dataBR(datas[itens[0].dataIndex]),
            label: (item) => `${formatarValor(item.raw)}  ${item.dataset.label}`,
            labelColor: (item) => ({ borderColor: item.dataset.borderColor, backgroundColor: item.dataset.borderColor, borderWidth: 2 }),
            labelPointStyle: () => ({ pointStyle: "line", rotation: 0 }),
          },
        },
      },
    },
    plugins: [plugMira, plugRotuloFinal],
  });
}

// ---------- Análise do Dia (botão flutuante + janela) ----------
// Transforma o Markdown simples da IA (negrito, itálico, listas) em elementos, sem usar innerHTML.
function markdownSimples(texto) {
  const caixa = document.createDocumentFragment();
  const inline = (pai, linha) => {
    for (const parte of linha.split(/(\*\*[^*]+\*\*|\*[^*]+\*|_[^_]+_)/g)) {
      if (!parte) continue;
      if (parte.startsWith("**") && parte.endsWith("**") && parte.length > 4) pai.append(el("strong", "", parte.slice(2, -2)));
      else if (/^[*_][^*_]+[*_]$/.test(parte)) pai.append(el("em", "", parte.slice(1, -1)));
      else pai.append(parte);
    }
  };
  let lista = null;
  for (const bruta of texto.split("\n")) {
    const linha = bruta.trim();
    if (!linha) { lista = null; continue; }
    const item = linha.match(/^[-*•]\s+(.*)$/);
    if (item) {
      if (!lista) { lista = el("ul"); caixa.append(lista); }
      const li = el("li");
      inline(li, item[1]);
      lista.append(li);
      continue;
    }
    lista = null;
    const titulo = linha.match(/^#{1,6}\s+(.*)$/);
    const p = el(titulo ? "h3" : "p");
    inline(p, titulo ? titulo[1] : linha);
    caixa.append(p);
  }
  return caixa;
}

function criarAnalise(apiFluxo, periodoAtual) {
  const botao = el("button", "botao-analise", "Análise do Dia");
  botao.type = "button";
  botao.setAttribute("aria-haspopup", "dialog");

  const dialogo = el("dialog", "dialogo-analise");
  dialogo.setAttribute("aria-labelledby", "titulo-analise");
  const topo = el("div", "topo-analise");
  const titulo = el("h2", "", "Análise do Dia");
  titulo.id = "titulo-analise";
  const fechar = el("button", "botao pequeno", "Fechar");
  fechar.type = "button";
  topo.append(titulo, fechar);
  const meta = el("div", "meta-analise");
  const linhaPeriodo = el("p");
  const linhaHora = el("p");
  meta.append(linhaPeriodo, linhaHora);
  const texto = el("div", "texto-analise");
  const estado = el("p", "sub estado-analise");
  const aviso = el("p", "erro");
  aviso.hidden = true;
  const rodape = el("p", "rodape-analise", "Texto gerado por inteligência artificial (Anthropic) a partir dos preços do Yahoo Finance. Para gerar a análise, seu nome e os números da sua carteira são enviados à Anthropic.");
  const corpo = el("div", "corpo-analise");
  corpo.append(meta, aviso, texto, estado);
  dialogo.append(topo, corpo, rodape);
  document.body.append(botao, dialogo);

  let controle = null;   // permite cancelar a geração ao fechar a janela
  let recebido = "";     // tudo o que a IA já mandou
  let mostrado = 0;      // quantos caracteres já "digitados" na tela
  let terminou = false;
  let relogio = null;

  function pintar() {
    texto.replaceChildren(markdownSimples(recebido.slice(0, mostrado)));
    corpo.scrollTop = corpo.scrollHeight;
  }
  function digitar() {
    if (mostrado < recebido.length) {
      // Anda mais rápido quando há muito texto na fila, para nunca ficar muito atrás da IA.
      mostrado = Math.min(recebido.length, mostrado + Math.max(1, Math.ceil((recebido.length - mostrado) / 50)));
      pintar();
    } else if (terminou) {
      clearInterval(relogio);
      relogio = null;
      estado.textContent = "";
      texto.removeAttribute("aria-busy");
    }
  }
  function parar() {
    if (controle) controle.abort();
    controle = null;
    clearInterval(relogio);
    relogio = null;
  }
  function falhar(mensagem) {
    aviso.textContent = mensagem;
    aviso.hidden = false;
    estado.textContent = "";
    terminou = true;
  }

  async function abrir() {
    parar();
    recebido = ""; mostrado = 0; terminou = false;
    texto.replaceChildren();
    texto.setAttribute("aria-busy", "true");
    aviso.hidden = true;
    linhaPeriodo.textContent = "";
    linhaHora.textContent = "";
    estado.textContent = "Lendo os números da sua carteira e escrevendo a análise…";
    if (!dialogo.open) dialogo.showModal();
    controle = new AbortController();
    relogio = setInterval(digitar, 25);
    try {
      await apiFluxo("/api/analise", { periodo: periodoAtual().id }, (ev) => {
        if (ev.tipo === "inicio") {
          linhaPeriodo.textContent = `Período analisado: ${ev.periodo} (${dataBR(ev.de)} a ${dataBR(ev.ate)})`;
          linhaHora.textContent = `Análise gerada às ${horaBR(ev.gerada_em)}` + (ev.em_cache ? " (reaproveitada: sua carteira e o período não mudaram nos últimos 15 minutos)" : "");
        } else if (ev.tipo === "texto") {
          recebido += ev.t;
        } else if (ev.tipo === "erro") {
          falhar(ev.mensagem);
        } else if (ev.tipo === "fim") {
          terminou = true;
        }
      }, controle.signal);
      if (!terminou) terminou = true; // a conexão acabou sem "fim": mostra o que chegou
    } catch (erro) {
      if (erro.name === "AbortError") return;
      falhar(erro.message);
    }
  }

  botao.addEventListener("click", abrir);
  fechar.addEventListener("click", () => dialogo.close());
  dialogo.addEventListener("close", parar); // também vale para a tecla Esc
  dialogo.addEventListener("click", (e) => { if (e.target === dialogo) dialogo.close(); }); // clicar fora fecha

  return () => { parar(); botao.remove(); dialogo.remove(); };
}

// ---------- Página "Ações" ----------
// Devolve uma função de limpeza, chamada quando a pessoa troca de página.
function paginaAcoes(raiz, api, apiFluxo) {
  let dados = null;            // resposta do servidor
  let periodo = PERIODOS.find((p) => p.id === "1a");
  let graficos = [];
  let cancelado = false;
  let fotoAtual = null;        // resultado de prepararSeries, usado pelo CSV

  raiz.replaceChildren();
  const cab = el("div", "cabecalho-pagina");
  const titulos = el("div");
  titulos.append(el("h1", "", "Ações"), el("p", "sub", "Preço de fechamento diário (R$), sem dividendos, das ações da sua carteira."));
  const botoesPeriodo = el("div", "periodos");
  botoesPeriodo.setAttribute("role", "group");
  botoesPeriodo.setAttribute("aria-label", "Período dos gráficos");
  for (const p of PERIODOS) {
    const b = el("button", "", p.rotulo);
    b.type = "button";
    b.dataset.periodo = p.id;
    b.addEventListener("click", () => { periodo = p; desenhar(); });
    botoesPeriodo.append(b);
  }
  cab.append(titulos, botoesPeriodo);

  const avisos = el("div");
  const corpo = el("div");
  const rodape = el("p", "rodape-dados");
  raiz.append(cab, avisos, corpo, rodape);
  corpo.append(el("p", "sub", "Buscando as cotações no Yahoo Finance…"));
  const removerAnalise = criarAnalise(apiFluxo, () => periodo);

  function aviso(texto, classe = "aviso") {
    avisos.append(el("p", classe, texto));
  }

  function limparGraficos() {
    graficos.forEach((g) => g.destroy());
    graficos = [];
  }

  function esqueletoCorpo() {
    corpo.innerHTML = `
      <div class="cartoes" id="cartoes"></div>
      <section class="painel">
        <div class="topo-grafico"><div><h2>Cotação diária</h2><p>Preço de fechamento em R$.</p></div><div class="legenda" data-legenda></div></div>
        <div class="area-grafico"><canvas id="grafico-cotacao" role="img" aria-label="Gráfico de linhas com a cotação diária das ações da carteira no período escolhido. Os valores estão nas tabelas abaixo."></canvas></div>
      </section>
      <section class="painel">
        <div class="topo-grafico"><div><h2>Performance comparada</h2><p>Todas começam em 100 no início do período. Acima de 100, valorizou; abaixo, caiu.</p></div><div class="legenda" data-legenda></div></div>
        <div class="area-grafico"><canvas id="grafico-performance" role="img" aria-label="Gráfico de linhas com a performance comparada das ações da carteira, todas partindo de 100. Os valores estão nas tabelas abaixo."></canvas></div>
      </section>
      <section class="painel"><h2>Resumo do período</h2>
        <div class="rolagem"><table id="tabela-resumo"><thead><tr><th>Empresa</th><th>Preço inicial</th><th>Preço final</th><th>Variação</th><th>Máxima</th><th>Mínima</th></tr></thead><tbody></tbody></table></div>
      </section>
      <section class="painel">
        <details id="detalhe-diario">
          <summary>Ver todos os preços diários</summary>
          <div class="topo-tabela" style="margin-top:10px"><span class="sub" style="margin:0" id="conta-linhas"></span><button type="button" class="botao" id="botao-csv">Baixar CSV</button></div>
          <div class="rolagem"><table id="tabela-diaria"><thead></thead><tbody></tbody></table></div>
        </details>
      </section>`;
    corpo.querySelector("#botao-csv").addEventListener("click", () => baixarCsv(fotoAtual.series, fotoAtual.datas, periodo));
    corpo.querySelector("#detalhe-diario").addEventListener("toggle", (e) => { if (e.target.open) tabelaDiaria(); });
  }

  function tabelaDiaria() {
    const detalhe = corpo.querySelector("#detalhe-diario");
    if (!detalhe || !detalhe.open) return; // só monta quando aberta: o período "Máximo" tem milhares de linhas
    desenharTabelaDiaria(corpo.querySelector("#tabela-diaria"), fotoAtual.series, fotoAtual.datas);
    corpo.querySelector("#conta-linhas").textContent = `${fotoAtual.datas.length} pregões`;
  }

  function desenhar() {
    botoesPeriodo.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.periodo === periodo.id)));
    if (!dados || !dados.itens.length) return;
    limparGraficos();
    fotoAtual = prepararSeries(dados.itens, periodo);
    const { series, datas, textoPeriodo } = fotoAtual;
    if (!corpo.querySelector("#cartoes")) esqueletoCorpo();

    desenharCartoes(corpo.querySelector("#cartoes"), series, textoPeriodo);
    desenharTabelaResumo(corpo.querySelector("#tabela-resumo"), series);
    desenharLegendas(corpo, series);
    tabelaDiaria();

    if (typeof Chart === "undefined") {
      if (!avisos.querySelector("[data-sem-grafico]")) {
        const p = el("p", "aviso", "Os gráficos não carregaram: eles precisam de internet para baixar a biblioteca Chart.js. Os números continuam nas tabelas.");
        p.dataset.semGrafico = "1";
        avisos.append(p);
      }
      return;
    }
    graficos.push(
      criarGrafico(corpo.querySelector("#grafico-cotacao"), series, datas, {
        valores: (s) => s.fechamento,
        formatarEixo: (v) => "R$ " + numero(v, 0),
        formatarValor: (v) => reais(v),
      }),
      criarGrafico(corpo.querySelector("#grafico-performance"), series, datas, {
        valores: (s) => s.indice,
        formatarEixo: (v) => numero(v, 0),
        formatarValor: (v) => `${numero(v, 1)} (${porcento(v / 100 - 1)})`,
        destacarCem: true,
      })
    );
  }

  async function carregar(recarga) {
    try {
      const novo = await api("GET", "/api/cotacoes");
      if (cancelado) return;
      dados = novo;
    } catch (erro) {
      if (cancelado) return;
      if (dados) return; // recarga automática falhou: mantém o que já está na tela
      avisos.replaceChildren();
      limparGraficos();
      const caixa = el("div", "aviso erro");
      caixa.append(el("p", "", erro.message), (() => {
        const b = el("button", "botao", "Tentar de novo");
        b.type = "button";
        b.addEventListener("click", () => { corpo.replaceChildren(el("p", "sub", "Buscando as cotações no Yahoo Finance…")); carregar(false); });
        return b;
      })());
      avisos.append(caixa);
      corpo.replaceChildren();
      return;
    }

    avisos.replaceChildren();
    rodape.textContent = "";
    for (const e of dados.erros) aviso(`Não consegui carregar ${e.codigo}: ${e.mensagem}`, "aviso erro");

    if (!dados.itens.length) {
      corpo.replaceChildren();
      if (!dados.erros.length) {
        const p = el("p", "aviso", "Sua carteira está vazia. Adicione ações na página ");
        const link = el("a", "", "Minha carteira");
        link.href = "#/carteira";
        p.append(link, ".");
        avisos.append(p);
      } else {
        const b = el("button", "botao", "Tentar de novo");
        b.type = "button";
        b.addEventListener("click", () => { corpo.replaceChildren(); carregar(false); });
        corpo.append(b);
      }
      return;
    }
    if (dados.itens.some((i) => i.desatualizado)) {
      aviso("O Yahoo Finance não respondeu agora. Estou mostrando os últimos dados que consegui, que podem estar desatualizados.");
    }
    const maisAntigo = Math.min(...dados.itens.map((i) => i.atualizado_em));
    rodape.textContent = `Cotações consultadas às ${horaBR(maisAntigo)} e renovadas a cada 15 minutos. Fonte: Yahoo Finance. Preços de fechamento sem dividendos. Não é recomendação de investimento.`;
    desenhar();
  }

  const relogio = setInterval(() => carregar(true), ATUALIZAR_A_CADA_MS);
  const modoEscuro = window.matchMedia("(prefers-color-scheme: dark)");
  const trocouModo = () => desenhar(); // redesenha com as cores certas
  modoEscuro.addEventListener("change", trocouModo);
  botoesPeriodo.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.periodo === periodo.id)));
  carregar(false);

  return () => {
    cancelado = true;
    removerAnalise();
    clearInterval(relogio);
    modoEscuro.removeEventListener("change", trocouModo);
    limparGraficos();
  };
}
