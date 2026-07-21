# Sentinel-1 Data Download Tools

A collection of Python scripts for querying and downloading Sentinel-1 and NISAR data from **ESA CDSE** (Copernicus Data Space Ecosystem) or/and **ASF** (Alaska Satellite Facility).

---

## Table of Contents

- [Overview](#overview)
- [Requirements](#requirements)
- [Tool 1: CDSE Sentinel-1 Downloader](#tool-1-cdse-sentinel-1-downloader)
- [Tool 2: ASF Sentinel-1 Search Tool](#tool-2-asf-sentinel-1-search-tool)
- [Tool 3: ASF NISAR Search & Download Tool](#tool-3-asf-nisar-search--download-tool)
- [Quick Comparison](#quick-comparison)
- [Tips](#tips)

---

## Overview

| Tool | Data Source | Authentication | Typical Use Case |
|------|-------------|----------------|------------------|
| `py_cdse_s1downloader.py` | ESA CDSE | CDSE Account (OAuth2) |  access for data received in the recent 12 months, SLC/GRD/RAW, Europe-centric |
| `py_asf_searchS1.py` | NASA ASF | NASA Earthdata | full-archive access with lastest data delayed, bulk download via aria2c, North America optimized |
| `py_asf_NISARdownloading.py` | NASA ASF | NASA Earthdata | NISAR L1 RSLC search/download, KML footprint generation |

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

# For ASF S1 tool, aria2 is highly recommanded for downloading SAR data...
pip install asf_search
sudo apt-get install aria2

# For ASF NISAR tool
pip install asf_search simplekml pygeoif geojson
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

## Tool 3: ASF NISAR Search & Download Tool

Search and download NISAR L1 RSLC data from the Alaska Satellite Facility (ASF). Supports KML generation, zip packaging, and selective HDF5-only downloads.

### Setup

Uses the same NASA Earthdata credentials as the ASF Sentinel-1 tool:

```bash
mkdir -p ~/.asf
cat > ~/.asf/passwd <<EOF
your_username your_password
EOF
chmod 600 ~/.asf/passwd
```

Additional dependencies:

```bash
pip install asf_search simplekml pygeoif geojson
```

### Usage

**Search only** (generate KML footprint):
```bash
python py_asf_NISARdownloading.py \
  20250601 20250730 \
  87.2,88.1,28.2,29 \
  -track 12 \
  -outkml nisar_results.kml
```

**Search + download all files**:
```bash
python py_asf_NISARdownloading.py \
  2025-06-01 2025-07-30 \
  87.2,88.1,28.2,29 \
  -track 12 \
  -download \
  -nisar_db ./nisar_data
```

**Download HDF5 only** (via aria2c):
```bash
python py_asf_NISARdownloading.py \
  2025-06-01 2025-07-30 \
  87.2,88.1,28.2,29 \
  -track 12 \
  -download \
  -only_h5 \
  -nisar_db ./nisar_data
```

**Download + auto-package to ZIP**: (if no track is given, data in available tracks will be returned)
```bash
python py_asf_NISARdownloading.py \
  2025-06-01 2025-07-30 \
  87.2,88.1,28.2,29 \
  -download -zip \
  -nisar_db ./nisar_data
```

### Arguments

| Argument | Description |
|----------|-------------|
| `start_time` | Start date (`YYYY-MM-DD`) |
| `end_time` | End date (`YYYY-MM-DD`) |
| `ext` | Bounding box: `lonmin,lonmax,latmin,latmax` |
| `-track N` | **Required.** Relative orbit number |
| `-download` | Trigger download (default: search only) |
| `-zip` | Auto-package each scene into a single ZIP file |
| `-only_h5` | Download only `.h5` files using aria2c |
| `-nisar_db PATH` | Output directory (default: current dir or `$NISAR_DB`) |
| `-outkml FILE` | KML footprint output (default: `asf_nisar.kml`) |
| `-user USER` | Override Earthdata username |
| `-pwd PASS` | Override Earthdata password |

### Outputs

- `asf_nisar.kml` — Search result footprints (viewable in Google Earth)
- `nisar_db/*.h5` / `*.zip` — Downloaded NISAR products
- Scene-level ZIP archives (if `-zip` is enabled)

> **Note:** The `-only_h5` mode uses `aria2c` directly for faster HDF5 downloads. Ensure aria2c is installed.

---

## Quick Comparison

| Feature | CDSE S1 Tool | ASF S1 Tool | ASF NISAR Tool |
|---------|-------------|-------------|----------------|
| **Data source** | ESA CDSE | NASA ASF | NASA ASF |
| **Product types** | SLC, GRD, RAW, OCN | SLC (fixed) | NISAR L1 RSLC |
| **AOI formats** | WKT, GeoJSON, bbox | Bbox only | Bbox only |
| **Output formats** | JSON, CSV, GeoJSON | CSV | KML |
| **Download method** | Built-in (requests) | External (aria2c) | Built-in / aria2c (`-only_h5`) |
| **Authentication** | CDSE OAuth2 | NASA Earthdata | NASA Earthdata |
| **Local cache check** | Yes (`/mnt/NAS80T*/S1/`) | No | Yes (file existence) |
| **Config file support** | Yes (`--config`) | No | No |
| **Track filtering** | Yes (`--relative-orbit`) | No | Yes (`-track`, required) |
| **Auto zip packaging** | No | No | Yes (`-zip`) |

---

## Tips

- **Choose CDSE S1** when you need GRD/RAW products, complex AOI queries, or direct downloads without external tools.
- **Choose ASF S1** when you need fast bulk downloads via aria2c or prefer NASA Earthdata credentials.
- **Choose ASF NISAR** when working with NISAR L1 RSLC data, need KML footprint visualization, or want automatic ZIP packaging.
- All tools support **resume/skip** for existing files (CDSE checks local NAS paths; ASF/NISAR check file existence).
- Keep your credential files (`~/.cdse`, `~/.asf/passwd`) **readable only by you** (`chmod 600`). Otherwise, you can pass account info by giving -usr/--user and -pwd/--password .
- If you do not plan to prepare credential files in your usr account, --usr and --password (or --passwd) can pass your account into tools instead.

---

## License

Use at your own risk. Adapted for geodetic SAR processing workflows.
