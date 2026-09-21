FROM python:3.12-slim AS engine
WORKDIR /app
COPY services/engine /app
RUN pip install --no-cache-dir .
ENV DANTEX_MODE=shadow
EXPOSE 8000
CMD ["uvicorn","dantex.api:app","--host","0.0.0.0","--port","8000"]
