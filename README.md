# Calibre to Kavita VFS

A dockerized tool that connects to your Calibre library (`metadata.db`) and automatically generates a Virtual File System (VFS) structure optimized for **Kavita**.

---

## Folder & File Structure

The tool organizes books into the exact hierarchy expected by Kavita:

```text
language/type/series/series Vol. volume Ch. chapter.ext
```

### Naming Rules:
- **`language`**: Extracted from Calibre's language tags (e.g. `eng`, `jpn`). Defaults to `unknown` or `DEFAULT_LANGUAGE`.
- **`type`**: Extracted from the custom Calibre column `type` (e.g. `Manga`, `Comic`, `Light Novel`, `Book`). Defaults to `DEFAULT_TYPE`.
- **`series`**: Extracted from Calibre's series. If the book does not have a series assigned, it defaults to the book's title.
- **`Vol.` & `Ch.`**: Only written if set in Calibre:
  - Both set: `Series Vol. 1 Ch. 12.cbz`
  - Volume only: `Series Vol. 1.cbz`
  - Chapter only: `Series Ch. 12.cbz`
  - Neither set: `Series.cbz`
  - Ranges supported: `Series Vol. 1-3 Ch. 1-25.cbz`
- **Number & String formatting**:
  - Strings are supported directly (e.g. `1-3`, `01-05`, `Special 1`).
  - Cleans floating point numbers (e.g. `1.0` becomes `1`, while `1.5` is preserved).
  - Automatically strips redundant user-typed prefixes like `Vol.` or `Ch.` if entered into Calibre.

---

## Calibre Setup

In Calibre, create the custom columns under **Preferences -> Add your own columns**:

| Lookup Name | Column Heading | Type | Notes |
|---|---|---|---|
| `type` (or `#type`) | Type | Enumeration or Text | e.g. `Manga`, `Comic`, `Light Novel` |
| `volume` (or `#volume`) | Volume | Text (or Integer / Float) | Use **Text** to allow ranges like `1-3`, or numbers like `1` |
| `chapter` (or `#chapter`) | Chapter | Text (or Integer / Float) | Use **Text** to allow ranges like `1-10` or numbers like `10` |

The tool automatically detects both normalized and unnormalized custom columns with or without the `#` prefix.

---

## Operating Modes

1. **`symlink` (Recommended Default)**:
   Creates directory trees with symlinks pointing to Calibre's original book files.
   - Requires zero special container privileges.
   - High performance with direct filesystem event support for Kavita.
   - *Note*: If using absolute symlinks, ensure `/calibre` is mounted in the Kavita container at the same path. Alternatively, set `RELATIVE_LINKS=true` if directories share a common root.

2. **`hardlink`**:
   Creates hardlinks instead of symlinks.
   - Does not depend on container mount paths.
   - Requires `/calibre` and `/vfs` to be located on the same underlying filesystem / disk mount.

3. **`fuse`**:
   Mounts a dynamic in-memory read-only FUSE filesystem.
   - Requires `--device /dev/fuse` and `--cap-add SYS_ADMIN` in Docker.

---

## Quickstart with Docker

### 1. `docker-compose.yml`

```yaml
version: "3.8"

services:
  calibre-kavita-vfs:
    build: .
    image: calibre-kavita-vfs:latest
    container_name: calibre-kavita-vfs
    restart: unless-stopped
    environment:
      - PUID=1000
      - PGID=1000
      - VFS_MODE=symlink           # 'symlink', 'hardlink', or 'fuse'
      - SYNC_INTERVAL=60           # Sync check interval in seconds
      - DEFAULT_LANGUAGE=eng
      - DEFAULT_TYPE=Manga
    volumes:
      - /path/to/calibre/library:/calibre:ro
      - /path/to/kavita/vfs_library:/vfs

  kavita:
    image: jvmilazz0/kavita:latest
    container_name: kavita
    restart: unless-stopped
    depends_on:
      - calibre-kavita-vfs
    ports:
      - "5000:5000"
    volumes:
      - /path/to/kavita/config:/kavita/config
      - /path/to/kavita/vfs_library:/data:ro
      # Required for symlink mode so target files resolve:
      - /path/to/calibre/library:/calibre:ro
```

### 2. Build and Run

```bash
# Build the image
docker compose build

# Start services in the background
docker compose up -d

# View logs
docker compose logs -f calibre-kavita-vfs
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `CALIBRE_DIR` | `/calibre` | Directory containing Calibre's `metadata.db` and book files |
| `VFS_DIR` | `/vfs` | Target directory for generated Kavita VFS |
| `CALIBRE_TARGET_DIR` | *(empty / uses CALIBRE_DIR)* | Custom path prefix written into symlinks (useful for Unraid host paths like `/mnt/user/...` or custom Kavita container paths) |
| `VFS_MODE` | `symlink` | `symlink`, `hardlink`, or `fuse` |
| `SYNC_INTERVAL` | `60` | Check interval in seconds for Calibre DB updates |
| `SYNC_ONCE` | `false` | If `true`, runs one sync pass and exits (for cron jobs) |
| `RELATIVE_LINKS` | `false` | When using symlink mode, create relative symlinks |
| `DEFAULT_LANGUAGE` | `unknown` | Fallback language code if not set in Calibre |
| `DEFAULT_TYPE` | `Unknown` | Fallback type if custom column `type` is not set |
| `PUID` | `1000` | User ID for file ownership |
| `PGID` | `1000` | Group ID for file ownership |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

---

## Unraid & Docker Path Mapping Tips

If Kavita cannot see or open your symlinked books, it is almost always because the symlink target path does not resolve **inside the Kavita container**:

1. **Why it happens**: By default, symlinks point to `/calibre/...`. Inside the `calibre-kavita-vfs` container, `/calibre` is mapped, but inside the `kavita` container, `/calibre` is usually missing. Without the target files present inside Kavita's container, the symlinks are dead/broken, and Kavita ignores them.
2. **Fix 1 (Recommended)**: In Unraid, edit your **Kavita** container and add a path mapping:
   - **Container Path**: `/calibre`
   - **Host Path**: `/mnt/user/.../calibre` (the same Calibre folder)
   - **Access Mode**: Read-Only
3. **Fix 2 (Hardlinks)**: If Calibre and VFS folders are on the same Unraid share or disk, set `VFS_MODE=hardlink`. Hardlinks do not require `/calibre` to be mapped inside Kavita at all!
4. **Fix 3 (Host Path Symlinks)**: Set `CALIBRE_TARGET_DIR=/mnt/user/path/to/calibre`. The symlinks will point directly to the host path.

---

## Running Tests

Run the unit test suite locally:

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```
