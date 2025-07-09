# Define o motor de armazenamento de baixo nível para a gestão de snapshots.
#
# Este módulo implementa o StorageEngine, que utiliza uma abordagem de
# armazenamento endereçável por conteúdo (semelhante ao Git) para gerir
# os arquivos de perfis de navegador de forma extremamente eficiente.

import hashlib
import shutil
from pathlib import Path
from typing import Dict, List, Tuple

from ..exceptions import StorageEngineError
from ..types import FilePath, ObjectHash, RelativePath, SnapshotDelta
from ..utils import ensure_directory


class StorageEngine:
    """
    Motor de armazenamento baseado em conteúdo (content-addressable storage).

    É responsável por três operações críticas:
    1.  Calcular a diferença (delta) entre dois estados de diretório.
    2.  Armazenar cada arquivo (objeto) de forma única, usando seu hash de
        conteúdo como identificador, eliminando redundância.
    3.  Materializar um diretório de trabalho funcional, compondo uma
        sequência de deltas para reconstruir um estado específico.
    """

    def __init__(self, objects_dir: FilePath):
        """
        Inicializa o motor de armazenamento.

        Args:
            objects_dir: O diretório raiz onde os objetos (arquivos com hash)
                         serão armazenados. Ex: '.../browser-core-output/objects'.
        """
        self.objects_dir = ensure_directory(objects_dir)

    def _hash_file(self, file_path: Path) -> ObjectHash:
        """
        Calcula o hash SHA256 do conteúdo de um arquivo.

        Args:
            file_path: O caminho para o arquivo a ser processado.

        Returns:
            O hash SHA256 em formato hexadecimal.
        """
        h = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):
                    h.update(chunk)
            return h.hexdigest()
        except IOError as e:
            raise StorageEngineError(
                f"Não foi possível ler o arquivo para calcular o hash: {file_path}",
                original_error=e
            )

    def store_object_from_path(self, source_path: Path) -> ObjectHash:
        """
        Armazena um arquivo do sistema de arquivos no diretório de objetos.

        Se um objeto com o mesmo conteúdo já existe, ele não é armazenado
        novamente, economizando espaço. O método é idempotente.

        Args:
            source_path: O caminho do arquivo de origem a ser armazenado.

        Returns:
            O hash SHA256 do conteúdo do arquivo, que serve como seu ID no
            armazenamento de objetos.
        """
        file_hash = self._hash_file(source_path)
        object_path = self.objects_dir / file_hash

        if not object_path.exists():
            try:
                shutil.copy(source_path, object_path)
            except IOError as e:
                raise StorageEngineError(
                    f"Falha ao copiar o arquivo para o armazenamento de objetos: {source_path}",
                    original_error=e
                )

        return file_hash

    def calculate_delta(self, base_dir: Path, new_dir: Path) -> Dict[RelativePath, ObjectHash]:
        """
        Calcula a diferença (delta) entre um diretório base e um novo estado.

        Compara o 'new_dir' com o 'base_dir' e retorna um dicionário
        mapeando os caminhos relativos para os hashes de conteúdo dos arquivos
        que foram adicionados ou modificados.

        Args:
            base_dir: O diretório que representa o estado "antigo" ou "pai".
            new_dir: O diretório que representa o estado "novo" ou "filho".

        Returns:
            Um dicionário representando o "diff" entre os diretórios.
        """
        delta: Dict[RelativePath, ObjectHash] = {}

        # Mapeia arquivos base: (caminho_relativo) -> (tamanho, hash)
        base_files: Dict[RelativePath, Tuple[int, ObjectHash]] = {}
        for p in base_dir.rglob("*"):
            if p.is_file():
                base_files[str(p.relative_to(base_dir))] = (p.stat().st_size, self._hash_file(p))

        for new_file in new_dir.rglob("*"):
            if not new_file.is_file():
                continue

            relative_path = str(new_file.relative_to(new_dir))
            new_size = new_file.stat().st_size

            # Compara metadados primeiro
            if relative_path in base_files and base_files[relative_path][0] == new_size:
                # Se o tamanho for o mesmo, compare os hashes (como verificação final)
                if base_files[relative_path][1] == self._hash_file(new_file):
                    continue  # O arquivo não mudou, pule.

            # Se o arquivo for novo, modificado, ou o hash diferir
            new_hash = self.store_object_from_path(new_file)
            delta[relative_path] = new_hash

        return delta

    def materialize(self, deltas: List[Dict[RelativePath, ObjectHash]], target_dir: Path) -> None:
        """
        Materializa um estado final aplicando uma sequência de deltas sobre um diretório.

        Constrói (ou reconstrói) um diretório de trabalho 'target_dir' ao
        mesclar os deltas em ordem. Deltas mais recentes sobrescrevem os
        arquivos das camadas anteriores.

        Args:
            deltas: Uma lista de dicionários de delta, do mais antigo (base)
                    para o mais novo.
            target_dir: O diretório de destino onde o perfil será construído.
                        O conteúdo existente será removido.
        """
        if target_dir.exists():
            shutil.rmtree(target_dir)
        ensure_directory(target_dir)

        # Mescla todos os deltas em um único dicionário de estado final.
        # A ordem garante que deltas posteriores (mais novos) sobrescrevam os anteriores.
        final_state: Dict[RelativePath, ObjectHash] = {}
        for delta in deltas:
            final_state.update(delta)

        # Constrói o diretório de trabalho a partir do estado final.
        for rel_path, obj_hash in final_state.items():
            object_path = self.objects_dir / obj_hash
            destination_path = target_dir / rel_path

            if not object_path.exists():
                raise StorageEngineError(
                    f"Objeto '{obj_hash}' referenciado por '{rel_path}' não foi "
                    "encontrado no armazenamento. O repositório pode estar corrompido."
                )

            # Garante que a estrutura de subdiretórios exista.
            ensure_directory(destination_path.parent)
            try:
                # Copia o objeto do armazenamento para o diretório de trabalho.
                shutil.copy(object_path, destination_path)
            except IOError as e:
                raise StorageEngineError(
                    f"Falha ao materializar o objeto '{obj_hash}' em '{destination_path}'",
                    original_error=e
                )
