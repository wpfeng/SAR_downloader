#!/usr/bin/env python3
"""
CDSE Sentinel-1 Data Query and Download Tool
=============================================
A comprehensive Python script for automatically querying and downloading 
Sentinel-1 data from the ESA Copernicus Data Space Ecosystem (CDSE) using 
the OData API.

Author: CDSE Script Generator
Date: 2026-07-12
Requirements: requests, shapely, pandas, tqdm

Usage:
    python py_cdse_s1downloader.py --config config.json
    python py_cdse_s1downloader.py --search-only --aoi "POLYGON(...)" --start 2026-01-01 --end 2026-01-31
"""

import os
import sys
import json
import time
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Union, Tuple
from urllib.parse import urlencode, quote
import requests
import hashlib
import glob

# Optional imports with graceful fallback
try:
    from shapely.geometry import shape, mapping
    from shapely.wkt import loads as wkt_loads
    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False
    print("Warning: shapely not installed. GeoJSON/WKT polygon support limited.")

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


# =============================================================================
# Configuration
# ===============(==============================================================

CDSE_BASE_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1"
CDSE_DOWNLOAD_URL = "https://download.dataspace.copernicus.eu/odata/v1"
CDSE_AUTH_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"

SENTINEL1_COLLECTION = "SENTINEL-1"

# Sentinel-1 product types commonly used
S1_PRODUCT_TYPES = {
    "IW_SLC__1S": "IW Single Look Complex (Level-1)",
    "IW_GRDH_1S": "IW Ground Range Detected High resolution (Level-1)",
    "IW_GRDM_1S": "IW Ground Range Detected Medium resolution (Level-1)",
    "EW_GRDM_1S": "EW Ground Range Detected Medium resolution (Level-1)",
    "EW_GRDH_1S": "EW Ground Range Detected High resolution (Level-1)",
    "SM_SLC__1S": "SM Single Look Complex (Level-1)",
    "SM_GRDH_1S": "SM Ground Range Detected High resolution (Level-1)",
    "IW_RAW__0S": "IW Level-0 RAW",
    "EW_RAW__0S": "EW Level-0 RAW",
    "SM_RAW__0S": "SM Level-0 RAW",
    "WV_SLC__1S": "WV Single Look Complex (Level-1)",
    "WV_RAW__0S": "WV Level-0 RAW",
    "OCN__2S": "Level-2 Ocean",
}

S1_MODES = ["IW", "EW", "SM", "WV"]
S1_LEVELS = ["0", "1", "2"]
S1_POLARIZATIONS = ["HH", "HV", "VV", "VH", "HH+HV", "VV+VH"]
S1_ORBIT_DIRECTIONS = ["ASCENDING", "DESCENDING"]
#
def check_s1_existing_inlocaldb(file_id):
    #
    dbs = ['/mnt/NAS80T_3/S1/','/mnt/NAS80T_2/S1/','/mnt/NAS80T/S1/']
    #
    for cdb in dbs:
        #
        files = glob.glob(cdb+'/%s.zip' % file_id)
        #
        if len(files)>0:
            #
            return True,files[0]
        #
    #
    return False, None
    #
#
def logging_local(logfile):
    #
    #
    outinfo = ' '.join(sys.argv)
    #
    ctime = datetime.fromtimestamp(time.time()).strftime('%Y-%m-%dT%H:%M:%S') 
    #
    with open(logfile,'a') as fid:
        #
        fid.write('%s: %s\n' % (ctime, outinfo))
#
#
def usr_info():
    #
    noline = 0
    usr_info_file = '/home/wafeng/.cdse'
    try:
       with open(usr_info_file,'r') as fid:
         for cline in fid:
            #
            if noline == 0:
                user = cline.split('\n')[0]
            else:
                passwd = cline.split('\n')[0]
                #
            #
            noline = noline + 1
            #
         #
         #
    except:
        user = None
        passwd = None
        #
    #
    #
    return user, passwd
#
# =============================================================================
# Logging Setup
# =============================================================================

def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """Configure logging with both console and optional file output."""
    logger = logging.getLogger("cdse_s1")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers = []

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # File handler
    if log_file:
        fh = logging.FileHandler(log_file)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    return logger


# =============================================================================
# Authentication
# =============================================================================

