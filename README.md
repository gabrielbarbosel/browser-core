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
* **Gestão de Abas Orientada a Objetos**: Abra, feche e alterne entre abas usando objetos `Tab` para um controle mais
  limpo e intuitivo.
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
# Importações atualizadas para usar 'browser_core'
from browser_core import Browser, BrowserType, Settings

try:
    # O 'with' garante que o navegador seja fechado corretamente
    with Browser("meu_utilizador", BrowserType.CHROME) as browser:
        browser.navigate_to("https://www.google.com")
        print("Automação concluída!")
except Exception as e:
    print(f"ERRO: {e}")
```

**Exemplo com Gestão de Abas (Nova API Orientada a Objetos):**

Este exemplo foi completamente reescrito para demonstrar o novo sistema de gerenciamento de abas, que é muito mais
poderoso e intuitivo.

```python
from browser_core import Browser, BrowserType

try:
    with Browser("multi_tab_user", BrowserType.CHROME) as browser:
        # A primeira aba é sempre a 'main'. Podemos obter seu objeto de controle.
        main_tab = browser.current_tab
        main_tab.navigate_to("https://www.google.com")
        print(f"Aba '{main_tab.name}' navegou para: {main_tab.current_url}")

        # Abrir uma nova aba para relatórios. O método já retorna o objeto 'Tab'.
        reports_tab = browser.open_tab(name="relatorios")
        reports_tab.navigate_to("https://www.bing.com")
        print(f"Aba '{reports_tab.name}' navegou para: {reports_tab.current_url}")

        # Para voltar para a aba principal, basta usar seu objeto
        main_tab.switch_to()
        print(f"De volta à aba '{main_tab.name}'. URL atual: {main_tab.current_url}")

        # Para listar todas as abas abertas:
        print(f"Nomes das abas abertas: {browser.list_tab_names()}")

        # Fechar a aba de relatórios diretamente pelo seu objeto
        reports_tab.close()
        print("Aba 'relatorios' fechada.")

        # O foco do navegador volta para a aba anterior ('main') automaticamente.
        print(f"Aba ativa agora: '{browser.current_tab.name}'")

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
