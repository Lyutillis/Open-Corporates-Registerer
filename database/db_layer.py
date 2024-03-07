import abc
from dataclasses import asdict
from datetime import datetime
import os
import sys
from typing import Literal, Optional, Union, List
from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker
from mongoengine import connect

from utils.log import get_logger
from database import models, mongo_models
from utils import dto
import envs


db_logger = get_logger("DB")


def get_db_class(
    db_type: Literal["postgresql", "mongodb"]
) -> Optional[Union["PostgreSQL", "MongoDB"]]:
    if db_type == "postgresql":
        return PostgreSQL

    if db_type == "mongodb":
        return MongoDB

    return None


class DatabaseABC(abc.ABC):

    @abc.abstractmethod
    def bulk_save_tasks(
        self,
        count: int
    ) -> None:
        pass

    @abc.abstractmethod
    def bulk_save_results(
        self,
        objects: List[dto.CreateResult]
    ) -> None:
        pass

    @abc.abstractmethod
    def reset_tasks_status(self) -> None:
        pass

    @abc.abstractmethod
    def get_idle_tasks(self, limit: int) -> List[models.Task]:
        pass

    @abc.abstractmethod
    def update_task(self, task: dto.Task, **kwargs) -> models.Task:
        pass

    @abc.abstractmethod
    def add_user(
        self,
        object: dto.User
    ) -> models.User:
        pass

    @abc.abstractmethod
    def add_result(
        self,
        object: dto.CreateResult
    ) -> models.Result:
        pass

    @abc.abstractmethod
    def get_task_by_id(self, id: int) -> models.Task:
        pass


class PostgreSQL(DatabaseABC):

    def __init__(self) -> None:
        self.engine = create_engine(
            (
                f"postgresql://{envs.POSTGRES_USER}:{envs.POSTGRES_PASSWORD}"
                f"@{envs.POSTGRES_HOST}/{envs.POSTGRES_DB}"
            )
        )
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        models.Base.metadata.create_all(self.engine)

    def bulk_save_tasks(
        self,
        count: int
    ) -> None:
        with self.SessionLocal() as db:
            db.bulk_save_objects(
                [
                    models.Task()
                    for _ in range(count)
                ]
            )
            db.commit()

    def bulk_save_results(
        self,
        objects: List[dto.CreateResult]
    ) -> None:
        with self.SessionLocal() as db:
            db.bulk_save_objects(
                [
                    models.Result(**asdict(result))
                    for result in objects
                ]
            )
            db.commit()

    def reset_tasks_status(self) -> None:
        with self.SessionLocal() as db:
            db.query(models.Task).filter(
                and_(models.Task.in_work == True, models.Task.completed == False)  # noqa
            ).update({"in_work": False})
            db.commit()

    def get_idle_tasks(self, limit: int) -> List[models.Task]:
        with self.SessionLocal() as db:
            return db.query(models.Task).filter(
                and_(
                    models.Task.in_work == False,  # noqa
                    models.Task.completed == False  # noqa
                )
            ).limit(limit).all()

    def update_task(self, task: dto.Task, **kwargs) -> models.Task:
        with self.SessionLocal() as db:
            db.query(models.Task).filter(
                models.Task.id == task.id
            ).update(kwargs)
            db.commit()
        return task

    def add_user(
        self,
        object: dto.User
    ) -> models.User:
        with self.SessionLocal() as db:
            result = models.User(**asdict(object))
            db.add(result)
            db.commit()
            return db.query(models.User).filter(
                models.User.id == result.id
            ).first()

    def add_result(
        self,
        object: dto.CreateResult
    ) -> models.Result:
        with self.SessionLocal() as db:
            result = models.Result(**asdict(object))
            db.add(result)
            db.commit()
            return db.query(models.Result).filter(
                models.Result.id == result.id
            ).first()

    def get_task_by_id(self, id: int) -> models.Task:
        with self.SessionLocal() as db:
            return db.query(models.Task).filter(
                models.Task.id == id
            ).first()

    @staticmethod
    def create_database_dump() -> None:
        timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        file_path = os.path.join("dumps", f"dump_{timestamp}")
        command = (
            f"pg_dump --no-owner --dbname=postgresql://{envs.POSTGRES_USER}"
            f":{envs.POSTGRES_PASSWORD}@{envs.POSTGRES_HOST}:"
            f"{envs.POSTGRES_PORT}/{envs.POSTGRES_DB} > {file_path}"
        )
        code = os.system(command)
        if code:
            db_logger.error(
                f"Error dumping database: code - {code}, command - {command}"
            )
            sys.exit(10)