class CDSEAuthenticator:
    """Handle CDSE authentication and token management."""

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None
        self.logger = logging.getLogger("cdse_s1.auth")

    def authenticate(self) -> str:
        """Authenticate and obtain access token."""
        self.logger.info("Authenticating with CDSE...")

        payload = {
            "grant_type": "password",
            "username": self.username,
            "password": self.password,
            "client_id": "cdse-public"
        }

        try:
            response = requests.post(CDSE_AUTH_URL, data=payload, timeout=30)
            response.raise_for_status()
            data = response.json()

            self.access_token = data["access_token"]
            self.refresh_token = data.get("refresh_token")
            # Token typically expires in 600 seconds (10 min), set buffer
            expires_in = data.get("expires_in", 600)
            self.token_expiry = datetime.now() + timedelta(seconds=expires_in - 60)

            self.logger.info("Authentication successful.")
            return self.access_token

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Authentication failed: {e}")
            raise

    def get_token(self) -> str:
        """Get valid access token, refresh if needed."""
        if self.access_token is None:
            return self.authenticate()

        if self.token_expiry and datetime.now() >= self.token_expiry:
            self.logger.info("Token expired, refreshing...")
            if self.refresh_token:
                return self._refresh_token()
            else:
                return self.authenticate()

        return self.access_token

    def _refresh_token(self) -> str:
        """Refresh access token using refresh token."""
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": "cdse-public"
        }

        try:
            response = requests.post(CDSE_AUTH_URL, data=payload, timeout=30)
            response.raise_for_status()
            data = response.json()

            self.access_token = data["access_token"]
            if "refresh_token" in data:
                self.refresh_token = data["refresh_token"]
            expires_in = data.get("expires_in", 600)
            self.token_expiry = datetime.now() + timedelta(seconds=expires_in - 60)

            return self.access_token

        except requests.exceptions.RequestException:
            self.logger.warning("Token refresh failed, re-authenticating...")
            return self.authenticate()

    def get_headers(self) -> Dict[str, str]:
        """Get authorization headers for API requests."""
        return {"Authorization": f"Bearer {self.get_token()}"}


# =============================================================================
# Query Builder
# =============================================================================

