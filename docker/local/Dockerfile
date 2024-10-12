FROM python:3.12
RUN apt-get clean && apt-get update && \
    apt-get install -y --no-install-recommends \
           postgresql-client-common \
           postgresql-client \
           netcat-traditional \
           gosu

ENV REQUIREMENTS_FILE=project/requirements/local.txt

WORKDIR /app
COPY project/requirements /app/project/requirements
RUN pip install -r ${REQUIREMENTS_FILE} --src=/pip-repos

COPY . /app

EXPOSE 8000

ENV PATH="/app/docker/local:${PATH}"

ENTRYPOINT ["/app/docker/local/entrypoint.sh"]
CMD ["start-server"]
