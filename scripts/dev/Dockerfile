FROM python:3.12

RUN apt-get clean && apt-get update && \
    apt-get install -y --no-install-recommends \
           gosu

WORKDIR /app
COPY requirements.txt dev-requirements.txt /app/
RUN pip install -r requirements.txt -r dev-requirements.txt --src=/pip-repos

COPY . /app

EXPOSE 8000

ENTRYPOINT ["/app/scripts/dev/entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
