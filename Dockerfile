FROM python:3.11-slim-bookworm

LABEL maintainer="Kavita VFS"
LABEL description="Bridge Calibre metadata.db and files to Kavita's expected directory structure"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CALIBRE_DIR=/calibre \
    VFS_DIR=/vfs \
    VFS_MODE=symlink \
    SYNC_INTERVAL=60 \
    LINK_TYPE=symlink \
    RELATIVE_LINKS=false \
    DEFAULT_LANGUAGE=unknown \
    DEFAULT_TYPE=Unknown \
    PUID=1000 \
    PGID=1000

# Install runtime dependencies: fuse3 (for FUSE mode), gosu (for user privilege dropping)
RUN apt-get update && apt-get install -y --no-install-recommends \
    fuse3 \
    libfuse3-3 \
    gosu \
    && rm -rf /var/lib/apt/lists/* \
    && sed -i 's/#user_allow_other/user_allow_other/' /etc/fuse.conf 2>/dev/null || true

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
CMD []
