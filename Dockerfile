FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY ui.html ./ui.html
COPY setup.html ./setup.html
RUN pip install --no-cache-dir -e . \
    && python -m playwright install --with-deps chromium
EXPOSE 8765
# Secure local default. Remote/container exposure requires an explicit non-loopback
# bind together with NOTSIP_API_KEY or a complete OIDC configuration.
ENV NOTSIP_HOST=127.0.0.1
CMD ["python","-m","notsip"]
