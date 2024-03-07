from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Boolean
)

from database.config import Base


class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False)
    username = Column(String(255), nullable=False)
    job_title = Column(String(255), nullable=False)
    organization = Column(String(255), nullable=False)
    password = Column(String(255), nullable=False)


class Task(Base):
    __tablename__ = "task"

    id = Column(Integer, primary_key=True, index=True)
    in_work = Column(Boolean, default=False)
    completed = Column(Boolean, default=False)


class Result(Base):
    __tablename__ = "result"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("task.id"))
    user_id = Column(Integer, ForeignKey("user.id"))
