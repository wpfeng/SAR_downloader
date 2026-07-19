#!/usr/bin/env python
#
# NISAR Data Auto-Search, download & packaging...
#
import sys
import os
import getpass
import asf_search as asf
import shutil
import zipfile
from datetime import datetime
import logging
#import pSAR
import json
import geojson
import simplekml
from pygeoif import geometry
#
def log(funcin,logname=None,info='Start'):
    '''
    Log inputs of a script to a local ascii file
    by Wanpeng Feng, @NRcan, 2017-08-21
    '''
    p_func  = funcin[0]
    #
    if logname is None:
       logname = os.path.basename(p_func)
       logname = os.path.splitext(logname)[0]+'.log'
    # cnow = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')
    cnow = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')
    #
    print(" *** %s @%s into %s" % (info,cnow,logname))
    try:
      with open(logname,'a') as fid:
        fid.write('%s: ' % cnow)
        for i,ckey in enumerate(funcin):
           if i < len(funcin)-1:
              fid.write('%s ' % funcin[i])
           else:
              fid.write('%s\n' % funcin[i])
        #
        fid.close()
    except:
        print("ERROR: %s cannot be written in the current folder!!!" % logname)
    #
    if os.path.exists(logname):
       return True
    else:
       return False
######
def nisarinfo2kml(results,outkml):
    #
    kml = simplekml.Kml()
    #
    kml.document.name = "ASF Search Results"

    # ====================== 3. Iterate Through Results to Build KML Features ======================
    print(f"Found {len(results)} ASF products, converting to KML...")
    for idx, product in enumerate(results):
        # ---- 3.1 Extract Core Attributes (customize as needed) ----
        props = {
            "Product ID": product.properties["sceneName"],
            "Platform": product.properties["platform"],
            "Acquisition Time": product.properties["startTime"],
            "Processing Level": product.properties["processingLevel"],
            "Download URL": product.properties["url"]
        }

        # ---- 3.2 Extract Spatial Geometry (Polygon/Point) ----
        # ASF product spatial extent: product.geometry is GeoJSON-formatted Polygon
        geom = product.geometry
        if geom["type"] != "Polygon":
            # Use centroid if no full polygon (for products without complete spatial extent)
            center_lon = (geom["bbox"][0] + geom["bbox"][2]) / 2
            center_lat = (geom["bbox"][1] + geom["bbox"][3]) / 2
            # Create KML Point feature
            point = kml.newpoint(
                name=f"ASF_Product_{idx+1}",  # KML feature name
                coords=[(center_lon, center_lat)],  # Coordinate order: lon, lat (KML standard)
                description="\n".join([f"{k}: {v}" for k, v in props.items()])  # Attributes as description
            )
            # Optional: Customize point style (red pushpin)
            point.style.iconstyle.icon.href = "http://maps.google.com/mapfiles/kml/pushpin/red-pushpin.png"
        else:
            # Extract polygon coordinates (ASF geometry format: [[[lon1,lat1], [lon2,lat2], ...]])
            polygon_coords = geom["coordinates"][0]
            # Create KML Polygon feature
            polygon = kml.newpolygon(
                name=f"ASF_Product_{idx+1}",
                outerboundaryis=polygon_coords,  # Polygon outer ring
                description="\n".join([f"{k}: {v}" for k, v in props.items()])
            )
            # Optional: Customize polygon style (semi-transparent blue)
            polygon.style.polystyle.color = simplekml.Color.changealphaint(100, simplekml.Color.blue)
            polygon.style.polystyle.outline = True  # Show polygon outline

    # ====================== 4. Save KML File ======================
    kml.save(outkml)
    print(f"✅ Successfully saved KML file: {outkml}")
    print(f"📌 Generated {len(results)} KML features")
    #
def convert_to_asf_params(ext, start_time, end_time):
    #
    try:
        minlon, maxlon, minlat, maxlat = map(float, ext.split(','))
        ext = f"POLYGON(({minlon} {minlat}, {maxlon} {minlat}, {maxlon} {maxlat}, {minlon} {maxlat}, {minlon} {minlat}))"
    except Exception as e:
        print(f"[!] Coordinate error:{e}")
        sys.exit(-1)
    #
    def to_iso(d_str):
        return datetime.strptime(d_str, '%Y-%m-%d').strftime('%Y-%m-%dT%H:%M:%SZ')
    start_time = to_iso(start_time)
    end_time   = to_iso(end_time)
    return ext, start_time, end_time
    #
def pack_to_zip(granule_id, target_dir):
    #
    # Package all SAR files of one scene into a single ZIP file.
    #
    zip_filename = f"{granule_id}.zip"
    zip_path = os.path.join(target_dir, zip_filename)
    
    if os.path.exists(zip_path):
        #
        return zip_path
        #
    files_to_pack = [
        f for f in os.listdir(target_dir) 
        if f.startswith(granule_id) and not f.endswith('.zip')
    ]
    #
    if not files_to_pack:
        return None
    #
    print(f" +++ Packaging {granule_id} (total {len(files_to_pack)} files)...")
    #
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for f in files_to_pack:
            file_full_path = os.path.join(target_dir, f)
            zipf.write(file_full_path, arcname=f)
            #
            os.remove(file_full_path)
    #
    return zip_path
    #
