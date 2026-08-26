FROM python:3.12-slim

WORKDIR /app

RUN pip install poetry && \
    poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root

COPY . .

WORKDIR /app/backend

EXPOSE 5000

CMD ["python", "main.py"]
