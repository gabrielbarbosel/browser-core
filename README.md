# Browser-Core

[![Versão PyPI](https://badge.fury.io/py/browser-core.svg)](https://badge.fury.io/py/browser-core)
[![Licença: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Browser-Core** é uma plataforma completa para orquestração de navegadores. O projeto nasceu para simplificar
automações em larga escala, garantindo isolamento total dos ambientes e reprodutibilidade dos estados de cada sessão.

Neste documento você encontrará uma visão detalhada de como funciona o framework, dicas de utilização e todos os
recursos disponíveis.

## Sumário

1. [Introdução](#introdução)
2. [Instalação](#instalação)
3. [Conceitos Fundamentais](#conceitos-fundamentais)
4. [Fluxo de Trabalho](#fluxo-de-trabalho)
5. [Exemplos de Uso](#exemplos-de-uso)
6. [Comandos da CLI](#comandos-da-cli)
7. [Dicas Avançadas](#dicas-avançadas)
8. [Contribuindo](#contribuindo)
9. [Licença](#licença)

---

## Introdução

Automatizar tarefas de navegador exige controle refinado sobre perfis, versões de drivers e paralelismo. O *
*Browser-Core** abstrai essa complexidade oferecendo:

- Camadas de snapshots reutilizáveis para capturar o estado exato do navegador (cookies, localStorage, extensões, etc.).
- Workers isolados que partem desses snapshots e executam tarefas independentes em paralelo.
- Integração transparente com Selenium e Playwright, bastando escolher o motor desejado.
- Uma CLI poderosa para manipular snapshots e gerenciar o armazenamento local.

Com esses componentes é possível escalar automações para centenas de execuções mantendo total rastreabilidade.

---

## Instalação

A instalação mais simples é via [PyPI](https://pypi.org/project/browser-core/):

```bash
pip install browser-core
```

Isso disponibiliza a biblioteca para uso em scripts Python e também instala a ferramenta de linha de comando
`browser-core`.

---

## Conceitos Fundamentais

**Snapshots em Camadas**
: Permitem criar "imagens" do navegador e derivar novos estados a partir delas. Assim você registra um login ou
configuração apenas uma vez e reutiliza em milhares de execuções.

**Workers Isolados**
: Cada worker é iniciado a partir de um snapshot específico e executa a tarefa em um perfil totalmente separado dos
demais.

**Drivers Gerenciados**
: O projeto baixa e armazena a versão exata do WebDriver para o navegador escolhido, evitando incompatibilidades em
diferentes máquinas.

**Arquitetura Multi‑engine**
: Tanto Selenium quanto Playwright podem ser utilizados com a mesma API de alto nível.

**CLI Integrada**
: Inclui comandos para criar snapshots base, listar estados existentes, inspecionar metadados e limpar todos os
artefatos.

---

## Fluxo de Trabalho

O uso típico divide-se em duas fases: criação dos snapshots e execução das tarefas.

### 1. Preparar os Snapshots

1. **Criar o Snapshot Base** – Perfil limpo com a versão de navegador desejada:

   ```bash
   browser-core snapshots create-base chrome-base
   ```

2. **Derivar um Snapshot com Estado** – Por exemplo, realizar login em um site e salvar esse estado:

   ```python
   # scripts/create_login_snapshot.py
   import os
   from browser_core import Orchestrator, Worker, create_selector
   from browser_core.types import SelectorType
   
   APP_USER = os.getenv("APP_USER")
   APP_PASSWORD = os.getenv("APP_PASSWORD")

   def perform_login(worker: Worker):
       """Função que executa a lógica de login."""

       worker.navigate_to("https://app.exemplo.com/login")
       worker.get(create_selector("input[name='email']", SelectorType.CSS)).send_keys(APP_USER)
       worker.get(create_selector("input[name='password']", SelectorType.CSS)).send_keys(APP_PASSWORD)
       worker.get(create_selector("button[type='submit']", SelectorType.CSS)).click()
       worker.get(create_selector("#dashboard", SelectorType.CSS)) # Aguarda o carregamento

   def main():
       """Função principal para orquestrar a criação do snapshot."""
       Orchestrator().create_snapshot_from_task(
           base_snapshot_id="chrome-base",
           new_snapshot_id="app_logged_in",
           setup_function=perform_login,
           metadata={"description": "Sessão autenticada"}
       )
       print("Snapshot 'app_logged_in' criado com sucesso!")

   if __name__ == "__main__":
       main()
   ```

### 2. Executar Tarefas em Paralelo

Com o snapshot `app_logged_in` pronto, processe uma série de itens utilizando vários workers:

```python
# scripts/run_tasks.py
from browser_core import Orchestrator, Worker, create_selector, default_settings
from browser_core.types import SelectorType


def fetch_report(worker: Worker, report_id: str):
    """Função que cada worker executará para buscar um relatório."""
    worker.navigate_to(f"https://app.exemplo.com/reports/{report_id}")
    table = worker.get(create_selector("#report-data-table", SelectorType.CSS)).text
    return {"report_id": report_id, "length": len(table)}

def main():
    """Função principal para executar as tarefas em paralelo."""
    REPORTS = ["Q1-2024", "Q2-2024", "Q3-2024", "Q4-2024"]
    settings = default_settings()
    settings["browser"]["headless"] = True

    results = Orchestrator(settings).run_tasks_in_squad(
        squad_size=2,
        base_snapshot_id="app_logged_in",
        task_items=REPORTS,
        worker_setup_function=lambda w: True,  # Função de setup simples
        item_processing_function=fetch_report,
    )
    print(results)

if __name__ == "__main__":
    main()
```

---

## Exemplos de Uso

O exemplo acima demonstra a execução de tarefas em paralelo utilizando snapshots para reaproveitar o estado de login.

---

## Comandos da CLI

A ferramenta `browser-core` auxilia na criação e manutenção dos snapshots e do armazenamento:

- **Criar snapshot base**
    ```bash
    browser-core snapshots create-base <snapshot-id>
    ```

- **Listar snapshots existentes**
    ```bash
    browser-core snapshots list
    ```

- **Inspecionar um snapshot**
    ```bash
    browser-core snapshots inspect <snapshot-id>
    ```

- **Limpar armazenamento**
    ```bash
    browser-core storage clean --force
    ```

Todas as opções estão disponíveis com `browser-core --help`.

---

## Dicas Avançadas

- **Modo headless ou gráfico**: Defina `settings["browser"]["headless"]` para alternar entre execução invisível ou com
  janela aberta.
- **Uso de proxies e variáveis de ambiente**: É possível configurar proxies ou outras opções de driver diretamente nas
  definições de `Settings`.
- **Persistência de logs**: Cada execução cria uma pasta com registros detalhados em `tasks_logs_dir`, auxiliando
  depuração e auditoria.
- **Extensibilidade**: A estrutura de `Worker` e `Orchestrator` permite implementar tarefas complexas com facilidade,
  reutilizando funções comuns de manipulação de página.

---

## Contribuindo

Contribuições são bem-vindas! Para configurar o ambiente de desenvolvimento:

1. Clone o repositório:
   ```bash
   git clone https://github.com/gabrielbarbosel/browser-core.git
   cd browser-core
   ```

2. Crie um ambiente virtual:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. Instale as dependências de desenvolvimento:
   ```bash
   pip install -e ".[dev]"
   ```

4. Execute as verificações locais:
   ```bash
   black -q src
   pytest -q
   ```

---

## Licença

Distribuído sob a licença MIT. Consulte o arquivo [LICENSE](LICENSE) para mais detalhes.
