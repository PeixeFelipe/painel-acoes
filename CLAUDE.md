# Painel de Ações

App web local com login, área de administração e carteira de ações por usuário. Cotações vêm do Yahoo Finance.
Dono do projeto: iniciante em programação. Explicar tudo em linguagem simples, em português do Brasil.

## Comandos

```
python -m pip install -r requirements-dev.txt   # instala as bibliotecas (+ pytest); iniciar.bat usa só requirements.txt
python servidor.py                          # liga o app em http://localhost:5000 (ou dois cliques em iniciar.bat)
python -m pytest testes -q                  # testes automáticos (usam banco temporário e Yahoo falso; ~20 s)
```

Para testar sem mexer nos dados reais, defina antes de ligar: `CAMINHO_BANCO` (banco temporário), `ADMIN_USUARIO`,
`ADMIN_SENHA`, `PORTA` e `ABRIR_NAVEGADOR=0`.

## Stack

- Python 3.12 + Flask, servido com waitress (no seu computador só em 127.0.0.1; na nuvem, 0.0.0.0 atrás do proxy do Railway).
- SQLite (`dados.db`) via módulo `sqlite3`, sem ORM.
- Front-end sem build: HTML/CSS/JS puros em `static/`; gráficos com Chart.js 4 pelo CDN.
- yfinance para o Yahoo Finance.

## Estrutura

| Arquivo | Papel |
|---|---|
| `servidor.py` | App Flask: login, sessão, CSRF, rotas `/api/*`, admin, carteira. Ponto de entrada (`criar_app()`). |
| `cotacoes.py` | Busca no Yahoo, cache de 15 min, validação de códigos, mensagens de erro amigáveis. |
| `static/index.html` | Página única (login + app + diálogo de senha temporária). |
| `static/app.js` | Chamadas à API, login, roteamento por `#/pagina`, páginas Carteira, Conta e Administração. |
| `static/acoes.js` | Formatação pt-BR, página "Ações" (cards, gráficos, períodos, tabelas, CSV). Carrega antes do `app.js`. |
| `static/estilo.css` | Visual, modo escuro automático, layout responsivo. |
| `testes/test_servidor.py` | Testes do servidor. |
| `antigo/` | Versão da aula passada (dados estáticos). Só referência; não usar. |
| `.env` | Segredo local: dados do primeiro admin. **Nunca commitar, nunca exibir o conteúdo.** |
| `dados.db`, `dados.chave` | Banco e chave que assina o cookie de login. Criados sozinhos; **não apagar** (apagar = perder usuários/carteiras/logins). |

## Regras de negócio (não quebrar)

- Só existem dois tipos: administrador e comum. Ninguém se cadastra sozinho; só admin cria usuários.
- Sistema nunca fica sem administrador: bloquear rebaixar/excluir o último. Admin não exclui a si mesmo.
- Senha temporária (criação ou redefinição) → `trocar_senha=1`. O servidor (hook `proteger` em `servidor.py`) bloqueia toda rota
  exceto `eu`, `sair` e `trocar_minha_senha` até a troca. Não depender só do front-end.
- Senha temporária é devolvida **uma única vez** na resposta da API; nunca é gravada legível.
- Primeiro admin é criado no primeiro start, se a tabela `usuarios` estiver vazia, com os dados do `.env`.
- Carteira nova começa com PETR4, ITUB4, VALE3; máximo de 8 ações (o gráfico tem 8 cores).
- Cotações: cache de 15 min compartilhado; se o Yahoo falhar e houver cache antigo, serve o antigo marcando `desatualizado`.

## Segurança (convenções)

- Senhas com `werkzeug.security` (scrypt). Nenhuma senha, chave ou token no código.
- Login: cookie de sessão assinado, HttpOnly, SameSite=Lax, 8 h; mensagem única "Usuário ou senha incorretos" (não revela quem existe);
  bloqueio de 5 min após 5 erros seguidos por (usuário, IP).
- Toda requisição POST/DELETE exige o header `X-CSRF-Token` (o front guarda em `csrf`).
- O front monta o DOM com `textContent`/`el()`; **nunca** inserir texto de usuário/API via `innerHTML`.
  `innerHTML` só com HTML fixo escrito por nós.
- CSP restritiva em `cabecalhos()`: scripts só de `'self'` e `cdn.jsdelivr.net`. Sem JS inline.

## Estilo de código

- Tudo em português do Brasil: interface, mensagens de erro, comentários, README, nomes de funções e variáveis de domínio.
- Comentários explicam o "porquê", curtos. Erros para o usuário via `ErroDeUso("mensagem amigável", status, codigo)`;
  nunca deixar vazar traceback ou mensagem técnica na tela.
- Cores só por variáveis CSS (`--serie-1..8`, etc.), com valores para modo claro e escuro em `:root`.
- Ao mudar regra de negócio, adicionar/ajustar teste em `testes/test_servidor.py` e rodar a suíte inteira.

## Antes de dizer que terminou

1. `python -m pytest testes -q` verde.
2. Ligar o app (com banco temporário) e conferir no navegador: login, admin, senha temporária, carteira, gráficos, celular.
3. Atualizar `README.md` se algo visível ao usuário mudou.

## Publicação (Railway + GitHub)

- Código: https://github.com/PeixeFelipe/painel-acoes (público). Branch `main`. **Publicou no GitHub = o Railway publica sozinho.**
- Site: https://painel-acoes-production-02b6.up.railway.app (projeto `trustworthy-endurance`, serviço `painel-acoes`, ambiente `production`).
- Build automático (Railpack, Python 3.12 via `.python-version`, `requirements.txt` com versões travadas). Início: `python servidor.py`
  (`railway.json`); o Railway visita `/saude` para saber se o app está de pé.
- **Disco permanente:** Volume de 500 MB montado em `/data`; o banco fica em `/data/dados.db`. Sem o volume, cada publicação apaga usuários e carteiras.
  Um serviço só pode ter um volume.
- **Segredos só nas Variables do Railway, nunca em arquivo/código:**

  | Variável | Para quê |
  |---|---|
  | `ADMIN_USUARIO`, `ADMIN_SENHA`, `ADMIN_NOME`, `ADMIN_EMAIL` | Primeiro admin (só vale com o banco vazio) |
  | `CHAVE_SECRETA` | Assina o cookie de login. Trocar = todo mundo é deslogado |
  | `CAMINHO_BANCO=/data/dados.db` | Onde fica o banco (no volume) |
  | `COOKIE_SEGURO=1` | Cookie só trafega por https |
  | `CONFIAR_PROXY=1` | Usa o IP real (cabeçalho do proxy do Railway) no bloqueio de tentativas |

- Modo nuvem = existe a variável `PORT` (o Railway define): o app escuta em `0.0.0.0` e não abre o navegador. Sem `PORT`: só `127.0.0.1`.
- Comandos úteis (CLI já ligada ao projeto): `railway status`, `railway logs -d --lines 50`, `railway deployment list`,
  `railway variable list` (**mostra segredos: nunca colar a saída em lugar público**), `railway domain`.
- Plano: Trial (crédito e prazo limitados; depois disso o site pode pausar até escolher plano pago). Conferir o saldo no painel.
- Aviso do Railway: `railway.json` está "deprecated" (funciona até 2026-12-01); migrar depois com `railway config migrate`.
- O rate limit de login é em memória (zera a cada publicação/reinício). Aceitável para poucos usuários.

## Fora de escopo por enquanto

Domínio próprio, e-mail de recuperação de senha, mais de uma réplica do servidor (o banco SQLite exige uma só).
