# Define a fábrica para criar instâncias de Worker configuradas.
#
# A classe WorkerFactory encapsula a lógica de inicialização de um Worker,
# incluindo a configuração do seu logger específico, garantindo que o
# WorkforceManager não precise de conhecer esses detalhes de implementação.

import logging
from pathlib import Path
from typing import Optional

from .logging import setup_task_logger
from .settings import Settings
from .types import DriverInfo
from .worker import Worker


class WorkerFactory:
    """
    Uma fábrica responsável por criar e configurar instâncias de Worker.
    """

    def __init__(self, settings: Settings, workforce_run_dir: Path):
        """
        Inicializa a fábrica de workers.

        Args:
            settings: As configurações globais do framework.
            workforce_run_dir: O diretório de execução da força de trabalho,
                               usado como base para os logs.
        """
        self.settings = settings
        self.workforce_run_dir = workforce_run_dir

    def create_worker(
            self,
            driver_info: DriverInfo,
            profile_dir: Path,
            worker_id: str,
            consolidated_log_handler: Optional[logging.Handler] = None,
    ) -> Worker:
        """
        Cria, configura e retorna uma nova instância de Worker.

        Args:
            driver_info: Informações sobre o driver a ser usado.
            profile_dir: O diretório de perfil para o worker.
            worker_id: O identificador único para o novo worker.
            consolidated_log_handler: Handler opcional para um log consolidado.

        Returns:
            Uma instância de Worker pronta para ser iniciada.
        """
        # Configura o logger específico para este worker
        task_logger = setup_task_logger(
            logger_name=worker_id,
            log_dir=self.workforce_run_dir,
            config=self.settings.get("logging", {}),
            consolidated_handler=consolidated_log_handler
        )

        # Cria a instância do Worker, injetando suas dependências
        worker = Worker(
            worker_id=worker_id,
            driver_info=driver_info,
            profile_dir=profile_dir,
            logger=task_logger,
            settings=self.settings,
            debug_artifacts_dir=(self.workforce_run_dir / worker_id / "debug"),
        )
        return worker