class S1QueryBuilder:
    """Build OData queries for Sentinel-1 data search."""

    def __init__(self):
        self.filters = []
        self.options = {}
        self.logger = logging.getLogger("cdse_s1.query")

    def set_collection(self, collection: str = SENTINEL1_COLLECTION) -> "S1QueryBuilder":
        """Set collection filter."""
        self.filters.append(f"Collection/Name eq '{collection}'")
        return self

    def set_time_range(self, start: str, end: str) -> "S1QueryBuilder":
        """Set time range filter (ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ)."""
        # Ensure proper format
        start_dt = self._parse_datetime(start)
        end_dt = self._parse_datetime(end)

        self.filters.append(
            f"ContentDate/Start ge {start_dt} and ContentDate/End le {end_dt}"
        )
        return self

    def set_aoi(self, geometry: Union[str, Dict, List]) -> "S1QueryBuilder":
        """Set area of interest using WKT polygon or GeoJSON."""
        wkt = self._to_wkt(geometry)
        self.filters.append(
            f"OData.CSC.Intersects(area=geography'SRID=4326;{wkt}')"
        )
        return self

    def set_product_type(self, product_type: str) -> "S1QueryBuilder":
        """Set product type filter (e.g., IW_SLC__1S, IW_GRDH_1S)."""
        self.filters.append(
            f"Attributes/OData.CSC.StringAttribute/any("
            f"att:att/Name eq 'productType' and "
            f"att/OData.CSC.StringAttribute/Value eq '{product_type}')"
        )
        return self

    def set_orbit_direction(self, direction: str) -> "S1QueryBuilder":
        """Set orbit direction (ASCENDING or DESCENDING)."""
        direction = direction.upper()
        if direction not in S1_ORBIT_DIRECTIONS:
            raise ValueError(f"Invalid orbit direction: {direction}")
        self.filters.append(
            f"Attributes/OData.CSC.StringAttribute/any("
            f"att:att/Name eq 'orbitDirection' and "
            f"att/OData.CSC.StringAttribute/Value eq '{direction}')"
        )
        return self

    def set_relative_orbit(self, orbit_numbers: List[int]) -> "S1QueryBuilder":
        """Set relative orbit number filter."""
        if len(orbit_numbers) == 1:
            self.filters.append(
                f"Attributes/OData.CSC.IntegerAttribute/any("
                f"att:att/Name eq 'relativeOrbitNumber' and "
                f"att/OData.CSC.IntegerAttribute/Value eq {orbit_numbers[0]})"
            )
        else:
            # Multiple orbits - use OR logic
            orbit_filters = []
            for orb in orbit_numbers:
                orbit_filters.append(
                    f"Attributes/OData.CSC.IntegerAttribute/any("
                    f"att:att/Name eq 'relativeOrbitNumber' and "
                    f"att/OData.CSC.IntegerAttribute/Value eq {orb})"
                )
            self.filters.append(f"({' or '.join(orbit_filters)})")
        return self

    def set_polarization(self, polarization: str) -> "S1QueryBuilder":
        """Set polarization mode (e.g., VV, VV+VH, HH+HV)."""
        self.filters.append(
            f"Attributes/OData.CSC.StringAttribute/any("
            f"att:att/Name eq 'polarisationChannels' and "
            f"att/OData.CSC.StringAttribute/Value eq '{polarization}')"
        )
        return self

    def set_name_contains(self, substring: str) -> "S1QueryBuilder":
        """Filter by product name containing substring."""
        self.filters.append(f"contains(Name, '{substring}')")
        return self

    def set_name_starts_with(self, prefix: str) -> "S1QueryBuilder":
        """Filter by product name starting with prefix."""
        self.filters.append(f"startswith(Name, '{prefix}')")
        return self

    def set_orderby(self, field: str = "ContentDate/Start", direction: str = "desc") -> "S1QueryBuilder":
        """Set ordering (asc or desc)."""
        self.options["$orderby"] = f"{field} {direction}"
        return self

    def set_limit(self, limit: int = 20) -> "S1QueryBuilder":
        """Set maximum number of results (max 1000)."""
        self.options["$top"] = min(limit, 1000)
        return self

    def set_skip(self, skip: int = 0) -> "S1QueryBuilder":
        """Set number of results to skip (for pagination)."""
        self.options["$skip"] = skip
        return self

    def set_count(self, enabled: bool = False) -> "S1QueryBuilder":
        """Enable counting total results (slows query)."""
        if enabled:
            self.options["$count"] = "True"
        return self

    def set_expand(self, expand_type: str = "Attributes") -> "S1QueryBuilder":
        """Expand additional metadata (Attributes, Assets, Locations)."""
        self.options["$expand"] = expand_type
        return self

    def build(self) -> str:
        """Build the complete OData query URL."""
        query = f"{CDSE_BASE_URL}/Products?$filter={' and '.join(self.filters)}"

        if self.options:
            params = "&".join([f"{k}={v}" for k, v in self.options.items()])
            query += f"&{params}"

        return query

    @staticmethod
    def _parse_datetime(dt_str: str) -> str:
        """Parse datetime string to ISO 8601 format."""
        # Handle various input formats
        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(dt_str, fmt)
                return parsed.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            except ValueError:
                continue

        # If already in ISO format, return as-is
        if "T" in dt_str and "Z" in dt_str:
            return dt_str

        raise ValueError(f"Cannot parse datetime: {dt_str}")

    @staticmethod
    def _to_wkt(geometry: Union[str, Dict, List]) -> str:
        """Convert various geometry formats to WKT."""
        if isinstance(geometry, str):
            # Already WKT
            if geometry.upper().startswith("POLYGON") or geometry.upper().startswith("POINT"):
                return geometry
            # Try parsing as GeoJSON string
            try:
                geojson = json.loads(geometry)
                return S1QueryBuilder._geojson_to_wkt(geojson)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid geometry string: {geometry}")

        elif isinstance(geometry, dict):
            return S1QueryBuilder._geojson_to_wkt(geometry)

        elif isinstance(geometry, list):
            # Assume list of [lon, lat] coordinates for polygon
            if len(geometry) > 0 and isinstance(geometry[0], (list, tuple)):
                coords = ", ".join([f"{c[0]} {c[1]}" for c in geometry])
                return f"POLYGON(({coords}))"
            else:
                # Single point
                return f"POINT({geometry[0]} {geometry[1]})"

        raise ValueError(f"Unsupported geometry type: {type(geometry)}")

    @staticmethod
    def _geojson_to_wkt(geojson: Dict) -> str:
        """Convert GeoJSON geometry to WKT."""
        geom_type = geojson.get("type", "").upper()
        coords = geojson.get("coordinates", [])

        if geom_type == "POLYGON":
            rings = []
            for ring in coords:
                ring_str = ", ".join([f"{c[0]} {c[1]}" for c in ring])
                rings.append(f"({ring_str})")
            return f"POLYGON({', '.join(rings)})"

        elif geom_type == "MULTIPOLYGON":
            polys = []
            for poly in coords:
                rings = []
                for ring in poly:
                    ring_str = ", ".join([f"{c[0]} {c[1]}" for c in ring])
                    rings.append(f"({ring_str})")
                polys.append(f"({', '.join(rings)})")
            return f"MULTIPOLYGON({', '.join(polys)})"

        elif geom_type == "POINT":
            return f"POINT({coords[0]} {coords[1]})"

        elif HAS_SHAPELY:
            geom = shape(geojson)
            return geom.wkt

        raise ValueError(f"Unsupported GeoJSON type: {geom_type}")


