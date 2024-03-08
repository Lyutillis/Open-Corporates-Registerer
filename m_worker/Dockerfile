FROM --platform=linux/amd64 python:3.10.7
LABEL maintainer="chemuranov@gmail.com"

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update

RUN pip install --upgrade pip

COPY worker_requirements.txt worker_requirements.txt

RUN pip install -r worker_requirements.txt

RUN pip install playwright 

RUN apt-get update && playwright install --with-deps chromium

COPY ../ .

CMD ["python3", "-m", "m_worker"]
