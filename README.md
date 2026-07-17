Here we share serveral python scripts to help search/download SAR data from ESA/CDSE (Copernicus Data Space Ecosystem) system and/or ASF (Alaska Satellite Facility) data center.

py_cdse_s1downloader.py is designed to search and download Sentinel-1 TOPS SAR data from ESA/CDSE server.
*********************************************************************************************************
   # Install dependencies
   pip install requests shapely pandas tqdm
   #
   # example one to search data info only. Note that user and passwd are required...
   
   python py_cdse_s1downloader.py --usr <usr> --password <password> \
      --start 2024-01-01 --end 2024-01-31 \
      --roi 116,117,39.5,40 \
      --search-only

   # example two to search and downad with python
   python py_cdse_s1downloader.py --usr <usr> --password <password> \
      --start 2024-01-01 --end 2024-01-31 \
      --roi 116,117,39.5,40 \
      --download

py_asf_searchS1.py is designed to saerch and download Sentinel-1 TOPS SAR data from ASF data center.
********************************************************************************************************
   # Install dependencies
   pip install asf_search pandas tqdm
   Note that aria2c is strongly recommanded to install in your server to use for downloading the data.
   
   # example one to search Sentinel-1 data only
   python py_asf_searchS1.py 2025-06-01 2025-07-30 87.2,88.1,28.2,29 s1_output.csv --usr <usr> --password <password>
   
   # example one to search and download Sentinel-1 data 
   python py_asf_searchS1.py 2025-06-01 2025-07-30 87.2,88.1,28.2,29 s1_output.csv --usr <usr> --password <password> -download


py_asf_NISARdownloader.py is designed to search and download NISAR SAR data from ASF data center
********************************************************************************************************
   # Install dependencies
   pip install asf_search pandas tqdm
   
   
