// Lê os preços de dados.js, calcula a performance e desenha a página.

const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

// ---------- Formatação (padrão brasileiro) ----------
const numero = (n, casas = 2) =>
  n.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
const reais = (n) => "R$ " + numero(n);
const porcento = (fracao) => (fracao >= 0 ? "+" : "−") + numero(Math.abs(fracao * 100), 1) + "%";
const dataBR = (iso) => iso.split("-").reverse().join("/"); // 2025-01-02 -> 02/01/2025
const diaMes = (iso) => dataBR(iso).slice(0, 5); // 02/01

function mostrarAviso(texto) {
  const aviso = document.getElementById("aviso");
  aviso.textContent = texto;
  aviso.hidden = false;
}

// ---------- Cálculos ----------
function prepararEmpresas() {
  return DADOS.map((e, i) => {
    const f = e.fechamento;
    const inicial = f[0];
    const final = f[f.length - 1];
    return {
      ...e,
      slot: i + 1, // a cor segue a empresa, não muda nunca
      inicial,
      final,
      variacao: final / inicial - 1,
      maxima: Math.max(...f),
      minima: Math.min(...f),
      indice: f.map((v) => (v / inicial) * 100),
    };
  });
}

// ---------- Cartões e tabelas (DOM com textContent) ----------
function el(tag, classe, texto) {
  const e = document.createElement(tag);
  if (classe) e.className = classe;
  if (texto !== undefined) e.textContent = texto;
  return e;
}

function desenharCartoes(empresas, datas) {
  const caixa = document.getElementById("cartoes");
  caixa.replaceChildren();
  for (const e of empresas) {
    const cartao = el("article", "painel cartao");

    const titulo = el("h3");
    const traco = el("span", "traco");
    traco.style.setProperty("--cor", `var(--serie-${e.slot})`);
    titulo.append(traco, e.nome, " ", el("span", "codigo", e.codigo));

    const subiu = e.variacao >= 0;
    const variacao = el("p", "variacao " + (subiu ? "alta" : "queda"), `${subiu ? "▲" : "▼"} ${porcento(e.variacao)} em 2025`);

    cartao.append(
      titulo,
      el("p", "valor", reais(e.final)),
      variacao,
      el("p", "detalhe", `${reais(e.inicial)} em ${diaMes(datas[0])} → ${reais(e.final)} em ${diaMes(datas[datas.length - 1])}`)
    );
    caixa.append(cartao);
  }
}

function desenharTabelaResumo(empresas) {
  const corpo = document.querySelector("#tabela-resumo tbody");
  corpo.replaceChildren();
  for (const e of empresas) {
    const tr = el("tr");
    tr.append(
      el("td", "", `${e.nome} (${e.codigo})`),
      el("td", "", reais(e.inicial)),
      el("td", "", reais(e.final)),
      el("td", e.variacao >= 0 ? "alta" : "queda", `${e.variacao >= 0 ? "▲" : "▼"} ${porcento(e.variacao)}`),
      el("td", "", reais(e.maxima)),
      el("td", "", reais(e.minima))
    );
    corpo.append(tr);
  }
}

function desenharTabelaDiaria(empresas, datas) {
  const cabeca = document.querySelector("#tabela-diaria thead");
  const corpo = document.querySelector("#tabela-diaria tbody");
  cabeca.replaceChildren();
  corpo.replaceChildren();

  const linhaCab = el("tr");
  linhaCab.append(el("th", "", "Data"));
  for (const e of empresas) linhaCab.append(el("th", "", e.codigo));
  cabeca.append(linhaCab);

  datas.forEach((d, i) => {
    const tr = el("tr");
    tr.append(el("td", "", dataBR(d)));
    for (const e of empresas) tr.append(el("td", "", numero(e.fechamento[i])));
    corpo.append(tr);
  });
}