#
def get_passwd():
    #
    usr = []
    passwd = []
    with open('/home/wafeng/.asf/passwd','r') as fid:
        for cline in fid:
            #
            tmp = cline.split('\n')[0].split()
            #
            usr = tmp[0]
            passwd = tmp[1]
            #
        #
    #
    return usr,passwd

#

if len(sys.argv) < 2:
   #
   helpstr = \
   '''
       %s <start_time> <end_time> <ext> -track [None in default] -user [] -pwd [] -download -zip -only_h5 -nisar_db
                                        [-outkml asf_nisar.kml]
       ++++++++++++++
       To search / download NISAR data directly from ASF...
       
       <end_time> should be in a format as 2025-06-01
       ++++++++++++++
   '''
   print(helpstr % sys.argv[0])
   sys.exit(-1)
   #
#
# pSAR.util.log(sys.argv)
log(sys.argv)
#
if True:
   #
   start_input = sys.argv[1]
   end_input   = sys.argv[2]
   ext_t       = sys.argv[3] #.split(',')
   ext, start_time, end_time = convert_to_asf_params(ext_t, start_input, end_input)
   #
   print(" Given extension: ", ext)
   # print(ext)
   outkml = 'asf_nisar.kml'
   tozip = False
   track = None
   only_h5 = False
   user = ''
   pwd = ""
   nisar_db = os.getcwd()
   #
   go_download = False
   #
   user,pwd = get_passwd()
   #
   #####
   if 'NISAR_DB' in os.environ:
       #
       nisar_db = os.environ['NISAR_DB']
   #
   #
   for i,key in enumerate(sys.argv):
       #
       if key == '-download':
           go_download=True
       if key == '-only_h5':
          only_h5 = True
       if key == '-zip':
          tozip = True
       if key == '-user':
          user = sys.argv[i+1]
       if key == '-pwd':
          pwd = sys.argv[i+1]
       if key == '-track':
          track = sys.argv[i+1]
       if key == '-nisar_db':
          nisar_db = sys.argv[i+1]
       if key == '-outkml':
          outkml = sys.argv[i+1]
       #
   #####
   #
   if not os.path.exists(nisar_db):
       os.makedirs(nisar_db)
       #
   #
   print(f" +++ Retrieving NISAR L1_RSLC data...")
   print(f" +++ roi: {ext_t}")
   print(f" +++ Range: {start_time} to {end_time}")
   #
   # pwd = getpass.getpass("Earthdata Password: ")
   #
   print(track)
   #
   try:
           session = asf.ASFSession().auth_with_creds(user, pwd)
   except Exception as e:
           print(f"[!] Loading error: {e}")
           sys.exit(-1)
   results = asf.search(
           dataset=asf.DATASET.NISAR,
           intersectsWith=ext,
           start=start_time,
           end=end_time,
           processingLevel=asf.PRODUCT_TYPE.RSLC,
           relativeOrbit=int(track),
           maxResults=9999
   )
   #
   #
   nisarinfo2kml(results,outkml)
   #
   #
   if not results:
       print(" --- No NISAR L1_RSLC data retrieved.")
       sys.exit(0)
       #
   print(f" +++ {len(results)} scenes have retrieved...")
   print(f" +++ Starting download...")
   #
   if go_download:
      SAR_download = []
      for product in results:
          granule_id = product.properties['sceneName']
          print(f"\n>>> processing: {granule_id}")  
          zip_name = f"{granule_id}.zip"  
          zip_phys_path = os.path.join(nisar_db, zip_name)
          #
          if not os.path.exists(zip_phys_path):
               SAR_download.append(product)
          else:
               print(f" [Skip] {granule_id} already exists.")
          urls = product.properties['url']
          #print(urls)
          urls2 = product.find_urls(pattern=r'.*\.(h5|kml|png|csv|pdf|xml|yaml)')
          filtered = [
              u for u in urls2
              if not u.endswith('.log') and not u.endswith('thumbnail.png')
          ]
          #print(filtered)
          if only_h5 == False:
              #
              print(f"+++++++++++++++++++++++")
              asf.download_urls(
                   urls=filtered,
                   path=nisar_db,
                   session=session,
                   processes=6
              )
              #
          else:
              #
              print(f"\n>>> processing: {granule_id} for hdf5 only!!!")
              #
              # aria2_GO = 'aria2c -c --http-auth-challenge=true --http-user=%s --http-passwd=%s "https://api.daac.asf.alaska.edu/services/search/param?granule_list=%s&output=metalink" --check-certificate=false -o %s.zip' % (usr,pwd,bname,bname)
              #
              print(urls)
              #
              outh5 = urls.split('/')[-1]
              #
              aria2_GO = 'aria2c -c --http-auth-challenge=true --http-user=%s --http-passwd=%s "%s" --check-certificate=false -o %s' % (user,pwd,urls,outh5)
              print(aria2_GO)
              #
              os.system(aria2_GO)
              #
              #asf.download_urls(
              #     urls=urls,
              #     path=nisar_db,
              #     session=session,
              #     processes=6
              #)
              #
       
          if tozip == True:
              zip_phys_path = pack_to_zip(granule_id, nisar_db)
              #
          #
          print(f"Download finished: {granule_id}")  
      print(f" +++ All tasks completed successfully.")


