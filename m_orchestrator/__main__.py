from typing import List, Literal
import json
from dataclasses import asdict
import time

from database.dal import TaskDAL, ResultDAL
from utils.dto import User, Task, Result
from utils.cache import Cache
from utils.log import get_logger
from utils.encoders import ObjectIdEncoder


orchestrator_logger = get_logger("Orchestrator")


class Orchestrator:
    def __init__(self, db_type: Literal["postgresql", "mongodb"]) -> None:
        self.tasks: List[Task] = []
        self.results: List[Result] = []
        self.cache_1: Cache = Cache(1)

        self.task_dal: TaskDAL = TaskDAL(db_type)
        self.result_dal: ResultDAL = ResultDAL(db_type)

    def create_tasks(self, count: int = 10) -> None:
        self.task_dal.create_tasks(count)

    def reset_tasks_status(self) -> None:
        self.task_dal.reset_tasks_status()

    def get_tasks(self, count: int = 10) -> None:
        self.tasks.extend(
            self.task_dal.get_tasks(count)
        )

    def pass_tasks(self) -> None:
        orchestrator_logger.info("Passing tasks to Redis")
        for task in self.tasks:
            self.cache_1.red.lpush(
                "tasks_queue",
                json.dumps(asdict(task), cls=ObjectIdEncoder)
            )
        self.tasks = []

    def get_results(self) -> None:
        orchestrator_logger.info("Getting results from Redis")
        while True:
            item = self.cache_1.red.rpop("results_queue")
            if not item:
                return
            data = json.loads(item)
            result = Result(
                task_id=data.pop("task_id"),
                user=User(
                    **data["user"]
                )
            )
            self.results.append(result)

    def save_results(self) -> None:
        if self.results:
            self.result_dal.save_results(self.results)
            self.results = []

    def run(self) -> None:
        self.create_tasks(count=2)
        self.reset_tasks_status()

        while True:
            self.get_tasks()
            self.pass_tasks()
            self.get_results()
            self.save_results()
            time.sleep(20)


if __name__ == "__main__":
    orchestrator = Orchestrator("mongodb")
    orchestrator.run()
