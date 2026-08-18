PYTHON ?= .venv/bin/python
PYTEST ?= .venv/bin/pytest

.PHONY: venv test unit e2e bench demo clean

venv:
	python3 -m venv .venv
	.venv/bin/pip install -U pip
	.venv/bin/pip install -e ".[dev]"

test:
	$(PYTEST) -q

unit:
	$(PYTEST) -q tests/test_parse.py tests/test_apply.py tests/test_ddmin.py tests/test_evaluate.py

e2e:
	$(PYTEST) -q tests/test_e2e.py tests/test_cli_and_patch.py

bench:
	$(PYTHON) scripts/bench.py

demo:
	$(PYTHON) scripts/make_demo.py demo-repo
	cd demo-repo && PYTHONPATH=../src $(PYTHON) -m commit_delta --verbose --output reduced.patch -- ./reproduce.sh

demo-video:
	bash scripts/record_live_demo.sh

clean:
	rm -rf .bench-scratch demo-repo dist build *.egg-info .pytest_cache
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
