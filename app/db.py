from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set. Check your .env file.")

engine = create_engine(
    DATABASE_URL,
    pool_size=10,          # Max persistent connections in the pool
    max_overflow=20,       # Extra connections allowed under burst load
    pool_pre_ping=True,    # Verify connection health before use
    pool_recycle=1800,     # Recycle connections every 30 min to avoid stale sockets
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()