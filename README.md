# Browser-Core

[![PyPI version](https://badge.fury.io/py/browser-core.svg)](https://badge.fury.io/py/browser-core)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Browser-Core** é uma plataforma de orquestração de ambientes de navegador, projetada para automação web em escala, com
foco em eficiência, isolamento e reprodutibilidade total.

---

## Visão Geral

O Browser-Core evoluiu de uma simples biblioteca de automação para uma plataforma de orquestração completa. Ele permite
provisionar, gerir e executar frotas de "Workers" (navegadores) em paralelo, com uma arquitetura robusta e elegante.

A base do framework é um **sistema de snapshots em camadas**, análogo ao Docker e Git, que permite criar, derivar e
reutilizar estados de navegador (como sessões com login efetuado) de forma rápida, eficiente em disco e, crucialmente, *
*100% reprodutível**.

## Conceitos Fundamentais

* **Snapshots em Camadas**: Crie "imagens" do estado do seu navegador (com cookies, `localStorage`, etc.) e derive
  outras a partir delas. Diga adeus à necessidade de repetir o login a cada execução.
* **Workers Isolados**: Execute cada tarefa em um "Worker" limpo e isolado, instanciado a partir de um snapshot,
  garantindo que execuções paralelas não interfiram umas nas outras.
* **API Fluente e Intuitiva**: Interaja com os elementos da página de forma declarativa e legível com o método
  `worker.get()`, que torna a automação mais limpa e de fácil manutenção.
* **Gestão Automática de Drivers**: O `browser-core` faz o download e gere o cache da versão exata do WebDriver
  necessária para cada snapshot, eliminando problemas de compatibilidade.
* **CLI Integrada**: Uma ferramenta de linha de comando para listar, inspecionar e gerir seus snapshots e o
  armazenamento de objetos.

---

## Instalação

A forma recomendada de instalar o `browser-core` é através do PyPI:

```bash
pip install browser-core
```

---

## Um Fluxo de Trabalho Moderno

O uso do `browser-core` é dividido em duas fases lógicas: a **preparação de ambientes** (criação de snapshots) e a *
*execução de tarefas**.

### Fase 1: Criar um Snapshot Reutilizável

Primeiro, você cria um estado base. O caso de uso mais comum é um snapshot com uma sessão de usuário já autenticada.
Este processo é feito uma única vez e automatizado pelo `WorkforceManager`.

```python
# scripts/create_login_snapshot.py
import os
from browser_core import WorkforceManager, Worker, create_selector, ConfigurationError
from browser_core.types import SelectorType

# De preferência, carregue credenciais como variáveis de ambiente
# Nunca coloque senhas ou dados sensíveis diretamente no código.
# Antes de executar, defina as variáveis no seu terminal:
# export APP_USER="meu_usuario@exemplo.com"
# export APP_PASSWORD="minha-senha-super-segura"
APP_USER = os.getenv("APP_USER")
APP_PASSWORD = os.getenv("APP_PASSWORD")


# 1. Defina a função que executa a lógica de setup
def perform_login(worker: Worker):
    """Esta função navega e realiza o login para criar o estado desejado."""
    # Valida se as credenciais foram carregadas do ambiente
    if not APP_USER or not APP_PASSWORD:
        raise ConfigurationError("As variáveis de ambiente APP_USER e APP_PASSWORD devem ser definidas.")

    worker.logger.info("Iniciando processo de login para criar o snapshot...")
    worker.navigate_to("https://app.exemplo.com/login")

    # Define os seletores de forma clara e reutilizável
    EMAIL_INPUT = create_selector("input[name='email']", SelectorType.CSS)
    PASSWORD_INPUT = create_selector("input[name='password']", SelectorType.CSS)
    LOGIN_BUTTON = create_selector("//button[text()='Entrar']", SelectorType.XPATH)

    # Utiliza a API para interagir com a página
    worker.get(EMAIL_INPUT).send_keys(APP_USER)
    worker.get(PASSWORD_INPUT).send_keys(APP_PASSWORD)
    worker.get(LOGIN_BUTTON).click()

    # Aguarda a navegação para a página de dashboard, confirmando o login
    worker.get(create_selector("#dashboard-welcome-message", SelectorType.CSS))
    worker.logger.info("Login realizado com sucesso! Estado pronto para ser capturado.")


# 2. Execute o orquestrador para criar o snapshot
def main():
    workforce = WorkforceManager()

    # Assumindo que um snapshot base para o Chrome já existe.
    # Ele pode ser criado com a CLI ou um script simples.
    BASE_SNAPSHOT = "chrome_base"  # Ex: um snapshot limpo do Chrome
    NEW_SNAPSHOT = "app_logged_in_v1"

    try:
        workforce.create_snapshot_from_task(
            base_snapshot_id=BASE_SNAPSHOT,
            new_snapshot_id=NEW_SNAPSHOT,
            setup_function=perform_login,
            metadata={
                "description": "Sessão autenticada no app.exemplo.com.",
                "user": APP_USER
            }
        )
        print(f"\nSnapshot '{NEW_SNAPSHOT}' criado com sucesso!")
    except Exception as e:
        print(f"\n[!!!] Falha ao criar o snapshot: {e}")


if __name__ == "__main__":
    main()
```

### Fase 2: Executar Tarefas Usando o Snapshot

Com o snapshot `app_logged_in_v1` pronto, você pode executar inúmeras tarefas que dependem de um usuário autenticado, de
forma massivamente paralela, e **sem nunca mais precisar fazer login**.

```python
# scripts/run_report_tasks.py
from browser_core import WorkforceManager, Worker, create_selector, default_settings
from browser_core.types import SelectorType


# --- Lógica da Tarefa ---
# Esta função já parte do princípio que o worker está logado.
def extract_report_data(worker: Worker, report_id: str):
    worker.logger.info(f"Iniciando extração para o relatório: {report_id}")
    worker.navigate_to(f"https://app.exemplo.com/reports/{report_id}")

    REPORT_TABLE = create_selector("#report-data-table", SelectorType.CSS)

    # A simples chamada a .text força o worker a aguardar o elemento aparecer
    table_data = worker.get(REPORT_TABLE).text

    # ... aqui você processaria os dados da tabela ...
    processed_data = {"report_id": report_id, "content_length": len(table_data)}
    worker.logger.info(f"Extração do relatório '{report_id}' concluída.")
    return processed_data


# --- Lógica de Setup do Worker (opcional) ---
# Função executada uma vez por worker antes de ele começar a processar os itens.
def worker_session_setup(worker: Worker) -> bool:
    worker.logger.info(f"Worker {worker.logger.extra['task_id']} está pronto e online.")
    # Poderia, por exemplo, navegar para uma página inicial comum.
    # Retornar True indica que o setup foi bem-sucedido.
    return True


# --- Execução em Lote ---
def main():
    settings = default_settings()
    # Para depuração, é útil desativar o modo headless
    settings["browser"]["headless"] = False

    workforce = WorkforceManager(settings)

    # Lista de tarefas a serem executadas
    reports_to_process = ["Q1-2024", "Q2-2024", "Q3-2024", "Q4-2024"]

    try:
        results = workforce.run_tasks_in_squad(
            squad_size=2,  # Executa 2 navegadores em paralelo
            base_snapshot_id="app_logged_in_v1",  # Usa o estado de login
            task_items=reports_to_process,
            worker_setup_function=worker_session_setup,
            item_processing_function=extract_report_data
        )
        print("\n--- Processamento Concluído ---")
        for res in results:
            print(res)

    except Exception as e:
        print(f"\n[!!!] Uma falha ocorreu durante a execução do esquadrão: {e}")


if __name__ == "__main__":
    main()
```

### Uso da CLI

Use o comando `browser-core` no seu terminal para gerir o ecossistema.

* **Listar snapshots disponíveis:**
    ```bash
    browser-core snapshots list
    ```

* **Inspecionar os detalhes de um snapshot:**
    ```bash
    browser-core snapshots inspect app_logged_in_v1
    ```

* **Limpar todo o armazenamento (cuidado, operação destrutiva!):**
    ```bash
    browser-core storage clean
    ```

---

## Desenvolvimento e Contribuição

Se pretende contribuir para o `browser-core`, siga estes passos para configurar seu ambiente.

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/gabrielbarbosel/browser-core.git
   cd browser-core
   ```

2. **Crie e ative um ambiente virtual:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # No Linux/macOS
   # .venv\Scripts\activate    # No Windows
   ```

3. **Instale o projeto em modo "editável":**
   ```bash
   pip install -e .
    