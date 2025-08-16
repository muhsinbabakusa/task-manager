import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# NEW: load .env locally; in prod, Render/Railway set env vars
from dotenv import load_dotenv
load_dotenv()

# Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- IMPORT YOUR MODELS' METADATA ---
# Adjust the path if your models are not in models.py or not at project root
from models import Base  # <- make sure this import is correct
target_metadata = Base.metadata

# --- DATABASE URL ---
def get_url():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL env var is not set")
    return url

# Optional: better autogenerate diffs
def include_object(object, name, type_, reflected, compare_to):
    # Always include; customize if needed
    return True

def run_migrations_offline():
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,      # detect column type changes
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
