#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)/.."
cd "$ROOT_DIR"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
REPORT_DIR="${REPORT_DIR:-$ROOT_DIR/dist/release-governance/$TIMESTAMP}"
DRY_RUN="${DRY_RUN:-0}"
AIRGAP_BUNDLE_DIR="$REPORT_DIR/airgap-bundle"
ROLLOUT_PLAN_PATH="${ROLLOUT_PLAN_PATH:-docs/release-rollout-waves.json}"

mkdir -p "$REPORT_DIR"

TEST_STATUS="failed"
HELM_STATUS="failed"
AIRGAP_STATUS="failed"
AIRGAP_VERIFY_STATUS="failed"
PLAN_STATUS="failed"
ROLLOUT_WAVES_STATUS="failed"

run_and_capture() {
	local name="$1"
	shift

	local logfile="$REPORT_DIR/${name}.log"
	echo "[governance] running ${name}"
	if "$@" >"$logfile" 2>&1; then
		echo "[governance] ${name} passed"
		return 0
	fi
	echo "[governance] ${name} failed (see $logfile)"
	return 1
}

if [[ "$DRY_RUN" == "1" ]]; then
	echo "[governance] DRY_RUN=1, writing placeholder outputs"
	printf 'dry run\n' >"$REPORT_DIR/tests.log"
	printf 'dry run\n' >"$REPORT_DIR/helm-template.yaml"
	printf 'dry run\n' >"$REPORT_DIR/airgap.log"
	printf 'dry run\n' >"$REPORT_DIR/airgap-verify.log"
	printf 'dry run\n' >"$REPORT_DIR/plan-check.log"
	printf 'dry run\n' >"$REPORT_DIR/rollout-waves.log"
	TEST_STATUS="passed"
	HELM_STATUS="passed"
	AIRGAP_STATUS="passed"
	AIRGAP_VERIFY_STATUS="passed"
	PLAN_STATUS="passed"
	ROLLOUT_WAVES_STATUS="passed"
else
	if run_and_capture tests python -m pytest -q; then
		TEST_STATUS="passed"
	fi

	echo "[governance] rendering helm templates"
	if helm template test ./helm/phase-lock-gateway >"$REPORT_DIR/helm-template.yaml" 2>"$REPORT_DIR/helm.log"; then
		HELM_STATUS="passed"
	else
		echo "[governance] helm template failed (see $REPORT_DIR/helm.log)"
	fi

	if run_and_capture airgap env OUT_DIR="$AIRGAP_BUNDLE_DIR" bash scripts/airgap/build_offline_bundle.sh; then
		AIRGAP_STATUS="passed"
	fi

	if [[ "$AIRGAP_STATUS" == "passed" ]]; then
		if run_and_capture airgap-verify bash scripts/airgap/verify_offline_bundle.sh "$AIRGAP_BUNDLE_DIR"; then
			AIRGAP_VERIFY_STATUS="passed"
		fi
	fi

	if grep -q "Step 20" docs/enterprise-execution-plan.md >"$REPORT_DIR/plan-check.log" 2>&1; then
		PLAN_STATUS="passed"
	else
		echo "[governance] plan check failed"
	fi

	if run_and_capture rollout-waves python scripts/release/validate_rollout_waves.py "$ROLLOUT_PLAN_PATH"; then
		ROLLOUT_WAVES_STATUS="passed"
	fi
fi

SUMMARY_JSON="$REPORT_DIR/summary.json"
cat >"$SUMMARY_JSON" <<EOF
{
	"report_dir": "$REPORT_DIR",
	"timestamp": "$TIMESTAMP",
	"checks": {
		"tests": "$TEST_STATUS",
		"helm_template": "$HELM_STATUS",
		"airgap_bundle": "$AIRGAP_STATUS",
		"airgap_verify": "$AIRGAP_VERIFY_STATUS",
		"plan_guard": "$PLAN_STATUS",
		"rollout_waves": "$ROLLOUT_WAVES_STATUS"
	}
}
EOF

echo "[governance] wrote summary to $SUMMARY_JSON"

if [[ "$TEST_STATUS" != "passed" || "$HELM_STATUS" != "passed" || "$AIRGAP_STATUS" != "passed" || "$AIRGAP_VERIFY_STATUS" != "passed" || "$PLAN_STATUS" != "passed" || "$ROLLOUT_WAVES_STATUS" != "passed" ]]; then
	echo "[governance] one or more checks failed"
	exit 1
fi

echo "[governance] checks complete"