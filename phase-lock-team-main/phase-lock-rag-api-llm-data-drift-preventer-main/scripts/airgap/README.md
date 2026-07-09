# Air-Gapped Bundle Builder

Builds an offline artifact bundle for enterprise air-gapped deployments.

## Outputs

- images.txt: OCI image list for mirroring
- file-list.txt: canonical artifact list included in the bundle
- Helm chart package (`.tgz`) when `helm` is available
- sbom.spdx.json: SBOM (full via `syft`, placeholder otherwise)
- provenance.json: build metadata (timestamp, git SHA, image/chart refs)
- manifest.sha256: checksums of key artifacts
- manifest.sha256.sig: optional cosign signature
- manifest.pub: optional copied public key when key-based signing is used

## Usage

```bash
bash scripts/airgap/build_offline_bundle.sh
bash scripts/airgap/verify_offline_bundle.sh dist/airgap
```

Optional variables:

- `OUT_DIR`
- `IMAGE`
- `CHART_DIR`
- `COSIGN_KEY_PATH`
- `COSIGN_PUB_PATH`
