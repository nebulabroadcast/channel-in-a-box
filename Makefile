.PHONY: help setup update

help:
	@echo "make setup   - reload ./settings into the database, restart server and worker"
	@echo "make update  - pull the latest images and recreate the stack"

# Re-run the one-shot setup job (loads ./settings), then restart
# the services that read settings on startup
setup:
	docker compose run --rm setup
	docker compose restart server worker

update:
	docker compose pull
	docker compose up -d --remove-orphans
