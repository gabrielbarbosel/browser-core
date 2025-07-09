from pathlib import Path
from typing import Optional

from .logging import setup_task_logger
from .settings import Settings
from .types import DriverInfo
from .worker import Worker


class WorkerFactory:
    """
    Classe responsável por encapsular a lógica de criação e configuração de Workers.

    Isso reduz o acoplamento do WorkforceManager com os detalhes de implementação do Worker.
    """

    def __init__(self, settings: Settings, workforce_run_dir: Path):
        self.settings = settings
        self.workforce_run_dir = workforce_run_dir
        self.log_config = self.settings.get("logging", {})
        self.debug_artifacts_dir = self.workforce_run_dir / "debug_artifacts"
        self.debug_artifacts_dir.mkdir(exist_ok=True)

    def create_worker(
            self,
            driver_info: DriverInfo,
            profile_dir: Path,
            worker_id: str,
            consolidated_log_handler: Optional[object] = None
    ) -> Worker:
        """
        Cria, configura e retorna uma nova instância de Worker.

        Args:
            driver_info: Informações do driver a ser usado.
            profile_dir: Diretório do perfil do navegador para o worker.
            worker_id: Identificador único para o worker (ex: "worker_0").
            consolidated_log_handler: Handler de log compartilhado para logs consolidados.

        Returns:
            Uma instância de Worker pronta para ser usada.
        """
        task_logger = setup_task_logger(
            logger_name=worker_id,
            log_dir=self.workforce_run_dir,
            config=self.log_config,
            consolidated_handler=consolidated_log_handler
        )

        worker = Worker(
            driver_info=driver_info,
            profile_dir=profile_dir,
            logger=task_logger,
            settings=self.settings,
            debug_artifacts_dir=self.debug_artifacts_dir
        )
        return worker
