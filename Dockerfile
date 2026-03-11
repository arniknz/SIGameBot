FROM python:3.12-alpine

WORKDIR /opt

COPY requirements/prod.txt requirements/prod.txt
RUN pip install --no-cache-dir -r requirements/prod.txt

COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .

ENV PYTHONPATH=/opt/app

RUN mkdir -p logs

CMD ["sh", "-c", "\
  for i in 1 2 3 4 5; do \
    alembic upgrade head && break; \
    echo \"Migration retry $i/5...\"; \
    sleep 3; \
  done && exec python -m bot.main \
"]
