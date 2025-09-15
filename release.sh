#!/bin/bash
#
# Sobe uma nova versão do pacote. Faz a limpeza, build e upload.
# Uso: ./release.sh
#

# Se algo der errado, o script para. Essencial pra não subir o pacote quebrado.
set -e

echo ">> Limpando builds antigos..."
rm -rf dist/ build/ *.egg-info/

echo ">> Gerando os pacotes da nova versão..."
python -m build

echo ">> Validando os pacotes com Twine..."
twine check dist/*

echo ">> Publicando no repositório..."
twine upload -- dist/*

echo
echo "Feito! Nova versão no ar. ✨"
