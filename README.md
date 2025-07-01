# Browser-Core

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
* **Configuração Flexível**: Um sistema de configurações unificado permite personalizar facilmente o comportamento do
  navegador.
* **CLI Integrada**: Uma ferramenta de linha de comando para gerir o ecossistema.
* **Seletores com Fallback**: Aumenta a resiliência das automações contra pequenas alterações no front-end.

---

## Instalação

Recomenda-se o uso de um ambiente virtual (`venv`).

1. Clone o repositório:
   ```bash
   git clone <url-do-seu-repositorio>
   cd browser-core
   ```

2. Instale o pacote em modo "editável":
   ```bash
   pip install -e .
   ```

---

## Como Usar

### 1. Uso como SDK (Biblioteca)

Importe e use o `Browser` no seu projeto de automação.

```python
from browser import Browser, Settings, BrowserType, create_selector, ElementNotFoundError, SelectorType

minhas_settings: Settings = {"browser": {"headless": False}}

try:
    with Browser("meu_utilizador", BrowserType.CHROME, settings=minhas_settings) as browser:
        browser.navigate_to("https://www.google.com")
        print("Automação concluída!")
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

* **Limpar todos os perfis e sessões:**
    ```bash
    browser-core profiles clean
    ```

---

## Contribuição

Este projeto está aberto a contribuições. Sinta-se à vontade para abrir uma *issue* ou submeter um *pull request*.
