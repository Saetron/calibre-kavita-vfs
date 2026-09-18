# Calibre to Kavita VFS

A dockerized tool that connects to your Calibre library (`metadata.db`) and automatically generates a Virtual File System (VFS) structure optimized for **Kavita**, complete with a live **WebUI Dashboard**.

---

## Folder & File Structure

The tool organizes books into the exact hierarchy expected by Kavita:

```text
language/type/series/series Vol. volume Ch. chapter {calibre_id}.ext
```

### Naming Rules:
- **`language`**: Extracted from Calibre's language tags (e.g. `eng`, `jpn`). Defaults to `unknown` or `DEFAULT_LANGUAGE`.
- **`type`**: Extracted from the custom Calibre column `type` (e.g. `Manga`, `Comic`, `Light Novel`, `Book`). Defaults to `DEFAULT_TYPE`.
- **`series`**: Extracted from Calibre's series. If the book does not have a series assigned, it defaults to the book's title.
- **`Vol.` & `Ch.`**: Only written if set in Calibre:
  - Both set: `Series Vol. 1 Ch. 12 {42}.cbz`
  - Volume only: `Series Vol. 1 {42}.cbz`
  - Chapter only: `Series Ch. 12 {42}.cbz`
  - Neither set: `Series {42}.cbz`
  - Ranges supported: `Series Vol. 1-3 Ch. 1-25 {42}.cbz`
- **`{calibre_id}`**: The Calibre book ID in curly brackets is added directly before the file extension, ensuring uniqueness and easy reference.
- **Number & String formatting**:
  - Strings and ranges are supported directly (e.g. `1-3`, `01-05`, `Special 1`).
  - Cleans floating point numbers (e.g. `1.0` becomes `1`, while `1.5` is preserved).
  - Automatically strips redundant user-typed prefixes like `Vol.` or `Ch.` if entered into Calibre.

---

## WebUI Dashboard

The container includes a built-in, lightweight web dashboard accessible at:
```text
http://<server-ip>:8080
```

### Features:
- **Live Statistics**:
  - Total books and series.
  - **Aggregated Volumes & Chapters**: Calculates and sums all individual volumes, chapters, and ranges across your entire library (e.g. `Vol. 1-3` counts as 3 volumes).
  - Breakdown by custom type (Manga, Comic, etc.) and language.
- **Collision Monitor**: Highlights any conflicting filename mappings and shows how they were automatically disambiguated.
- **Searchable Book Explorer**: Filterable and searchable table of every mapped book showing its Calibre ID, title, series, volume, chapter, VFS path, and source file.
- **Manual Sync Button**: Trigger an immediate VFS synchronization without waiting for the check interval.
- **Cleanup VFS Button**: Scans the VFS directory, removes any unregistered files or broken links, prunes empty folders, and ensures all links are converted when switching between `symlink` and `hardlink` modes.

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

### `docker-compose.yml`

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
      - WEBUI_ENABLED=true
      - WEBUI_PORT=8080
    ports:
      - "8080:8080"                # WebUI Dashboard
    volumes:
      # Option A (Standard Symlinks): Separate mounts
      - /path/to/calibre/library:/calibre:ro
      - /path/to/kavita/vfs_library:/vfs
      # Option B (Hardlinks on single mount):
      # - /path/to/shared/data:/data
      # (and set CALIBRE_DIR=/data/calibre, VFS_DIR=/data/vfs, VFS_MODE=hardlink)

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
| `WEBUI_ENABLED` | `true` | Enable WebUI status dashboard |
| `WEBUI_PORT` | `8080` | Port to serve the WebUI dashboard |
| `PUID` | `1000` | User ID for file ownership |
| `PGID` | `1000` | Group ID for file ownership |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

---

## Unraid & Docker Path Mapping Tips

### Using Hardlinks on Unraid (`VFS_MODE=hardlink`)
In Linux, **hardlinks cannot cross Docker mount points** (Linux returns `EXDEV: Invalid cross-device link`).
If you map `-v /mnt/user/data/calibre:/calibre` and `-v /mnt/user/data/vfs:/vfs`, Docker creates **two separate mounts**, preventing hardlinks from working even though they are on the same Unraid share!

**Solution**: Use a single parent mount (e.g. `/data`):
- **Host Share**: `/mnt/user/data`
- **In `calibre-kavita-vfs` container**:
  - Mount: `/mnt/user/data` -> `/data`
  - Set: `CALIBRE_DIR=/data/calibre`
  - Set: `VFS_DIR=/data/vfs`
  - Set: `VFS_MODE=hardlink`
- **In `kavita` container**:
  - Mount: `/mnt/user/data/vfs` -> `/data`
  - Kavita sees real, independent files. It does **not** need Calibre mounted at all, and it consumes **zero extra disk space**!

### Using Symlinks
If using symlinks, remember that Kavita runs in its own container and must be able to reach the target files:
1. **Fix 1 (Recommended)**: In Unraid, edit your **Kavita** container and add a path mapping:
   - **Container Path**: `/calibre`
   - **Host Path**: `/mnt/user/.../calibre` (the same Calibre folder)
   - **Access Mode**: Read-Only
2. **Fix 2 (Host Path Symlinks)**: Set `CALIBRE_TARGET_DIR=/mnt/user/path/to/calibre`. The symlinks will point directly to the host path.

---

## Running Tests

Run the unit test suite locally:

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```
