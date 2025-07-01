# Define o sistema de gestão de perfis de utilizador.
#
# Este módulo é responsável por criar, carregar e gerir perfis
# persistentes para os utilizadores da automação, que contêm as sessões
# e os dados persistentes do navegador.

import shutil
import threading
from datetime import datetime
from pathlib import Path

from .exceptions import ProfileError
from .types import FilePath, ProfileConfig, ProfileData, ProfilePathConfig
from .utils import ensure_directory, safe_json_dumps, safe_json_loads


class UserProfileManager:
    """
    Gere perfis de utilizador persistentes para a automação do navegador.

    Cada perfil de utilizador é vinculado a um `username` e serve como um
    contentor para os dados do navegador (cookies, etc.) e para todas as
    suas sessões de automação.

    A estrutura de diretórios gerida por esta classe é:
    `base_profiles_dir/`
    `└── {profile_id}/`
        `├── browser_profile/`
        `├── sessions/`
        `└── profile_metadata.json`
    """

    def __init__(
            self,
            username: str,
            base_profiles_dir: FilePath,
            settings: ProfileConfig,
    ):
        """
        Inicializa o gestor de perfis.

        Args:
            username: O nome de utilizador para o qual o perfil será criado/gerido.
            base_profiles_dir: O diretório base onde todos os perfis serão armazenados.
            settings: O dicionário de configuração para os perfis.
        """
        if not base_profiles_dir:
            raise ValueError("O 'base_profiles_dir' não pode ser nulo ou vazio.")

        self.username = username
        self.settings = settings
        self.base_profiles_dir = Path(base_profiles_dir)

        self.profile_id: str = self._generate_profile_id(username)
        self.paths: ProfilePathConfig = self._create_profile_structure()

        self._profile_data: ProfileData = {
            "profile_id": self.profile_id,
            "username": username,
            "created_at": datetime.now().isoformat(),
            "last_accessed": datetime.now().isoformat(),
        }

        # Garante que as operações no perfil sejam thread-safe.
        self._lock = threading.RLock()

        self._load_or_create_profile()

    def _generate_profile_id(self, username: str) -> str:
        # Gera um ID seguro para ser usado em nomes de diretório.
        sanitized = "".join(c for c in username if c.isalnum() or c in "._-")
        return f"user_{sanitized}"

    def _create_profile_structure(self) -> ProfilePathConfig:
        # Cria a estrutura de diretórios necessária para o perfil.
        profile_dir = self.base_profiles_dir / self.profile_id
        paths: ProfilePathConfig = {
            "profile_dir": profile_dir,
            "browser_profile_dir": profile_dir / "browser_profile",
            "sessions_dir": profile_dir / "sessions",
        }
        for path in paths.values():
            ensure_directory(path)
        return paths

    def _load_or_create_profile(self) -> None:
        # Carrega os metadados de um perfil existente ou cria um novo ficheiro.
        profile_metadata_file = self.paths["profile_dir"] / "profile_metadata.json"
        try:
            if profile_metadata_file.exists():
                with open(profile_metadata_file, "r", encoding="utf-8") as f:
                    existing_data = safe_json_loads(f.read())
                if existing_data:
                    self._profile_data.update(existing_data)

            self._profile_data["last_accessed"] = datetime.now().isoformat()
            self._save_profile_data()
        except Exception as e:
            raise ProfileError(f"Falha ao carregar ou criar o perfil: {e}", original_error=e)

    def _save_profile_data(self) -> None:
        # Salva os metadados do perfil no ficheiro JSON, de forma thread-safe.
        profile_metadata_file = self.paths["profile_dir"] / "profile_metadata.json"
        try:
            with self._lock:
                json_data = safe_json_dumps(self._profile_data, indent=2)
                with open(profile_metadata_file, "w", encoding="utf-8") as f:
                    f.write(json_data)
        except Exception as e:
            raise ProfileError(f"Falha ao salvar os dados do perfil: {e}", original_error=e)

    def create_session_directory(self, session_id: str) -> Path:
        """
        Cria um diretório para uma nova sessão dentro da estrutura deste perfil.

        Args:
            session_id: O ID da nova sessão a ser criada.

        Returns:
            O caminho (Path) para o diretório da nova sessão.
        """
        session_dir = self.paths["sessions_dir"] / session_id
        ensure_directory(session_dir)
        return session_dir

    def get_browser_profile_path(self) -> Path:
        """Retorna o caminho para o diretório de perfil do navegador."""
        if self.settings.get("persistent_browser_profile", True):
            return self.paths["browser_profile_dir"]
        return None

    def cleanup_old_sessions(self) -> None:
        """Exclui diretórios de sessões antigas com base na configuração."""
        cleanup_days = self.settings.get("auto_cleanup_days", False)
        if not cleanup_days:
            return

        if cleanup_days <= 0:
            return

        cutoff_date = datetime.now().timestamp() - (cleanup_days * 86_400)
        for session_dir in self.paths["sessions_dir"].iterdir():
            if not session_dir.is_dir():
                continue

            try:
                if session_dir.stat().st_mtime < cutoff_date:
                    shutil.rmtree(session_dir)
            except (OSError, FileNotFoundError):
                # Ignora erros se o ficheiro for removido por outro processo
                pass
