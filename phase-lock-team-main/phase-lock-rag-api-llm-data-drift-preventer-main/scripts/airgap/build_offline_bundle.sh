#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
OUT_DIR="${OUT_DIR:-${ROOT_DIR}/dist/airgap}"
IMAGE="${IMAGE:-ghcr.io/anthonyrenecastro-create/phase-lock-rag-api-llm-data-drift-preventer:latest}"
CHART_DIR="${CHART_DIR:-${ROOT_DIR}/helm/phase-lock-gateway}"
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
COSIGN_KEY_PATH="${COSIGN_KEY_PATH:-}"
COSIGN_PUB_PATH="${COSIGN_PUB_PATH:-}"

mkdir -p "$OUT_DIR"

GIT_COMMIT="unknown"
if git -C "$ROOT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  GIT_COMMIT="$(git -C "$ROOT_DIR" rev-parse HEAD 2>/dev/null || echo unknown)"
fi

echo "[airgap] writing image manifest"
printf '%s\n' "$IMAGE" >"$OUT_DIR/images.txt"

FILE_LIST="$OUT_DIR/file-list.txt"
: >"$FILE_LIST"
printf '%s\n' "images.txt" >>"$FILE_LIST"

if command -v helm >/dev/null 2>&1; then
  echo "[airgap] packaging helm chart"
  helm package "$CHART_DIR" --destination "$OUT_DIR" >/dev/null
  chart_name="$(basename "$CHART_DIR")"
  chart_pkg="$(ls -1 "$OUT_DIR"/${chart_name}-*.tgz 2>/dev/null | head -n 1 || true)"
  if [[ -n "$chart_pkg" ]]; then
    printf '%s\n' "$(basename "$chart_pkg")" >>"$FILE_LIST"
  fi
else
  echo "[airgap] helm not found; skipping chart package"
fi

if command -v syft >/dev/null 2>&1; then
  echo "[airgap] generating sbom"
  syft "$ROOT_DIR" -o spdx-json >"$OUT_DIR/sbom.spdx.json"
else
  echo "[airgap] syft not found; writing placeholder sbom"
  cat >"$OUT_DIR/sbom.spdx.json" <<'EOF'
{"spdxVersion":"SPDX-2.3","name":"phase-lock-gateway","comment":"Install syft to generate full SBOM"}
EOF
fi
printf '%s\n' "sbom.spdx.json" >>"$FILE_LIST"

cat >"$OUT_DIR/provenance.json" <<EOF
{
  "created_at_utc": "$TIMESTAMP",
  "git_commit": "$GIT_COMMIT",
  "image": "$IMAGE",
  "chart_dir": "$CHART_DIR",
  "builder": "scripts/airgap/build_offline_bundle.sh"
}
EOF
printf '%s\n' "provenance.json" >>"$FILE_LIST"

(
  cd "$OUT_DIR"
  while IFS= read -r file; do
    if [[ -f "$file" ]]; then
      sha256sum "$file"
    fi
  done < file-list.txt > manifest.sha256
)

if command -v cosign >/dev/null 2>&1; then
  if [[ -n "$COSIGN_KEY_PATH" ]]; then
    echo "[airgap] signing manifest with cosign key"
    cosign sign-blob --yes --key "$COSIGN_KEY_PATH" "$OUT_DIR/manifest.sha256" --output-signature "$OUT_DIR/manifest.sha256.sig"
    if [[ -n "$COSIGN_PUB_PATH" ]]; then
      cp "$COSIGN_PUB_PATH" "$OUT_DIR/manifest.pub"
    fi
  else
    echo "[airgap] signing manifest with keyless cosign"
    cosign sign-blob --yes "$OUT_DIR/manifest.sha256" --output-signature "$OUT_DIR/manifest.sha256.sig"
  fi
else
  echo "[airgap] cosign not found; skipping signature"
fi

echo "[airgap] bundle created at $OUT_DIR"
