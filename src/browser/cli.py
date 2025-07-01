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
        # Instancia o DriverManager para aceder à sua lógica de download/cache.
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
    profiles_dir = Path(settings["session_output_dir"]) / "profiles"

    if not profiles_dir.exists() or not any(profiles_dir.iterdir()):
        click.echo("Nenhum perfil encontrado.")
        return

    click.echo(f"Perfis encontrados em: {profiles_dir}")
    for profile_path in profiles_dir.iterdir():
        if profile_path.is_dir():
            click.echo(f"- {profile_path.name}")


@profiles.command()
@click.option(
    "--path",
    "custom_path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Caminho para o diretório de output, se for diferente do padrão.",
)
def clean(custom_path: Path):
    """Remove todos os diretórios de perfis e sessões."""
    settings = default_settings()
    output_dir = custom_path or Path(settings["session_output_dir"])

    if not output_dir.exists() or not any(output_dir.iterdir()):
        click.echo(f"Diretório de output '{output_dir}' está vazio ou não existe. Nada a limpar.")
        return

    if click.confirm(
            f"Tem a certeza de que quer apagar TODO o conteúdo de '{output_dir}'? Esta ação é irreversível."
    ):
        try:
            shutil.rmtree(output_dir)
            click.echo(f"Diretório '{output_dir}' limpo com sucesso.")
        except OSError as e:
            cli_logger.error(f"Não foi possível apagar o diretório '{output_dir}': {e}")
            click.echo(f"Erro: Não foi possível apagar o diretório. Verifique as permissões.")


if __name__ == "__main__":
    cli()
