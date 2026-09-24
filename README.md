# Painel de Ações

Um app que roda no seu computador e mostra, com dados atualizados do Yahoo Finance, a cotação e a performance das ações que cada pessoa escolher acompanhar. Cada pessoa entra com seu usuário e senha e tem sua própria lista de ações.

## O que o app faz

- **Login com usuário e senha.** Sem entrar, ninguém vê nada. Ninguém se cadastra sozinho: quem cria os usuários é o administrador.
- **Ações:** cards, dois gráficos (cotação e performance comparada), tabela-resumo e tabela com todos os preços diários, com botão para **baixar em CSV** (abre no Excel). Botões de período: 1 mês, 3 meses, 6 meses, no ano, 1 ano e máximo.
- **Minha carteira:** cada usuário tem a sua lista. Começa com PETR4, ITUB4 e VALE3; dá para adicionar (ex.: WEGE3, BBAS3) e remover. Fica salva.
- **Minha conta:** seus dados e a troca de senha.
- **Administração** (só para administradores): criar usuários, redefinir senhas, promover a administrador, rebaixar a comum e excluir.
- Os dados de cotação são renovados a cada 15 minutos. Se o Yahoo Finance não responder, aparece uma mensagem clara na tela.

## Como rodar

**Da primeira vez** (e também nas seguintes):

1. Abra a pasta do app no Windows.
2. Dê **dois cliques em `iniciar.bat`**.
3. Vai abrir uma janela preta. Deixe-a aberta: ela é o app funcionando. Na primeira vez ela instala o que falta, o que pode levar um minuto.
4. O navegador abre sozinho em **http://localhost:5000**. Se não abrir, abra você e digite esse endereço.

**Para desligar:** feche a janela preta.

## Como entrar pela primeira vez

O primeiro administrador é criado automaticamente na primeira vez que o app roda. O usuário e a senha dele ficam no arquivo **`.env`**, na pasta do app.

1. Abra o arquivo `.env` com o Bloco de Notas (clique com o botão direito → Abrir com → Bloco de Notas).
2. Você verá linhas como:
   ```
   ADMIN_USUARIO=admin
   ADMIN_SENHA=uma-senha-gerada
   ADMIN_NOME=Administrador
   ADMIN_EMAIL=admin@exemplo.com.br
   ```
3. **Antes de ligar o app pela primeira vez**, se quiser, troque essas linhas pelo seu usuário, sua senha (mínimo de 8 caracteres), seu nome e seu e-mail. Salve o arquivo.
4. Ligue o app (`iniciar.bat`) e entre com esse usuário e essa senha.

Atenção:
- O `.env` só vale **na primeira vez**. Depois que o administrador existe, mudar o `.env` não muda nada. Para trocar sua senha depois, use a página **Minha conta**.
- O `.env` é secreto. Não envie para ninguém.
- Se quiser recomeçar do zero (perde tudo!), feche o app, apague os arquivos `dados.db` e `dados.chave` e ligue de novo.

## Como criar usuários

1. Entre como administrador e clique em **Administração** no menu.
2. Clique em **Novo usuário** e preencha nome completo, nome de usuário (só letras sem acento, números, ponto, traço ou sublinhado) e e-mail.
3. O app mostra uma **senha temporária, uma única vez**. Anote ou clique em Copiar e passe para a pessoa.
4. No primeiro acesso, a pessoa é obrigada a criar uma senha nova antes de usar o app.

**Esqueci minha senha:** a pessoa pede ao administrador, que clica em **Redefinir senha** na linha dela e passa a nova senha temporária.

Proteções: você não pode excluir a si mesmo e o app nunca deixa de ter pelo menos um administrador.

## Como testar

**Teste automático** (para quem mexer no código): abra o terminal na pasta, rode uma vez `python -m pip install -r requirements-dev.txt` e depois `python -m pytest testes -q`. Deve aparecer "passed" em verde.

**Roteiro para conferir com os próprios olhos:**

1. Abra o app e confira que só aparece a tela de entrada. Digite uma senha errada: deve aparecer "Usuário ou senha incorretos".
2. Entre como administrador. Deve aparecer o menu com Ações, Minha carteira, Minha conta e Administração, e seu nome embaixo.
3. Em **Ações**, clique em cada botão de período e confira que os cards e gráficos mudam. Abra "Ver todos os preços diários" e clique em **Baixar CSV**.
4. Aperte **F5**: você continua logado. Clique em **Sair**: volta à tela de entrada.
5. Em **Minha carteira**, adicione `WEGE3` (deve entrar), tente `ZZZZ9` (deve avisar que não encontrou) e remova uma ação.
6. Em **Administração**, crie um usuário de teste e anote a senha temporária. Tente rebaixar a si mesmo (deve ser recusado, pois você é o único administrador).
7. Saia e entre com o usuário de teste e a senha temporária: o app deve obrigar a criar uma senha nova. Depois, ele deve ver a carteira inicial (PETR4, ITUB4, VALE3) e **não** ver o menu Administração.
8. Volte como administrador, clique em **Redefinir senha** para o usuário de teste e depois em **Excluir**.
9. Feche a janela preta, ligue de novo e confira que usuários e carteiras continuam lá.

