.PHONY: registry bundles dist test verify-generated

registry:
	python -m minefield agent-bundle

bundles: registry

dist: registry

test:
	python -m unittest discover -s tests
	python -m unittest discover -s integrity/tests -t integrity/tests
	python -m unittest discover -s doctor/tests -t doctor/tests

verify-generated:
	python -m minefield agent-bundle
	python -m minefield agent-bundle --verify
	git diff --exit-code -- dist minefield/data registry/diagnostic_coverage.json registry/guided_experiments.json web/registry-data.js skills/model-serving-minefield/references/agent-bundle.md
