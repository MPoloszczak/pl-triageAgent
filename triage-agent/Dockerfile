# syntax=docker/dockerfile:1
FROM public.ecr.aws/lambda/python:3.12

# Prevent Python from writing pyc files & buffer stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /var/task

# Ensure the app package directory is discoverable for absolute imports like `import graph`
ENV PYTHONPATH="/var/task/app:${PYTHONPATH}"

# Copy dependency definitions first for cache
COPY triage-agent/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source so that /var/task/app is importable
COPY triage-agent/app ./app

EXPOSE 8000

# Lambda image entrypoint expects CMD to point to handler
CMD ["app.lambda_handler.handler"] 