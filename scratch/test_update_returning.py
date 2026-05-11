import sys
from uuid import uuid4
from sqlalchemy import create_engine, Column, String, update
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class TestModel(Base):
    __tablename__ = 'test_table2'
    id = Column(String, primary_key=True)
    name = Column(String)

engine = create_engine('sqlite:///:memory:', echo=True)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

db = SessionLocal()
item_id = str(uuid4())
item = TestModel(id=item_id, name="Test Item")
db.add(item)
db.commit()

# Update with returning
stmt = update(TestModel).where(TestModel.id == item_id).values(name="New Name").returning(TestModel)
result = db.execute(stmt).scalar_one_or_none()

db.expunge(result)
db.commit()

print("--- Accessing attribute after commit ---")
print(result.name)
print("--- Done ---")
