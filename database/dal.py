from typing import List, Literal

from utils import dto
from utils.log import get_logger
from database.db_layer import DBInterface


db_logger = get_logger("Database")


class DAL:
    def __init__(self, db_type: Literal["postgresql", "mongodb"]) -> None:
        self.db: DBInterface = DBInterface(db_type)


class TaskDAL(DAL):
    def reset_tasks_status(self) -> None:
        db_logger.info("Resetting unfinished tasks")
        self.db.reset_tasks_status()

    def create_tasks(self, count: int) -> None:
        db_logger.info("Creating new tasks")
        self.db.bulk_save_tasks(count)

    def get_tasks(self, limit: int) -> List[dto.Task]:
        db_logger.info("Getting tasks from DataBase")
        result = []
        for item in self.db.get_idle_tasks(limit):
            task = dto.Task(
                item.id,
                item.in_work,
                item.completed
            )
            self.db.update_task(item, in_work=True)
            result.append(task)

        return result


class ResultDAL(DAL):
    def save_results(self, items: List[dto.Result]) -> None:
        if not items:
            return

        db_logger.info("Saving results into DataBase")

        for item in items:
            db_user = self.db.add_user(item.user)

            result = dto.CreateResult(
                task_id=item.task_id,
                user_id=db_user.id
            )
            self.db.add_result(result)
            self.db.update_task(
                self.db.get_task_by_id(item.task_id),
                completed=True
            )
