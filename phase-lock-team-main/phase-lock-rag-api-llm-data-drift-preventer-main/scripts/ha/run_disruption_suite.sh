#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-default}"
GATEWAY_LABEL="${GATEWAY_LABEL:-app=phase-lock-gateway}"
GATEWAY_DEPLOYMENT="${GATEWAY_DEPLOYMENT:-phase-lock-gateway}"
DEPENDENCY_DEPLOYMENT="${DEPENDENCY_DEPLOYMENT:-}"
DEPENDENCY_REPLICAS="${DEPENDENCY_REPLICAS:-1}"

log() {
  printf '[ha-suite] %s\n' "$*"
}

require() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "missing required command: $1"
    exit 1
  fi
}

wait_rollout() {
  local deployment="$1"
  kubectl -n "$NAMESPACE" rollout status "deployment/${deployment}" --timeout=300s
}

select_node_for_gateway() {
  kubectl -n "$NAMESPACE" get pods -l "$GATEWAY_LABEL" -o jsonpath='{.items[0].spec.nodeName}'
}

node_drain_test() {
  log "starting node drain test"
  local node
  node="$(select_node_for_gateway)"
  if [[ -z "$node" ]]; then
    log "no gateway pod found for node drain test"
    return 1
  fi

  kubectl drain "$node" --ignore-daemonsets --delete-emptydir-data --force --grace-period=30 --timeout=5m
  wait_rollout "$GATEWAY_DEPLOYMENT"
  kubectl uncordon "$node"
  log "node drain test completed"
}

pod_eviction_test() {
  log "starting pod eviction test"
  local pod
  pod="$(kubectl -n "$NAMESPACE" get pods -l "$GATEWAY_LABEL" -o jsonpath='{.items[0].metadata.name}')"
  if [[ -z "$pod" ]]; then
    log "no gateway pod found for eviction test"
    return 1
  fi

  kubectl -n "$NAMESPACE" delete pod "$pod" --grace-period=0 --force
  wait_rollout "$GATEWAY_DEPLOYMENT"
  log "pod eviction test completed"
}

dependency_outage_test() {
  if [[ -z "$DEPENDENCY_DEPLOYMENT" ]]; then
    log "DEPENDENCY_DEPLOYMENT is empty; skipping dependency outage test"
    return 0
  fi

  log "starting dependency outage test for deployment/${DEPENDENCY_DEPLOYMENT}"
  kubectl -n "$NAMESPACE" scale "deployment/${DEPENDENCY_DEPLOYMENT}" --replicas=0
  wait_rollout "$GATEWAY_DEPLOYMENT"
  kubectl -n "$NAMESPACE" scale "deployment/${DEPENDENCY_DEPLOYMENT}" --replicas="$DEPENDENCY_REPLICAS"
  kubectl -n "$NAMESPACE" rollout status "deployment/${DEPENDENCY_DEPLOYMENT}" --timeout=300s
  log "dependency outage test completed"
}

main() {
  require kubectl

  log "suite configuration namespace=${NAMESPACE} gateway_label=${GATEWAY_LABEL} gateway_deployment=${GATEWAY_DEPLOYMENT}"
  node_drain_test
  pod_eviction_test
  dependency_outage_test
  log "all disruption tests completed"
}

main "$@"