class MongoDB(DatabaseABC):

    def __init__(self) -> None:
        connect(
            host=envs.MONGO_URI
        )

    def bulk_save_tasks(
        self,
        count: int
    ) -> None:
        mongo_models.Task.objects.insert(
            [
                mongo_models.Task()
                for _ in range(count)
            ]
        )

    def bulk_save_results(
        self,
        objects: List[dto.CreateResult]
    ) -> None:
        mongo_models.Result.objects.insert(
            [
                mongo_models.Result(
                    task=mongo_models.Task.objects.get(id=result.task_id),
                    user=mongo_models.User.objects.get(id=result.user_id)
                )
                for result in objects
            ]
        )

    def reset_tasks_status(self) -> None:
        mongo_models.Task.objects(
            in_work=True, completed=False
        ).update(in_work=False)

    def get_idle_tasks(self, limit: int) -> List[mongo_models.Task]:
        return mongo_models.Task.objects(
            in_work=False, completed=False
        ).limit(limit).all()

    def update_task(self, task: dto.Task, **kwargs) -> mongo_models.Task:
        mongo_models.Task.objects(id=task.id).update_one(**kwargs)
        return mongo_models.Task.objects(id=task.id).first()

    def add_user(
        self,
        object: dto.User
    ) -> models.User:
        user = mongo_models.User(
            **asdict(object)
        )
        user.save()
        return user

    def add_result(
        self,
        object: dto.CreateResult
    ) -> mongo_models.Result:
        user = mongo_models.User.objects.get(id=object.user_id)
        task = mongo_models.Task.objects.get(id=object.task_id)
        result = mongo_models.Result()
        result.task = task
        result.user = user
        result.save()
        return result

    def get_task_by_id(self, id: int) -> mongo_models.Task:
        return mongo_models.Task.objects(id=id).first()

    @staticmethod
    def create_database_dump() -> None:
        timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        file_path = os.path.join("dumps", f"dump_{timestamp}")
        command = (
            f"mongodump --uri={envs.MONGO_URI} --out {file_path}"
        )
        code = os.system(command)
        if code:
            db_logger.error(
                f"Error dumping database: code - {code}, command - {command}"
            )
            sys.exit(10)


class DBInterface(DatabaseABC):
    def __init__(self, db_type: Literal["postgresql", "mongodb"]) -> None:
        self.db_type = db_type
        self.db: Optional[Union[PostgreSQL, MongoDB]] = get_db_class(db_type)()
        assert self.db is not None

    def bulk_save_tasks(
        self,
        count: int
    ) -> None:
        return self.db.bulk_save_tasks(count)

    def bulk_save_results(
        self,
        objects: List[dto.Result]
    ) -> None:
        return self.db.bulk_save_results(objects)

    def reset_tasks_status(self) -> None:
        return self.db.reset_tasks_status()

    def get_idle_tasks(self, limit: int) -> List[models.Task]:
        return self.db.get_idle_tasks(limit)

    def update_task(self, task: models.Task, **kwargs) -> models.Task:
        return self.db.update_task(task, **kwargs)

    def add_user(
        self,
        object: dto.User
    ) -> models.User:
        return self.db.add_user(object)

    def add_result(
        self,
        object: dto.CreateResult
    ) -> mongo_models.Result:
        return self.db.add_result(object)

    def get_task_by_id(self, id: int) -> models.Task:
        return self.db.get_task_by_id(id)

    def create_database_dump(self) -> None:
        self.db.create_database_dump()
