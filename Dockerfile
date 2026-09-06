FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY ui.html ./ui.html
RUN pip install --no-cache-dir -e .
EXPOSE 8765
ENV NOTSIP_HOST=0.0.0.0
CMD ["python","-m","notsip"]
