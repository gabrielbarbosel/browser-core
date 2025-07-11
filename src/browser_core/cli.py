import json
import shutil
from importlib import metadata
from pathlib import Path

import click

from .exceptions import ConfigurationError, SnapshotError, StorageEngineError
from .settings import default_settings
from .snapshots.manager import SnapshotManager
from .storage.engine import StorageEngine
from .types import BrowserType, DriverInfo
from .utils import safe_json_dumps


class CliContext:
    """Objeto para carregar e passar dependências para os comandos da CLI."""

    def __init__(self):
        try:
            self.settings = default_settings()
            self.paths = self.settings.get("paths", {})

            # Garante que os caminhos são objetos Path
            self.objects_dir = Path(self.paths.get("objects_dir"))
            self.snapshots_dir = Path(self.paths.get("snapshots_metadata_dir"))

            storage_engine = StorageEngine(objects_dir=self.objects_dir)
            self.snapshot_manager = SnapshotManager(
                snapshots_metadata_dir=self.snapshots_dir, storage_engine=storage_engine
            )
        except (SnapshotError, StorageEngineError, ConfigurationError) as e:
            click.echo(
                f"ERRO: Falha ao inicializar os gestores do browser-core: {e}", err=True
            )
            exit(1)


@click.group()
@click.version_option(
    version=metadata.version("browser-core"), prog_name="browser-core"
)
@click.pass_context
def cli(ctx: click.Context):
    """Interface de Linha de Comando para gerir o browser-core."""
    ctx.obj = CliContext()


# --- Grupo de Comandos para Snapshots ---
@cli.group()
def snapshots():
    """Comandos para gerir os snapshots de estado do navegador."""
    pass


@snapshots.command(name="create-base")
@click.argument("snapshot_id")
@click.option(
    "--browser",
    type=click.Choice([b.value for b in BrowserType], case_sensitive=False),
    default=BrowserType.CHROME.value,
    help="O tipo de navegador para este snapshot base.",
)
@click.option(
    "--version",
    default="latest",
    help="A versão do driver a ser usada (ex: 115.0.5790.170 ou 'latest').",
)
@click.pass_context
def create_base_snapshot(
    ctx: click.Context, snapshot_id: str, browser: str, version: str
):
    """
    Cria um snapshot 'raiz' (base) para um navegador específico.

    Este snapshot representa um perfil limpo e serve como ponto de partida
    para criar outros snapshots mais complexos (ex: com login).
    """
    snapshot_manager = ctx.obj.snapshot_manager
    click.echo(f"A criar snapshot base '{snapshot_id}' para {browser} v{version}...")

    driver_info: DriverInfo = {"name": browser, "version": version}
    _metadata = {
        "description": f"Snapshot base para um perfil limpo do {browser.capitalize()} v{version}.",
        "created_by": "cli",
    }

    try:
        snapshot_manager.create_base_snapshot(snapshot_id, driver_info, _metadata)
        click.secho(f"Snapshot base '{snapshot_id}' criado com sucesso!", fg="green")
        click.echo(
            "Agora pode usá-lo como 'base_snapshot_id' para criar novos snapshots."
        )
    except SnapshotError as e:
        click.secho(f"Erro ao criar snapshot: {e}", fg="red", err=True)


@snapshots.command(name="list")
@click.pass_context
def list_snapshots(ctx: click.Context):
    """Lista todos os snapshots disponíveis."""
    snapshots_dir = ctx.obj.snapshots_dir

    if not snapshots_dir.exists() or not any(snapshots_dir.glob("*.json")):
        click.echo(f"Nenhum snapshot encontrado em '{snapshots_dir}'.")
        click.echo(
            f"Dica: Crie um snapshot base com 'browser-core snapshots create-base <ID>'"
        )
        return

    click.echo(f"Snapshots encontrados em: {snapshots_dir}")
    for snapshot_file in sorted(snapshots_dir.glob("*.json")):
        try:
            data = json.loads(snapshot_file.read_text(encoding="utf-8"))
            parent = data.get("parent_id") or "--- (Base)"
            driver = data.get("base_driver", {}).get("name", "N/A")
            version = data.get("base_driver", {}).get("version", "N/A")
            click.echo(
                f"- ID: {data['id']:<30} | Pai: {parent:<30} | Driver: {driver} v{version}"
            )
        except (json.JSONDecodeError, KeyError):
            click.echo(
                f"[AVISO] Arquivo de snapshot mal formado ou incompleto: {snapshot_file.name}",
                err=True,
            )


@snapshots.command(name="inspect")
@click.argument("snapshot_id")
@click.pass_context
def inspect_snapshot(ctx: click.Context, snapshot_id: str):
    """Exibe os metadados completos de um snapshot específico."""
    snapshot_manager = ctx.obj.snapshot_manager
    data = snapshot_manager.get_snapshot_data(snapshot_id)
    if not data:
        click.echo(f"Erro: Snapshot com ID '{snapshot_id}' não encontrado.", err=True)
        return

    click.echo(safe_json_dumps(data, indent=2))


# --- Grupo de Comandos para o Armazenamento ---
@cli.group()
def storage():
    """Comandos para gerir o armazenamento de objetos e caches."""
    pass


@storage.command(name="clean")
@click.option("--force", is_flag=True, help="Executa a limpeza sem pedir confirmação.")
@click.pass_context
def clean_storage(ctx: click.Context, force: bool):
    """
    Remove TODOS os artefatos do browser-core (snapshots, objetos, logs).

    Esta é uma operação destrutiva e irreversível.
    """
    paths = ctx.obj.paths
    # Define todos os caminhos que devem ser considerados para limpeza.
    # O filtro subsequente cuidará dos que não existem ou não estão configurados.
    potential_dirs_to_clean = [
        paths.get("objects_dir"),
        paths.get("snapshots_metadata_dir"),
        paths.get("tasks_logs_dir"),
        paths.get("driver_cache_dir"),
    ]
    # Converte para Path apenas os caminhos definidos.
    dirs_to_clean = [Path(p) for p in potential_dirs_to_clean if p]

    click.echo("Os seguintes diretórios e todo o seu conteúdo serão APAGADOS:")
    for d in dirs_to_clean:
        if d.exists():
            click.echo(f"- {d}")

    if not force:
        if not click.confirm("\nTem a CERTEZA de que quer continuar?"):
            click.echo("Operação cancelada.")
            return

    for dir_path in dirs_to_clean:
        if dir_path.exists():
            try:
                shutil.rmtree(dir_path)
                click.echo(f"Diretório '{dir_path}' limpo com sucesso.")
            except OSError as e:
                click.echo(f"Erro ao apagar o diretório '{dir_path}': {e}", err=True)

    click.echo("\nLimpeza concluída.")


if __name__ == "__main__":
    cli()
