# Painel de Ações

Um app que roda no seu computador e mostra, com dados atualizados do Yahoo Finance, a cotação e a performance das ações que cada pessoa escolher acompanhar. Cada pessoa entra com seu usuário e senha e tem sua própria lista de ações.

## O que o app faz

- **Login com usuário e senha.** Sem entrar, ninguém vê nada. Ninguém se cadastra sozinho: quem cria os usuários é o administrador.
- **Ações:** cards, dois gráficos (cotação e performance comparada), tabela-resumo e tabela com todos os preços diários, com botão para **baixar em CSV** (abre no Excel). Botões de período: 1 mês, 3 meses, 6 meses, no ano, 1 ano e máximo.
- **Minha carteira:** cada usuário tem a sua lista. Começa com PETR4, ITUB4 e VALE3; dá para adicionar (ex.: WEGE3, BBAS3) e remover. Fica salva.
- **Minha conta:** seus dados e a troca de senha.
- **Administração** (só para administradores): criar usuários, redefinir senhas, promover a administrador, rebaixar a comum e excluir.
- Os dados de cotação são renovados a cada 15 minutos. Se o Yahoo Finance não responder, aparece uma mensagem clara na tela.
- **Análise do Dia (inteligência artificial):** um botão no canto inferior direito da página Ações abre uma janela em que a IA escreve, ao vivo, uma análise didática da sua carteira no período escolhido. Veja a seção "Análise do Dia" mais abaixo.

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
| `analise.py` | Prepara os números da carteira e conversa com a IA (Análise do Dia). |
| `instrucoes_analista.md` | As instruções da IA. Pode ser editado à vontade. |
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

## Análise do Dia (inteligência artificial)

**O que faz:** na página **Ações**, o botão **Análise do Dia** (canto inferior direito, sempre visível) abre uma janela onde o texto aparece sendo escrito ao vivo. Ela analisa a carteira de quem está logado, no período escolhido nos botões (1 mês, 3 meses, 6 meses, no ano, 1 ano ou máximo). A janela mostra o período analisado, a hora em que a análise foi gerada e o botão Fechar.

**Como funciona por dentro (sem mistério):**
1. O próprio app calcula os números de cada ação: preço atual, variação no período, mínima e máxima com datas, distância da máxima, variação em 5 pregões, tendência (média de 20 dias contra 50) e volatilidade (o quanto o preço oscila).
2. Só esse resumo de números é enviado à IA (modelo **Claude Haiku 4.5**, o mais barato da Anthropic). Ela não vê gráficos, não busca notícias e é instruída a não inventar nada.
3. A análise fica guardada por 15 minutos: clicar de novo com a mesma carteira e o mesmo período reaproveita o texto e não gasta crédito.
4. Cada pessoa pode gerar até **10 análises novas por hora**.

**Privacidade:** para gerar a análise, o nome do usuário, os códigos das ações e os números calculados são enviados à Anthropic. A janela avisa isso.

**Custo:** cerca de **US$ 0,004 por análise** (menos de meio centavo de dólar; algo como R$ 0,02 a R$ 0,03). Com US$ 5 de crédito dá para gerar bem mais de 800 análises. Os preços mudam: confira em platform.claude.com.

### Como configurar a chave (uma vez só)

A chave é uma senha do app junto à Anthropic. **Ela nunca vai para o código nem para o GitHub.**

1. **Conta e crédito:** crie a conta em https://platform.claude.com, vá em **Settings → Billing**, compre um crédito pequeno (US$ 5) e deixe a recarga automática **desligada**. Em **Settings → Limits** você pode definir um teto de gasto mensal.
2. **Criar a chave:** em **API keys → Create key**, dê o nome `painel-acoes` e copie a chave (começa com `sk-ant-`). Ela só aparece uma vez.
3. **No seu computador:** abra o arquivo `.env` com o Bloco de Notas e acrescente uma linha (sem espaços e sem aspas):
   ```
   ANTHROPIC_API_KEY=sk-ant-...sua chave aqui...
   ```
   Salve e reinicie o app (feche a janela preta e abra `iniciar.bat` de novo).
4. **No Railway (site na internet):** railway.com → seu projeto → serviço `painel-acoes` → aba **Variables** → **New Variable** → nome `ANTHROPIC_API_KEY`, valor a chave → **Add**. O Railway reinicia o app sozinho.

### Como ajustar o que a IA escreve

As instruções da IA estão no arquivo **`instrucoes_analista.md`**. Você pode editá-lo com o Bloco de Notas (mudando o tom, o tamanho, as regras). Para valer no site da internet, é preciso enviar o arquivo ao GitHub. Não mexa nos outros arquivos para isso.

Para trocar o modelo de IA (por exemplo, se o Haiku 4.5 for aposentado), defina a variável `MODELO_IA` (no `.env` ou no Railway). Sem ela, o app usa `claude-haiku-4-5-20251001`.

### Problemas comuns da análise

| O que aparece na janela | O que fazer |
|---|---|
| "A Análise do Dia ainda não foi ativada: falta a chave" | Falta cadastrar a `ANTHROPIC_API_KEY` (passo 3 ou 4 acima). |
| "A chave de acesso da IA está errada ou foi desativada" | Confira se copiou a chave inteira, sem espaços. Se preciso, crie outra chave no console e troque. |
| "O crédito da conta da IA acabou" | Adicione crédito em platform.claude.com → Settings → Billing. |
| "O modelo de IA configurado não está mais disponível" | Defina `MODELO_IA` com outro modelo (veja a lista de modelos em platform.claude.com). |
| "Pedidos demais" / "fora do ar" | Espere alguns minutos e tente de novo. |
| "Você já gerou 10 análises novas na última hora" | Espere um pouco; repetir a mesma análise não conta. |

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
