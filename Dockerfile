FROM python:3.12-alpine

WORKDIR /opt/app

COPY requirements/prod.txt requirements/prod.txt
RUN pip install --no-cache-dir -r requirements/prod.txt

COPY app/ .
COPY .env .env

RUN mkdir -p logs

CMD ["python", "-m", "bot.main"]
