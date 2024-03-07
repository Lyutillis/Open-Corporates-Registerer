from mongoengine import (
    Document,
    StringField,
    BooleanField,
    ReferenceField
)


class User(Document):
    email = StringField(max_length=255, required=True)
    username = StringField(max_length=255, required=True)
    job_title = StringField(max_length=255, required=True)
    organization = StringField(max_length=255, required=True)
    password = StringField(max_length=255, required=True)


class Task(Document):
    in_work = BooleanField(default=False)
    completed = BooleanField(default=False)


class Result(Document):
    task = ReferenceField("Task", reverse_delete_rule=1)
    user = ReferenceField("User", reverse_delete_rule=1)
