#!/usr/bin/env bash
# setup_dosimetria_branches.sh
#
# Cria os 4 branches de dosimetria no repositório remoto a partir do main.
# Execute UMA VEZ após clonar o repositório.
#
# Uso:
#   chmod +x scripts/setup_dosimetria_branches.sh
#   ./scripts/setup_dosimetria_branches.sh

set -euo pipefail

REMOTE="${1:-origin}"

echo "🔬 Criando branches de dosimetria (remote: $REMOTE)…"

# Garante que temos as refs remotas atualizadas antes de qualquer verificação
git fetch "$REMOTE"

_criar_branch() {
  local branch="$1"
  local base="$2"

  # Verifica se o branch já existe no remote (usando refs recém-buscadas)
  if git ls-remote --exit-code --heads "$REMOTE" "$branch" > /dev/null 2>&1; then
    echo "  ⏭  $branch já existe no remote."
    return
  fi

  git checkout -b "$branch" "$base"
  git push -u "$REMOTE" "$branch"
  git checkout -
  echo "  ✅ $branch criado."
}

# 1) modelos — base de dados e schemas Pydantic
_criar_branch feature/dosimetria-modelos "$REMOTE/main"

# 2) calculo — motor de cálculo dosimétrico
if git ls-remote --exit-code --heads "$REMOTE" feature/dosimetria-modelos > /dev/null 2>&1; then
  _criar_branch feature/dosimetria-calculo "$REMOTE/feature/dosimetria-modelos"
else
  _criar_branch feature/dosimetria-calculo "$REMOTE/main"
fi

# 3) integracao — rotas FastAPI + integração com Alexandria-AI
if git ls-remote --exit-code --heads "$REMOTE" feature/dosimetria-calculo > /dev/null 2>&1; then
  _criar_branch feature/dosimetria-integracao "$REMOTE/feature/dosimetria-calculo"
else
  _criar_branch feature/dosimetria-integracao "$REMOTE/main"
fi

# 4) interface — aba Dosimetria no frontend
if git ls-remote --exit-code --heads "$REMOTE" feature/dosimetria-integracao > /dev/null 2>&1; then
  _criar_branch feature/dosimetria-interface "$REMOTE/feature/dosimetria-integracao"
else
  _criar_branch feature/dosimetria-interface "$REMOTE/main"
fi

echo ""
echo "✅ Branches de dosimetria prontos:"
echo "   • feature/dosimetria-modelos"
echo "   • feature/dosimetria-calculo"
echo "   • feature/dosimetria-integracao"
echo "   • feature/dosimetria-interface"
echo ""
echo "Consulte docs/DOSIMETRIA-BRANCHES.md para guia completo."
