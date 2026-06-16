# Image reproductible (API). Le front se build séparément (apps/web).
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml ./
COPY packages ./packages
COPY apps ./apps
COPY config ./config
COPY data ./data
RUN uv pip install --system -e ".[api,data,quant]"
EXPOSE 8000
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