## Problemas comuns

| O que aconteceu | O que fazer |
|---|---|
| `iniciar.bat` diz que não conseguiu instalar | Confira se há internet e se o Python está instalado (digite `python --version` no terminal). |
| A janela preta fecha logo ou fala do arquivo `.env` | Abra o `.env` e confira `ADMIN_USUARIO` (3 a 30 letras/números) e `ADMIN_SENHA` (mínimo de 8 caracteres). |
| O navegador diz que não consegue acessar a página | A janela preta foi fechada. Dê dois cliques em `iniciar.bat` de novo. |
| "Address already in use" / porta ocupada | O app já está aberto em outra janela preta. Feche-a ou use a que já está aberta. |
| "Não consegui falar com o Yahoo Finance" | Verifique a internet. Se o Yahoo estiver fora do ar, tente de novo em alguns minutos. |
| Os gráficos não aparecem, só as tabelas | Os gráficos baixam uma biblioteca da internet; sem conexão ficam de fora. |
| "Muitas tentativas erradas" | Espere 5 minutos, ou peça ao administrador para redefinir sua senha. |
| Esqueci a senha do administrador | Se houver outro administrador, ele redefine. Se não, feche o app, apague `dados.db` e `dados.chave` (perde tudo) e ligue de novo para recriar o admin pelo `.env`. |
| A ação não existe | Use o código da B3 com 4 letras e 1 ou 2 números, como `PETR4` ou `BOVA11`. |

## Arquivos

| Arquivo | Para que serve |
|---|---|
| `iniciar.bat` | Liga o app com dois cliques. |
| `servidor.py` | O "cérebro": login, usuários, carteira. |
| `cotacoes.py` | Busca as cotações no Yahoo Finance. |
| `static/` | As telas (HTML, CSS e JavaScript). |
| `.env` | Usuário e senha do primeiro administrador (secreto). |
| `dados.db` | Onde ficam usuários, senhas (embaralhadas) e carteiras. Criado sozinho. Faça cópia dele para ter backup. |
| `testes/` | Testes automáticos. |
| `antigo/` | A versão da aula passada, guardada só de lembrança. |
| `CLAUDE.md` | Anotações técnicas para o assistente de programação. |

## Observações

- Preços de fechamento, sem dividendos. Fonte: Yahoo Finance. Pode haver diferença de centavos em relação à sua corretora.
- Este app **não é recomendação de investimento**.
- No seu computador ele funciona em `localhost`. Na internet, ele está publicado no Railway (veja a seção abaixo).

## Publicado na internet

- **Site:** https://painel-acoes-production-02b6.up.railway.app
- **Código:** https://github.com/PeixeFelipe/painel-acoes
- **Como atualiza:** toda vez que uma nova versão do código é enviada ao GitHub (branch `main`), o Railway a publica sozinho, em cerca de 1 a 2 minutos.
- **Seus dados não somem:** usuários, senhas (embaralhadas) e carteiras ficam num disco permanente do Railway (`/data`), que continua igual a cada nova versão e a cada reinício.
- **Segredos:** a senha do administrador e a chave de segurança do login ficam nas configurações do Railway (serviço → aba **Variables**), nunca no código nem no GitHub.
  - O usuário e a senha do primeiro administrador são lidos de `ADMIN_USUARIO` e `ADMIN_SENHA` só na primeira vez (com o banco vazio).
  - Para ver a senha: no painel do Railway, abra o serviço `painel-acoes` → **Variables** → clique no ícone de olho ao lado de `ADMIN_SENHA`.
  - Depois de entrar, troque a senha em **Minha conta**. Aí a variável deixa de valer e pode ser apagada sem problema.
- **Teste gratuito (Trial):** o Railway dá um crédito limitado por tempo limitado. Acompanhe o saldo no painel dele; quando acabar, o site pode ser pausado até você escolher um plano.

### Problemas comuns na internet

| O que aconteceu | O que fazer |
|---|---|
| O site não abre | Veja o estado em railway.com → seu projeto → serviço. Se estiver "Crashed", abra **Deployments → View logs** e leia a última mensagem. |
| "Crashed" com mensagem sobre o primeiro administrador | Faltam `ADMIN_USUARIO` e `ADMIN_SENHA` em **Variables**. |
| Os usuários sumiram depois de uma atualização | Confira se o serviço tem o disco (Volume) em `/data` e se `CAMINHO_BANCO` vale `/data/dados.db`. |
| Todo mundo foi deslogado | Normal se a `CHAVE_SECRETA` foi trocada. É só entrar de novo. |
