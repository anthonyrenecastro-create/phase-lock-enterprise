#!/usr/bin/env bash
set -euo pipefail

BUNDLE_DIR="${1:-}"
if [[ -z "$BUNDLE_DIR" ]]; then
  echo "usage: $0 <bundle_dir>" >&2
  exit 2
fi

if [[ ! -d "$BUNDLE_DIR" ]]; then
  echo "bundle dir not found: $BUNDLE_DIR" >&2
  exit 2
fi

required=(file-list.txt manifest.sha256 provenance.json images.txt sbom.spdx.json)
for file in "${required[@]}"; do
  if [[ ! -f "$BUNDLE_DIR/$file" ]]; then
    echo "missing required file: $file" >&2
    exit 1
  fi
done

(
  cd "$BUNDLE_DIR"
  sha256sum -c manifest.sha256
)

if [[ -f "$BUNDLE_DIR/manifest.sha256.sig" ]]; then
  if ! command -v cosign >/dev/null 2>&1; then
    echo "cosign signature found but cosign command is unavailable" >&2
    exit 1
  fi

  if [[ -f "$BUNDLE_DIR/manifest.pub" ]]; then
    cosign verify-blob --key "$BUNDLE_DIR/manifest.pub" --signature "$BUNDLE_DIR/manifest.sha256.sig" "$BUNDLE_DIR/manifest.sha256"
  else
    echo "manifest signature exists without manifest.pub; skipping cryptographic verification"
  fi
fi

echo "offline bundle verification passed"