function desenharLegendas(empresas) {
  document.querySelectorAll("[data-legenda]").forEach((caixa) => {
    caixa.replaceChildren();
    for (const e of empresas) {
      const item = el("span");
      const traco = el("span", "traco");
      traco.style.setProperty("--cor", `var(--serie-${e.slot})`);
      item.append(traco, e.codigo);
      caixa.append(item);
    }
  });
}

// ---------- Gráficos ----------
function lerCores() {
  const css = getComputedStyle(document.documentElement);
  const v = (nome) => css.getPropertyValue(nome).trim();
  return {
    superficie: v("--superficie"),
    tinta: v("--tinta"),
    tinta2: v("--tinta-2"),
    grade: v("--grade"),
    base: v("--base"),
    borda: v("--borda"),
    serie: [v("--serie-1"), v("--serie-2"), v("--serie-3")],
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
      const ponto = chart.getDatasetMeta(i).data[ds.data.length - 1];
      if (!ponto) return;
      ctx.save();
      ctx.fillStyle = opcoes.superficie; // anel de 2px que separa o ponto da linha
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

const graficos = [];

function criarGrafico(idCanvas, empresas, datas, { valores, formatarEixo, formatarValor, destacarCem }) {
  const c = lerCores();
  const primeiroDoMes = datas.map((d, i) => i === 0 || d.slice(5, 7) !== datas[i - 1].slice(5, 7));

  const datasets = empresas.map((e) => {
    const cor = c.serie[e.slot - 1];
    return {
      label: e.codigo,
      data: valores(e),
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

  const grafico = new Chart(document.getElementById(idCanvas), {
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
            autoSkip: false,
            maxRotation: 0,
            color: c.tinta2,
            callback: (_valor, i) => (primeiroDoMes[i] ? MESES[Number(datas[i].slice(5, 7)) - 1] : null),
          },
        },
        y: {
          border: { display: false },
          grid: {
            lineWidth: 1,
            color: (ctx) => (destacarCem && ctx.tick && ctx.tick.value === 100 ? c.base : c.grade),
          },
          ticks: { color: c.tinta2, callback: (v) => formatarEixo(v) },
        },
      },
      plugins: {
        legend: { display: false }, // a legenda em HTML fica no topo do gráfico
        mira: { cor: c.base },
        rotuloFinal: { superficie: c.superficie, texto: c.tinta2 },
        tooltip: {
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
  graficos.push(grafico);
}

function desenharGraficos(empresas, datas) {
  graficos.splice(0).forEach((g) => g.destroy());

  criarGrafico("grafico-cotacao", empresas, datas, {
    valores: (e) => e.fechamento,
    formatarEixo: (v) => "R$ " + numero(v, 0),
    formatarValor: (v) => reais(v),
  });

  criarGrafico("grafico-performance", empresas, datas, {
    valores: (e) => e.indice,
    formatarEixo: (v) => numero(v, 0),
    formatarValor: (v) => `${numero(v, 1)} (${porcento(v / 100 - 1)})`,
    destacarCem: true,
  });
}

// ---------- Início ----------
function iniciar() {
  if (typeof DADOS === "undefined") {
    mostrarAviso("Não encontrei o arquivo dados.js. Ele precisa estar na mesma pasta do index.html. Rode: python baixar_dados.py");
    return;
  }
  const empresas = prepararEmpresas();
  const datas = empresas[0].datas;
  if (empresas.some((e) => e.datas.join() !== datas.join())) {
    mostrarAviso("As datas das três ações não coincidem. Rode python baixar_dados.py de novo.");
    return;
  }

  desenharCartoes(empresas, datas);
  desenharTabelaResumo(empresas);
  desenharTabelaDiaria(empresas, datas);
  desenharLegendas(empresas);

  if (typeof Chart === "undefined") {
    mostrarAviso("Os gráficos não carregaram. Eles precisam de internet para baixar a biblioteca Chart.js. Os números continuam nas tabelas.");
    return;
  }
  desenharGraficos(empresas, datas);
  // Se o Windows trocar entre modo claro e escuro, redesenha com as cores certas.
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => desenharGraficos(empresas, datas));
}

iniciar();