# =============================================================================
# Data Searcher
# =============================================================================

class S1DataSearcher:
    """Search for Sentinel-1 products in CDSE catalog."""

    def __init__(self, authenticator: CDSEAuthenticator):
        self.auth = authenticator
        self.logger = logging.getLogger("cdse_s1.search")
        self.session = requests.Session()

    def search(self, query_url: str) -> List[Dict]:
        """Execute search query and return list of products."""
        self.logger.info(f"Searching: {query_url[:120]}...")

        headers = self.auth.get_headers()
        all_products = []
        next_link = query_url
        page = 1

        while next_link:
            try:
                response = self.session.get(next_link, headers=headers, timeout=60)
                response.raise_for_status()
                data = response.json()

                products = data.get("value", [])
                all_products.extend(products)

                self.logger.info(f"Page {page}: Retrieved {len(products)} products (total: {len(all_products)})")

                # Check for next page
                next_link = data.get("@OData.nextLink")
                page += 1

                # Rate limiting
                if next_link:
                    time.sleep(0.5)

            except requests.exceptions.RequestException as e:
                self.logger.error(f"Search request failed: {e}")
                raise

        self.logger.info(f"Search complete. Total products found: {len(all_products)}")
        return all_products

    def search_all_pages(self, query_builder: S1QueryBuilder, max_results: Optional[int] = None) -> List[Dict]:
        """Search across all pages with optional result limit."""
        all_products = []
        skip = 0
        top = 1000  # Maximum per page

        while True:
            query_builder.set_skip(skip).set_limit(top)
            query_url = query_builder.build()

            products = self.search(query_url)
            if not products:
                break

            all_products.extend(products)

            if max_results and len(all_products) >= max_results:
                all_products = all_products[:max_results]
                break

            if len(products) < top:
                break

            skip += top
            time.sleep(0.5)

        return all_products

    def get_product_by_id(self, product_id: str) -> Dict:
        """Get product details by ID."""
        url = f"{CDSE_BASE_URL}/Products({product_id})"
        headers = self.auth.get_headers()

        response = self.session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_product_attributes(self, product_id: str) -> Dict:
        """Get product attributes/metadata."""
        url = f"{CDSE_BASE_URL}/Products({product_id})?$expand=Attributes"
        headers = self.auth.get_headers()

        response = self.session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Parse attributes into a clean dict
        attrs = {}
        for attr in data.get("Attributes", {}).get("value", []):
            attrs[attr.get("Name", "")] = attr.get("Value", "")

        return attrs


# =============================================================================
# Data Downloader
# =============================================================================

