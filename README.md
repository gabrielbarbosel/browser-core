# Browser-Core

[![PyPI version](https://badge.fury.io/py/browser-core.svg)](https://badge.fury.io/py/browser-core)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Um framework robusto e configurável para automação de navegadores em Python, com gestão de perfis, sessões e uma CLI
integrada.

---

## Visão Geral

O **Browser-Core** foi desenhado para ser a fundação de qualquer projeto de automação web. Ele abstrai as complexidades
do Selenium e da gestão de WebDrivers, oferecendo uma API limpa e de alto nível para interagir com navegadores. A sua
arquitetura é focada em resiliência, organização e escalabilidade, permitindo que os desenvolvedores se concentrem na
lógica de negócio da automação, e não na infraestrutura.

## Principais Funcionalidades

* **Gestão Automática de Drivers**: Faz o download e gere o cache dos WebDrivers automaticamente.
* **Perfis de Utilizador Persistentes**: Mantém o estado do navegador (cookies, etc.) entre execuções.
* **Sessões de Automação Isoladas**: Cada execução gera uma sessão única com os seus próprios logs e snapshots.
* **Snapshots Inteligentes**: Captura o estado da página em pontos-chave ou em caso de erro.
* **Gestão de Abas Intuitiva**: Abra, feche e alterne entre abas usando nomes amigáveis.
* **Configuração Flexível**: Um sistema de configurações unificado permite personalizar facilmente o comportamento do
  navegador.
* **CLI Integrada**: Uma ferramenta de linha de comando para gerir o ecossistema.
* **Seletores com Fallback**: Aumenta a resiliência das automações contra pequenas alterações no front-end.

---

## Instalação

A forma recomendada de instalar o `browser-core` é através do PyPI:

```bash
pip install browser-core
```

Isto irá descarregar e instalar a versão mais recente e estável do pacote.

---

## Como Usar

### 1. Uso como SDK (Biblioteca)

Importe e use o `Browser` no seu projeto de automação.

**Exemplo Básico:**

```python
from browser_core import Browser, Settings, BrowserType

try:
    # Use 'with' para garantir que o navegador é fechado corretamente
    with Browser("meu_utilizador", BrowserType.CHROME) as browser:
        browser.navigate_to("https://www.google.com")
        print("Automação concluída!")
except Exception as e:
    print(f"ERRO: {e}")
```

**Exemplo com Gestão de Abas:**

```python
from browser_core import Browser, BrowserType

try:
    with Browser("multi_tab_user", BrowserType.CHROME) as browser:
        # A primeira aba é a 'main'
        browser.navigate_to("https://www.google.com")
        print(f"Título da aba 'main': {browser._driver.title}")

        # Abrir e nomear uma nova aba para relatórios
        reports_tab_name = browser.open_tab(name="relatorios")
        browser.navigate_to("https://www.bing.com")
        print(f"Título da aba '{reports_tab_name}': {browser._driver.title}")

        # Voltar para a aba principal
        browser.switch_to_tab("main")
        print(f"De volta à aba 'main'. Título: {browser._driver.title}")

        # Fechar a aba de relatórios
        browser.close_tab("relatorios")
        print("Aba 'relatorios' fechada.")
except Exception as e:
    print(f"ERRO: {e}")
```

### 2. Uso da CLI

Use o comando `browser-core` no seu terminal para tarefas de manutenção.

* **Listar perfis:**

    ```bash
    browser-core profiles list
    ```

* **Atualizar um driver:**

    ```bash
    browser-core drivers update chrome
    ```

---

## Desenvolvimento e Contribuição

Se pretende contribuir para o `browser-core`, siga estes passos para configurar o seu ambiente de desenvolvimento.

### 1. Configuração do Ambiente

1. Clone o repositório:

   ```bash
   git clone https://github.com/gabrielbarbosel/browser-core.git
   cd browser-core
   ```

2. Crie e ative um ambiente virtual:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # No Linux/macOS
   # .venv\Scripts\activate    # No Windows
   ```

3. Instale o projeto em modo "editável":

   ```bash
   pip install -e .
   ```

### 2. Construir o Pacote (Build)

Para gerar os ficheiros de distribuição (`.whl` e `.tar.gz`), use o seguinte comando na raiz do projeto:

```bash
python -m build
```

Os pacotes serão gerados no diretório `dist/`.

### 3. Submeter Contribuições

Sinta-se à vontade para abrir uma *issue* para discutir uma nova funcionalidade ou reportar um bug. Para submeter
alterações, por favor, crie um *pull request* a partir de um *fork* do projeto.
