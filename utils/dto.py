from dataclasses import dataclass


@dataclass
class User:
    email: str
    username: str
    job_title: str
    organization: str
    password: str


@dataclass
class Task:
    id: int
    in_work: bool
    completed: bool


@dataclass
class Result:
    task_id: int
    user: User


@dataclass
class CreateResult:
    task_id: int
    user_id: int
