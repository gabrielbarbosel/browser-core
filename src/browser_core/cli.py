# Define a Interface de Linha de Comando (CLI) para o browser-core.
#
# Esta ferramenta permite gerir o ecossistema do browser-core, como
# a atualização de drivers e a manutenção de perfis de utilizador,
# diretamente a partir do terminal.

import shutil
from pathlib import Path

import click

from .drivers import DriverManager
from .logging import setup_session_logger
from .settings import default_settings
from .types import BrowserType

# Cria um logger simples para as operações da CLI.
# Usamos 'None' para session_id e um nome genérico para o utilizador.
cli_logger = setup_session_logger("cli", "cli_user", Path.cwd(), {"to_file": False})


@click.group()
def cli():
    """Interface de Linha de Comando para gerir o browser-core."""
    pass


# --- Grupo de Comandos para Drivers ---
@cli.group()
def drivers():
    """Comandos para gerir os WebDrivers."""
    pass


@drivers.command()
@click.argument("browser_name", type=click.Choice([b.value for b in BrowserType]))
def update(browser_name: str):
    """Força a verificação e atualização do driver para um navegador."""
    cli_logger.info(f"A forçar a atualização para o driver do '{browser_name}'...")
    try:
        browser_type = BrowserType(browser_name)
        manager = DriverManager(logger=cli_logger)
        manager.create_driver(browser_type, browser_config={"headless": True})
        cli_logger.info(f"Driver do '{browser_name}' verificado e/ou atualizado com sucesso.")
    except Exception as e:
        cli_logger.error(f"Ocorreu um erro ao atualizar o driver: {e}", exc_info=True)
        click.echo(f"Erro ao atualizar o driver: {e}")


# --- Grupo de Comandos para Perfis ---
@cli.group()
def profiles():
    """Comandos para gerir os perfis de utilizador."""
    pass


@profiles.command(name="list")
def list_profiles():
    """Lista todos os perfis de utilizador existentes."""
    settings = default_settings()
    # CORREÇÃO: Lê o caminho a partir do dicionário 'paths'
    paths_config = settings.get("paths", {})
    profiles_dir = Path(paths_config.get("profiles_base_dir"))

    if not profiles_dir.exists() or not any(profiles_dir.iterdir()):
        click.echo(f"Nenhum perfil encontrado em '{profiles_dir}'.")
        return

    click.echo(f"Perfis encontrados em: {profiles_dir}")
    for profile_path in profiles_dir.iterdir():
        if profile_path.is_dir():
            click.echo(f"- {profile_path.name}")


@profiles.command()
@click.option(
    "--path",
    "custom_path",
    type=click.Path(file_okay=False, path_type=Path),
    help="Ignora os caminhos padrão e apaga o diretório especificado.",
)
def clean(custom_path: Path):
    """Remove todos os diretórios de perfis e sessões."""
    settings = default_settings()
    paths_config = settings.get("paths", {})

    # Obtém os dois diretórios relevantes das configurações
    dirs_to_clean = []
    if custom_path:
        # Se um caminho personalizado for fornecido, limpa apenas ele
        dirs_to_clean.append(custom_path)
        click.echo(f"Alvo da limpeza: diretório personalizado '{custom_path}'")
    else:
        # Caso contrário, usa os caminhos padrão de perfis e sessões
        profiles_base_dir = Path(paths_config.get("profiles_base_dir"))
        sessions_base_dir = Path(paths_config.get("sessions_base_dir"))
        dirs_to_clean.extend([profiles_base_dir, sessions_base_dir])
        click.echo(f"Alvos da limpeza: '{profiles_base_dir}' e '{sessions_base_dir}'")

    found_dirs = [d for d in dirs_to_clean if d.exists() and any(d.iterdir())]

    if not found_dirs:
        click.echo("Nenhum diretório com conteúdo encontrado. Nada a limpar.")
        return

    if click.confirm(
            f"Tem a certeza de que quer apagar TODO o conteúdo dos diretórios acima? Esta ação é irreversível."
    ):
        for dir_path in found_dirs:
            try:
                shutil.rmtree(dir_path)
                click.echo(f"Diretório '{dir_path}' limpo com sucesso.")
            except OSError as e:
                cli_logger.error(f"Não foi possível apagar o diretório '{dir_path}': {e}")
                click.echo(f"Erro: Não foi possível apagar '{dir_path}'. Verifique as permissões.")


if __name__ == "__main__":
    cli()
