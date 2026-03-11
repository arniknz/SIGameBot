FROM python:3.12-alpine

WORKDIR /opt

COPY requirements/prod.txt requirements/prod.txt
RUN pip install --no-cache-dir -r requirements/prod.txt

COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .
COPY .env .env

RUN mkdir -p logs

CMD ["sh", "-c", "alembic upgrade head && cd app && python -m bot.main"]
