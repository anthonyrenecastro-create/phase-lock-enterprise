.PHONY: governance governance-dry rollout-plan-check

governance:
	bash scripts/release_governance_checks.sh

governance-dry:
	DRY_RUN=1 bash scripts/release_governance_checks.sh

rollout-plan-check:
	python scripts/release/validate_rollout_waves.py docs/release-rollout-waves.json
