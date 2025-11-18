#!/usr/bin/env bash
set -euo pipefail
source ./discord/WEBHOOKS.example.env 2>/dev/null || true
: "${DISCORD_WEBHOOK_GERAL:=}"
: "${DISCORD_WEBHOOK_ATRASOS:=}"
: "${DISCORD_WEBHOOK_APROVADOS:=}"
: "${DISCORD_WEBHOOK_CHECKPOINTS:=}"

send() {
  local url="$1" msg="$2"
  [ -z "$url" ] && { echo "Webhook vazio, pulando: $msg"; return; }
  curl -s -X POST -H "Content-Type: application/json" \
    -d "{\"username\":\"LYL Bot\",\"content\":\"$msg\"}" "$url" >/dev/null \
    && echo "ok: $msg"
}
send "$DISCORD_WEBHOOK_GERAL" "✅ Canal **Geral de Lançamentos** OK"
send "$DISCORD_WEBHOOK_ATRASOS" "⚠️ Canal **Atrasos de Lançamentos** OK"
send "$DISCORD_WEBHOOK_APROVADOS" "🟩 Canal **Aprovados** OK"
send "$DISCORD_WEBHOOK_CHECKPOINTS" "📍 Canal **Checkpoints Concluídos** OK"
