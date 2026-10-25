.PHONY: install check test eval demo api
install:
	python -m pip install -r requirements-dev.lock
	python -m pip install --no-deps -e .
check:
	ruff check .
	ruff format --check .
	python scripts/check_repository.py
test:
	pytest -q --cov=jev_core --cov=jev_tools --cov=jev_workflows --cov=jev_api --cov=jev_evals --cov-fail-under=85
eval:
	jev-eval --output reports/evaluation.json
demo:
	jev demo --simulate-review
api:
	uvicorn jev_api.app:create_app --factory --host 127.0.0.1 --port 8000
