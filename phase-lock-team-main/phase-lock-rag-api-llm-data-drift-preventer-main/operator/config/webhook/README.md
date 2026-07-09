# Webhook Scaffold

This directory contains admission webhook manifests for `PhaseLockGateway` lifecycle safety.

- `validating-webhook.yaml`: validates create/update requests.

The webhook server implementation is not yet included; this scaffold allows platform teams to wire cert-manager, TLS, and admission service routing as part of deployment hardening.
