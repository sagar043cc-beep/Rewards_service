import sys
from uuid import uuid4
from sqlalchemy import create_engine, Column, String, select, delete
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class TestModel(Base):
    __tablename__ = 'test_table'
    id = Column(String, primary_key=True)
    name = Column(String)

engine = create_engine('sqlite:///:memory:')
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

db = SessionLocal()
item_id = str(uuid4())
item = TestModel(id=item_id, name="Test Item")
db.add(item)
db.commit()

# Delete with returning
stmt = delete(TestModel).where(TestModel.id == item_id).returning(TestModel)
result = db.execute(stmt).scalar_one_or_none()

# db.expunge(result)
db.commit()

try:
    print(result.name)
except Exception as e:
    print(f"Error without expunge: {type(e).__name__} - {e}")

# test with expunge
item2_id = str(uuid4())
item2 = TestModel(id=item2_id, name="Test Item 2")
db.add(item2)
db.commit()

stmt2 = delete(TestModel).where(TestModel.id == item2_id).returning(TestModel)
result2 = db.execute(stmt2).scalar_one_or_none()
db.expunge(result2)
db.commit()

try:
    print(result2.name)
    print("Success with expunge")
except Exception as e:
    print(f"Error with expunge: {type(e).__name__} - {e}")

