from alembic import context
from app.database import make_engine

with make_engine().connect() as connection:
    context.configure(connection=connection, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()
