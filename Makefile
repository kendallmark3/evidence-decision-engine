.PHONY: install dev api ui build serve test

install:            ## Install backend + frontend dependencies
	python3 -m pip install -r backend/requirements-dev.txt
	cd frontend && npm install

api:                ## Run the API on :8000 (auto-reload)
	cd backend && uvicorn app.api:app --reload --port 8000

ui:                 ## Run the UI dev server on :5173 (proxies /api to :8000)
	cd frontend && npm run dev

dev:                ## Run API and UI together
	$(MAKE) -j2 api ui

build:              ## Build the UI into frontend/dist (served by the API)
	cd frontend && npm run build

serve: build        ## Single process: API + built UI on :8000
	cd backend && uvicorn app.api:app --port 8000

test:               ## All tests: intent gate + backend + UI type-check/build
	bash tests/pre-implement.test.sh
	bash hooks/pre-implement.sh
	cd backend && python3 -m pytest -q
	cd frontend && npm run build
