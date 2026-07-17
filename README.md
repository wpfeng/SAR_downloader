# Sentinel-1 Data Download Tools

A collection of Python scripts for querying and downloading Sentinel-1 SAR data from **ESA CDSE** (Copernicus Data Space Ecosystem) and **ASF** (Alaska Satellite Facility).

---

## Table of Contents

- [Overview](#overview)
- [Requirements](#requirements)
- [Tool 1: CDSE Sentinel-1 Downloader](#tool-1-cdse-sentinel-1-downloader)
- [Tool 2: ASF Sentinel-1 Search Tool](#tool-2-asf-sentinel-1-search-tool)
- [Quick Comparison](#quick-comparison)
- [Tips](#tips)

---

## Overview

| Tool | Data Source | Authentication | Typical Use Case |
|------|-------------|----------------|------------------|
| `py_cdse_s1downloader.py` | ESA CDSE | CDSE Account (OAuth2) | Full-archive access, SLC/GRD/RAW, Europe-centric |
| `py_asf_searchS1.py` | NASA ASF | NASA Earthdata | Fast search, bulk download via aria2c, North America optimized |

---

## Requirements

### Common Dependencies

```bash
pip install requests pandas tqdm
```

### Tool-Specific Dependencies

```bash
# For CDSE tool (optional but recommended)
pip install shapely

# For ASF tool
pip install asf_search
```

---

## Tool 1: CDSE Sentinel-1 Downloader

Query and download Sentinel-1 products from the ESA Copernicus Data Space Ecosystem (CDSE) via the OData API.

### Setup

Store your CDSE credentials:

```bash
mkdir -p ~/.cdse
cat > ~/.cdse <<EOF
your_cdse_username
your_cdse_password
EOF
chmod 600 ~/.cdse
```

### Usage

**Search only** (no download):
```bash
python py_cdse_s1downloader.py \
  --start 2024-01-01 --end 2024-01-31 \
  --roi 116,117,39.5,40 \
  --search-only
```

**Search + download**:
```bash
python py_cdse_s1downloader.py \
  --start 2024-01-01 --end 2024-01-31 \
  --roi 116,117,39.5,40 \
  --product-type IW_SLC__1S \
  --orbit-direction ASCENDING \
  --download
```

### CLI Options

| Option | Description |
|--------|-------------|
| `--start YYYY-MM-DD` | Start date |
| `--end YYYY-MM-DD` | End date |
| `--roi lonmin,lonmax,latmin,latmax` | Bounding box (shortcut for AOI) |
| `--aoi "POLYGON(...)"` | WKT polygon or GeoJSON file |
| `--product-type` | `IW_SLC__1S` (default), `IW_GRDH_1S`, etc. |
| `--orbit-direction` | `ASCENDING` or `DESCENDING` |
| `--relative-orbit 12 34` | Filter by orbit number(s) |
| `--polarization VV+VH` | Polarization mode |
| `--limit N` | Max results (default: 1000) |
| `--search-only` | Query catalog without downloading |
| `--download` | Confirm and download after search |
| `--output-dir ./downloads` | Download directory |

### Outputs

- `search_results.json` / `.csv` / `.geojson` — Search metadata
- `downloads/*.zip` — Downloaded SLC/GRD products
- `py_cdse_s1downloader.log` — Execution log

---

## Tool 2: ASF Sentinel-1 Search Tool

Search and download Sentinel-1 SLC data from the Alaska Satellite Facility (ASF) using `asf_search`.

### Setup

Store your NASA Earthdata credentials:

```bash
mkdir -p ~/.asf
cat > ~/.asf/passwd <<EOF
your_username your_password
EOF
chmod 600 ~/.asf/passwd
```

### Usage

**Search only**:
```bash
python py_asf_searchS1.py \
  2025-06-01 2025-07-30 \
  87.2,88.1,28.2,29 \
  s1_output.csv
```

**Search + download**:
```bash
python py_asf_searchS1.py \
  2025-06-01 2025-07-30 \
  87.2,88.1,28.2,29 \
  s1_output.csv \
  -download
```

### Arguments

| Argument | Description |
|----------|-------------|
| `start_date` | Start date (`YYYY-MM-DD`) |
| `end_date` | End date (`YYYY-MM-DD`) |
| `roi` | Bounding box: `lonmin,lonmax,latmin,latmax` |
| `out_csv` | Output CSV filename |
| `-download` | (Optional) Trigger batch download |

### Outputs

- `s1_output.csv` — Search results (granule name, beam mode, polarization, orbit direction, URL)
- `s1_output.list` — Plain-text URL list for external downloaders
- Downloaded data in `./data/` (only if `-download` is used)

> **Note:** Batch download relies on `pSAR_alask_s1downloading_url.py` (aria2c-based). Ensure it is in your `$PATH`.

---

## Quick Comparison

| Feature | CDSE Tool | ASF Tool |
|---------|-----------|----------|
| **Product types** | SLC, GRD, RAW, OCN | SLC (fixed) |
| **AOI formats** | WKT, GeoJSON, bbox | Bbox only |
| **Output formats** | JSON, CSV, GeoJSON | CSV |
| **Download method** | Built-in (requests) | External (aria2c) |
| **Authentication** | CDSE OAuth2 | NASA Earthdata |
| **Local cache check** | Yes (`/mnt/NAS80T*/S1/`) | No |
| **Config file support** | Yes (`--config`) | No |

---

## Tips

- **Choose CDSE** when you need GRD/RAW products, complex AOI queries, or direct downloads without external tools.
- **Choose ASF** when you need fast bulk downloads via aria2c or prefer NASA Earthdata credentials.
- Both tools support **resume/skip** for existing files (CDSE checks local NAS paths; ASF checks file size).
- Keep your credential files (`~/.cdse`, `~/.asf/passwd`) **readable only by you** (`chmod 600`).

---

## License

Use at your own risk. Adapted for geodetic SAR processing workflows.
