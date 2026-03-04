.PHONY: build up down restart logs ps prune db-migrate

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker-compose logs -f

ps:
	docker-compose ps

prune:
	docker-compose down -v
	docker system prune -f

db-migrate:
	docker-compose exec backend python -c "from app.database import db; import sqlmodel; sqlmodel.SQLModel.metadata.create_all(db.engine)"
