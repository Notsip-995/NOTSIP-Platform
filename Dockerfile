FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY ui.html ./ui.html
COPY setup.html ./setup.html
RUN pip install --no-cache-dir -e . \
    && python -m playwright install --with-deps chromium \
    && useradd --create-home --uid 10001 notsip \
    && mkdir -p /app/data /home/notsip/.cache \
    && chown -R notsip:notsip /app/data /home/notsip
EXPOSE 8765
# Secure local default. Remote/container exposure requires an explicit non-loopback
# bind together with NOTSIP_API_KEY or a complete OIDC configuration.
ENV NOTSIP_HOST=127.0.0.1
USER notsip
CMD ["python","-m","notsip"]
