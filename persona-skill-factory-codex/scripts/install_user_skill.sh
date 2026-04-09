#!/usr/bin/env bash
set -euo pipefail
slug="${1:-}"
if [[ -z "$slug" ]]; then
  echo "用法: ./install_user_skill.sh livermore"
  exit 1
fi
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
src="$repo_root/.agents/skills/$slug"
dst="$HOME/.agents/skills/$slug"
if [[ ! -d "$src" ]]; then
  echo "找不到源 skill: $src"
  exit 1
fi
mkdir -p "$HOME/.agents/skills"
rm -rf "$dst"
cp -R "$src" "$dst"
echo "已安装到: $dst"
echo "重启 Codex 后可用。"