class S1DataDownloader:
    """Download Sentinel-1 products from CDSE."""

    def __init__(self, authenticator: CDSEAuthenticator, output_dir: str = "./downloads"):
        self.auth = authenticator
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("cdse_s1.download")
        self.session = requests.Session()

    def download_product(self, product_id: str, product_name: Optional[str] = None,
                         compressed: bool = True, verify: bool = True) -> str:
        """
        Download a single product by ID.

        Args:
            product_id: Product UUID from catalog
            product_name: Optional filename (derived from product if not provided)
            compressed: Download as zip ($zip) or native ($value)
            verify: Verify checksum after download

        Returns:
            Path to downloaded file
        """
        if not product_name:
            product_name = f"{product_id}.zip"

        # Determine extension
        ext = ".zip" if compressed else ".SAFE"
        #
        #
        #
        if not product_name.endswith(ext):
            product_name = product_name.split('.SAFE')[0]
            #
            product_name = f"{product_name}{ext}"

        output_path = self.output_dir / product_name
        #  
        # Check if already downloaded
        if output_path.exists():
            self.logger.info(f"File already exists: {output_path}")
            if verify:
                # Could add checksum verification here
                pass
            return str(output_path)

        # Build download URL
        endpoint = "$zip" if compressed else "$value"
        download_url = f"{CDSE_DOWNLOAD_URL}/Products({product_id})/{endpoint}"

        self.logger.info(f"Downloading: {product_name}")
        self.logger.info(f"URL: {download_url}")

        headers = self.auth.get_headers()

        try:
            response = self.session.get(
                download_url, 
                headers=headers, 
                stream=True, 
                timeout=300
            )
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))

            # Download with progress bar
            if HAS_TQDM and total_size > 0:
                progress = tqdm(
                    total=total_size, 
                    unit="B", 
                    unit_scale=True, 
                    desc=product_name[:40]
                )
                with open(output_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            progress.update(len(chunk))
                progress.close()
            else:
                with open(output_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

            self.logger.info(f"Download complete: {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")
            return str(output_path)

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Download failed: {e}")
            # Clean up partial download
            if output_path.exists():
                output_path.unlink()
            raise

    def download_products(self, products: List[Dict], 
                          compressed: bool = True,
                          skip_existing: bool = True) -> List[str]:
        """
        Download multiple products.

        Args:
            products: List of product dicts from search results
            compressed: Download as zip or native format
            skip_existing: Skip if file already exists

        Returns:
            List of downloaded file paths
        """
        downloaded = []
        failed = []

        for i, product in enumerate(products):
            product_id = product.get("Id", "")
            product_name = product.get("Name", product_id)
            #
            self.logger.info(f"[{i+1}/{len(products)}] Processing: {product_name}")
            #
            fileID = product_name.split('.SAFE')[0]
            #
            #
            # an option for FengLab, 2026/07/15
            #
            existingflag, filepath = check_s1_existing_inlocaldb(fileID)
            #
            if existingflag:
                #
                # link existing S1 zip file into local ...
                #
                goStr = 'ln -s %s %s/.' % (filepath, self.output_dir)
                os.system(goStr)
            #
            #
            try:
                path = self.download_product(
                    product_id, 
                    product_name, 
                    compressed=compressed
                )
                downloaded.append(path)

                # Rate limiting between downloads
                if i < len(products) - 1:
                    time.sleep(1)

            except Exception as e:
                self.logger.error(f"Failed to download {product_name}: {e}")
                failed.append({"id": product_id, "name": product_name, "error": str(e)})

        self.logger.info(f"Download summary: {len(downloaded)} succeeded, {len(failed)} failed")

        if failed:
            failed_log = self.output_dir / "failed_downloads.json"
            with open(failed_log, "w") as f:
                json.dump(failed, f, indent=2)
            self.logger.info(f"Failed downloads logged to: {failed_log}")

        return downloaded

    def download_quicklook(self, product_id: str, output_name: Optional[str] = None) -> str:
        """Download product quicklook image."""
        if not output_name:
            output_name = f"{product_id}_quicklook.jpg"

        output_path = self.output_dir / output_name

        # Quicklook is available via Assets
        url = f"{CDSE_BASE_URL}/Products({product_id})?$expand=Assets"
        headers = self.auth.get_headers()

        try:
            response = self.session.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            assets = data.get("Assets", {}).get("value", [])
            quicklook = None
            for asset in assets:
                if "quicklook" in asset.get("Type", "").lower():
                    quicklook = asset
                    break

            if not quicklook:
                self.logger.warning(f"No quicklook found for {product_id}")
                return ""

            download_url = quicklook.get("DownloadLink", "")
            if not download_url:
                return ""

            img_response = self.session.get(download_url, headers=headers, stream=True, timeout=60)
            img_response.raise_for_status()

            with open(output_path, "wb") as f:
                for chunk in img_response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            self.logger.info(f"Quicklook saved: {output_path}")
            return str(output_path)

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Quicklook download failed: {e}")
            return ""


# =============================================================================
# Results Manager
# =============================================================================

class ResultsManager:
    """Manage and export search results."""

    def __init__(self, output_dir: str = "./results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("cdse_s1.results")

    def to_json(self, products: List[Dict], filename: str = "search_results.json") -> str:
        """Export results to JSON."""
        path = self.output_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(products, f, indent=2, ensure_ascii=False)
        self.logger.info(f"Results saved to JSON: {path}")
        return str(path)

    def to_csv(self, products: List[Dict], filename: str = "search_results.csv") -> str:
        """Export results to CSV."""
        if not HAS_PANDAS:
            self.logger.warning("pandas not installed, skipping CSV export")
            return ""

        # Flatten nested dicts for DataFrame
        flattened = []
        for p in products:
            flat = {
                "Id": p.get("Id", ""),
                "Name": p.get("Name", ""),
                "ContentType": p.get("ContentType", ""),
                "ContentLength": p.get("ContentLength", 0),
                "OriginDate": p.get("OriginDate", ""),
                "PublicationDate": p.get("PublicationDate", ""),
                "ModificationDate": p.get("ModificationDate", ""),
                "Online": p.get("Online", False),
                "S3Path": p.get("S3Path", ""),
            }

            # Add ContentDate
            content_date = p.get("ContentDate", {})
            flat["StartDate"] = content_date.get("Start", "")
            flat["EndDate"] = content_date.get("End", "")

            # Add GeoFootprint
            geo = p.get("GeoFootprint", {})
            flat["GeometryType"] = geo.get("type", "")

            flattened.append(flat)

        df = pd.DataFrame(flattened)
        path = self.output_dir / filename
        df.to_csv(path, index=False, encoding="utf-8")
        self.logger.info(f"Results saved to CSV: {path}")
        return str(path)

    def to_geojson(self, products: List[Dict], filename: str = "search_results.geojson") -> str:
        """Export results to GeoJSON."""
        features = []
        for p in products:
            geo = p.get("GeoFootprint")
            if geo:
                feature = {
                    "type": "Feature",
                    "geometry": geo,
                    "properties": {
                        "Id": p.get("Id", ""),
                        "Name": p.get("Name", ""),
                        "StartDate": p.get("ContentDate", {}).get("Start", ""),
                        "EndDate": p.get("ContentDate", {}).get("End", ""),
                        "PublicationDate": p.get("PublicationDate", ""),
                    }
                }
                features.append(feature)

        geojson = {
            "type": "FeatureCollection",
            "features": features
        }

        path = self.output_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(geojson, f, indent=2, ensure_ascii=False)

        self.logger.info(f"Results saved to GeoJSON: {path}")
        return str(path)

    def print_summary(self, products: List[Dict]):
        """Print a summary table of results."""
        if not products:
            print("No products found.")
            return

        print(f"\n{'='*100}")
        print(f"Search Results Summary: {len(products)} products found")
        print(f"{'='*100}")
        print(f"{'#':<4} {'Name':<50} {'Start Date':<25} {'Size (MB)':<12}")
        print(f"{'-'*100}")

        for i, p in enumerate(products[:20]):  # Show first 20
            name = p.get("Name", "N/A")[:48]
            start = p.get("ContentDate", {}).get("Start", "N/A")[:23]
            size = p.get("ContentLength", 0) / 1024 / 1024
            print(f"{i+1:<4} {name:<50} {start:<25} {size:<12.1f}")

        if len(products) > 20:
            print(f"... and {len(products) - 20} more products")

        print(f"{'='*100}\n")


# =============================================================================
# Main Application
# =============================================================================

class CDSES1Downloader:
    """Main application class orchestrating search and download."""

    def __init__(self, username: str, password: str, 
                 output_dir: str = "./downloads",
                 results_dir: str = "./results"):
        self.logger = logging.getLogger("cdse_s1")
        self.auth = CDSEAuthenticator(username, password)
        self.searcher = S1DataSearcher(self.auth)
        self.downloader = S1DataDownloader(self.auth, output_dir)
        self.results = ResultsManager(results_dir)

    def search(self, 
               start_date: str,
               end_date: str,
               aoi: Optional[Union[str, Dict, List]] = None,
               product_type: Optional[str] = None,
               orbit_direction: Optional[str] = None,
               relative_orbit: Optional[List[int]] = None,
               polarization: Optional[str] = None,
               name_contains: Optional[str] = None,
               limit: int = 1000,
               orderby: str = "ContentDate/Start desc") -> List[Dict]:
        """
        Search for Sentinel-1 products.

        Args:
            start_date: Start date (YYYY-MM-DD or ISO 8601)
            end_date: End date (YYYY-MM-DD or ISO 8601)
            aoi: Area of interest (WKT, GeoJSON, or coordinate list)
            product_type: Product type (e.g., IW_SLC__1S, IW_GRDH_1S)
            orbit_direction: ASCENDING or DESCENDING
            relative_orbit: List of relative orbit numbers
            polarization: Polarization mode (VV, VV+VH, etc.)
            name_contains: Substring to match in product name
            limit: Maximum results to return
            orderby: Sort order

        Returns:
            List of product dictionaries
        """
        builder = S1QueryBuilder()
        builder.set_collection()
        builder.set_time_range(start_date, end_date)

        if aoi:
            builder.set_aoi(aoi)
        if product_type:
            builder.set_product_type(product_type)
        if orbit_direction:
            builder.set_orbit_direction(orbit_direction)
        if relative_orbit:
            builder.set_relative_orbit(relative_orbit)
        if polarization:
            builder.set_polarization(polarization)
        if name_contains:
            builder.set_name_contains(name_contains)

        builder.set_orderby(*orderby.rsplit(" ", 1))
        builder.set_limit(limit)
        builder.set_expand("Attributes")

        query_url = builder.build()
        products = self.searcher.search(query_url)

        return products

    def download(self, products: List[Dict], compressed: bool = True) -> List[str]:
        """Download a list of products."""
        return self.downloader.download_products(products, compressed=compressed)

    def search_and_download(self, **kwargs) -> Tuple[List[Dict], List[str]]:
        """Search and download in one step."""
        products = self.search(**kwargs)

        if not products:
            self.logger.warning("No products found matching criteria.")
            return products, []

        # Save search results
        self.results.to_json(products)
        self.results.to_csv(products)
        self.results.to_geojson(products)
        self.results.print_summary(products)

        # Ask for confirmation before download (if interactive)
        if sys.stdin.isatty():
            confirm = input(f"\nDownload {len(products)} products? [Y/n]: ").strip().lower()
            if confirm and confirm not in ("y", "yes"):
                self.logger.info("Download cancelled by user.")
                return products, []

        downloaded = self.download(products)
        return products, downloaded


# =============================================================================
# CLI Interface
# =============================================================================

def create_sample_config():
    """Create a sample configuration file."""
    config = {
        "credentials": {
            "username": "your_cdse_username",
            "password": "your_cdse_password"
        },
        "search": {
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "product_type": "IW_SLC__1S",
            "orbit_direction": "ASCENDING",
            "aoi": {
                "type": "Polygon",
                "coordinates": [[
                    [116.0, 39.5],
                    [116.5, 39.5],
                    [116.5, 40.0],
                    [116.0, 40.0],
                    [116.0, 39.5]
                ]]
            }
        },
        "download": {
            "output_dir": "./downloads",
            "compressed": True,
            "skip_existing": True
        }
    }

    with open("cdse_config_sample.json", "w") as f:
        json.dump(config, f, indent=2)
    print("Sample config created: cdse_config_sample.json")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="CDSE Sentinel-1 Data Query and Download Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Search only (no download)
  python py_cdse_s1downloader.py --search-only -u user -p pass \
      --start 2026-01-01 --end 2026-01-31 --aoi "POLYGON((116 39.5, 116.5 39.5, 116.5 40, 116 40, 116 39.5))"

  # Search and download IW SLC data
  python py_cdse_s1downloader.py -u user -p pass \
      --start 2026-01-01 --end 2026-01-31 --product-type IW_SLC__1S \
      --aoi aoi.geojson --orbit-direction ASCENDING

  # Use config file
  python py_cdse_s1downloader.py --config config.json

  # Create sample config
  python py_cdse_s1downloader.py --sample-config
  
  # Use a roi for region search
  python py_cdse_s1downloader.py --start 2026-01-01 --end 2026-01-31 --product-type IW_SLC__1S --roi 116,117,39.5,40

        """
    )

    parser.add_argument("-u", "--username", help="CDSE username")
    parser.add_argument("-p", "--password", help="CDSE password")
    parser.add_argument("--config", help="Path to JSON config file")

    parser.add_argument("--search-only", action="store_true", help="Only search, do not download")
    parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    parser.add_argument("--aoi", help="Area of interest (WKT string, GeoJSON file, or coordinate list)")
    #
    parser.add_argument("--roi", help="ROI: lonmin,lonmax,latmin,latmax. If given, aoi will be reset!")
    #
    parser.add_argument("--product-type", help="Product type (e.g., IW_SLC__1S, IW_GRDH_1S)",default="IW_SLC__1S")
    # 
    parser.add_argument("--orbit-direction", choices=["ASCENDING", "DESCENDING"], help="Orbit direction")
    parser.add_argument("--relative-orbit", type=int, nargs="+", help="Relative orbit number(s)")
    parser.add_argument("--polarization", help="Polarization (VV, VV+VH, HH+HV, etc.)")
    parser.add_argument("--name-contains", help="Filter by name substring")
    parser.add_argument("--limit", type=int, default=1000, help="Maximum results (default: 1000)")
    
    parser.add_argument("--output-dir", default="./", help="Download output directory")
    parser.add_argument("--results-dir", default="./results", help="Results output directory")
    parser.add_argument("--no-compressed", action="store_true", help="Download native format instead of zip")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--log-file", help="Log file path")

    parser.add_argument("--sample-config", action="store_true", help="Create sample config file and exit")
    #
    parser.add_argument("--download", action="store_true", help="trigger a downloading")
    #
    return parser.parse_args()


def load_config(config_path: str) -> Dict:
    """Load configuration from JSON file."""
    with open(config_path, "r") as f:
        return json.load(f)


def main():
    """Main entry point."""
    args = parse_args()

    if args.sample_config:
        create_sample_config()
        return
    #
    if args.roi is not None:
        #
        ll = [float(croi) for croi in args.roi.split(',')]
        args.aoi = "POLYGON((%f  %f,%f %f,%f %f,%f %f,%f %f))" % (ll[0],ll[2],ll[1],ll[2],ll[1],ll[3],ll[0],ll[3],ll[0],ll[2])
        #
    #
    # Setup logging
    logger = setup_logging(args.log_level, args.log_file)
    # 
    # Load credentials and parameters
    username,password = usr_info()
    #
    if username is None:
       username = args.username
       password = args.password
    #
    #
    search_params = {}
    download_params = {}
    #
    if args.config:
        config = load_config(args.config)
        creds = config.get("credentials", {})
        username = username or creds.get("username")
        password = password or creds.get("password")

        search_cfg = config.get("search", {})
        search_params = {
            "start_date": search_cfg.get("start_date"),
            "end_date": search_cfg.get("end_date"),
            "aoi": search_cfg.get("aoi"),
            "product_type": search_cfg.get("product_type"),
            "orbit_direction": search_cfg.get("orbit_direction"),
            "relative_orbit": search_cfg.get("relative_orbit"),
            "polarization": search_cfg.get("polarization"),
            "name_contains": search_cfg.get("name_contains"),
            "limit": search_cfg.get("limit", 1000),
        }

        dl_cfg = config.get("download", {})
        download_params = {
            "compressed": dl_cfg.get("compressed", True),
        }
    #
    # Override with CLI args
    if args.start:
        search_params["start_date"] = args.start
    if args.end:
        search_params["end_date"] = args.end
    if args.aoi:
        # Try to parse AOI
        aoi = args.aoi
        if os.path.isfile(aoi):
            with open(aoi, "r") as f:
                aoi = json.load(f)
        search_params["aoi"] = aoi
    if args.product_type:
        search_params["product_type"] = args.product_type
    if args.orbit_direction:
        search_params["orbit_direction"] = args.orbit_direction
    if args.relative_orbit:
        search_params["relative_orbit"] = args.relative_orbit
    if args.polarization:
        search_params["polarization"] = args.polarization
    if args.name_contains:
        search_params["name_contains"] = args.name_contains
    if args.limit:
        search_params["limit"] = args.limit

    # Validate required parameters
    if not username or not password:
        logger.error("Username and password are required. Use -u/-p or --config.")
        sys.exit(1)

    if not search_params.get("start_date") or not search_params.get("end_date"):
        logger.error("Start and end dates are required.")
        sys.exit(1)

    # Initialize downloader
    try:
        app = CDSES1Downloader(
            username=username,
            password=password,
            output_dir=args.output_dir,
            results_dir=args.results_dir
        )
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        sys.exit(1)

    # Execute search
    try:
        logger.info("Starting search...")
        products = app.search(**search_params)
        #
        #
        # Save results
        app.results.to_json(products)
        app.results.to_csv(products)
        app.results.to_geojson(products)
        app.results.print_summary(products)

        if args.search_only:
            logger.info("Search-only mode. Results saved, exiting.")
            return

        if not products:
            logger.warning("No products found. Exiting.")
            return

        # Confirm download
        if sys.stdin.isatty():
            #
            # confirm = input(f"\nDownload {len(products)} products? [Y/n]: ").strip().lower()
            # if confirm and confirm not in ("y", "yes"):
            #
            #
            if not args.download:
                logger.info("Download cancelled.")
                return

        # Download
        compressed = not args.no_compressed
        downloaded = app.download(products, compressed=compressed)

        logger.info(f"\nCompleted! Downloaded {len(downloaded)} products to {args.output_dir}")

    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    #
    outlog = os.path.basename(sys.argv[0]).split('.py')[0]+'.log'
    logging_local(outlog)
    #
    #
    main()
