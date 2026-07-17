#!/usr/bin/env python
#
import os
import sys
#
from tqdm import tqdm
import asf_search as asf
import pandas as pd
from datetime import datetime
#
#
def download_data(products, output_dir='./data', username=None, password=None):
    """
    下载搜索到的数据产品

    参数:
        products (list): 产品列表
        output_dir (str): 输出目录
        username (str): NASA Earthdata用户名
        password (str): NASA Earthdata密码
    """
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)

    # 如果未提供凭证，则尝试从环境变量获取
    if not username or not password:
        username = os.environ.get('EARTHDATA_USERNAME')
        password = os.environ.get('EARTHDATA_PASSWORD')

    if not username or not password:
        print("错误: 需要提供NASA Earthdata用户名和密码")
        return

    # 创建认证会话
    session = asf.ASFSession()
    session.auth_with_creds(username, password)

    # 逐个下载产品
    for product in tqdm(products, desc="下载进度"):
        try:
            # 获取产品文件名
            filename = os.path.join(output_dir, product.properties['fileName'])

            # 检查文件是否已存在（断点续传）
            if os.path.exists(filename):
                file_size = os.path.getsize(filename)
                if file_size == int(product.properties['size']):
                    print(f"文件 {filename} 已完整下载，跳过")
                    continue

            # 下载产品
            product.download(path=output_dir, session=session)
            print(f"已下载: {filename}")
        except Exception as e:
            print(f"下载 {product.properties['fileName']} 时出错: {e}")
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
def search_and_save_sentinel1_data(wkt, start_date, end_date, output_csv,download,usr,passwd):
    """
    Search for Sentinel-1 SAR data within specified spatial and temporal ranges,
    and save the results to a CSV file.

    Args:
        wkt (str): Well-Known Text representation of the spatial area
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
        output_csv (str): Path to output CSV file
    """
    # Convert date strings to datetime objects
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')

    # Set search parameters
    search_parameters = {
        'platform': asf.PLATFORM.SENTINEL1,
        'processingLevel': [asf.PRODUCT_TYPE.SLC],
        'start': start,
        'end': end,
        'intersectsWith': wkt
    }

    try:
        # Execute the search
        print("Searching for data...")
        results = asf.search(**search_parameters)
        print(f"Found {len(results)} matching datasets")

        if not results:
            print("No data found. Exiting.")
            return
        #
        # Extract relevant metadata
        data_list = []
        for i,product in enumerate(results):
            #
            if download:
               download_data(product, output_dir='./data', username=usr, password=passwd)
            #
            data = {
                'granule_name': "",
                'platform': product.properties['platform'],
                'beam_mode': product.properties['beamModeType'],
                'polarization': product.properties['polarization'],
                'processing_level': product.properties['processingLevel'],
                'start_time': product.properties['startTime'],
                'flight_direction': product.properties['flightDirection'],
                'url': product.properties['url']
            }
            data_list.append(data)
            #

        #
        # Convert to DataFrame and save as CSV
        df = pd.DataFrame(data_list)
        df.to_csv(output_csv, index=False)
        print(f"Data saved successfully to {output_csv}")

    except Exception as e:
        print(f"An error occurred during the search: {e}")
#
if len(sys.argv)<3:
    #
    helpstr = \
            '''
            %s <start_date1> <end_date2> <roi> <out_csv> 
            ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
            To get Sentinel-1 SLC datalist using asf_search

            Example:
            %s 2025-06-01 2025-07-30 87.2,88.1,28.2,29 s1_output.csv 
            '''
    #
    print(helpstr % (sys.argv[0],sys.argv[0]))
    sys.exit(-1)
#
download = False
for i,key in enumerate(sys.argv):
    #
    if key == '-download':
        download = True
        #
    #
#
log(sys.argv)
#
#
if __name__ == "__main__":
    #
    # Example WKT (rectangular area around Beijing)
    #
    example_wkt = 'POLYGON((115.4 39.4,117.6 39.4,117.6 41.0,115.4 41.0,115.4 39.4))'
    #
    #
    roi = [float(croi) for croi in sys.argv[3].split(',')]
    lonmin = roi[0]
    lonmax = roi[1]
    latmin = roi[2]
    latmax = roi[3]
    #
    example_wkt = 'POLYGON((%f %f,%f %f,%f %f,%f %f,%f %f))' % (lonmin,latmin,\
                                                                lonmax,latmin,\
                                                                lonmax,latmax,\
                                                                lonmin,latmax,\
                                                                lonmin,latmin)
    #
    #
    # Set search parameters
    START_DATE = sys.argv[1] #'2025-06-01'  # Start date
    END_DATE = sys.argv[2] #'2025-07-30'    # End date
    OUTPUT_CSV = sys.argv[4] #'sentinel1_data_DingriEQ.csv'  # Output filename

    # Execute search and save
    #
    #
    usr,passwd = get_passwd()
    search_and_save_sentinel1_data(example_wkt, START_DATE, END_DATE, OUTPUT_CSV,False,usr,passwd)
    #
    df = pd.read_csv(OUTPUT_CSV, skip_blank_lines=True)
    #
    urls = df['url']
    #
    outlist = OUTPUT_CSV.replace('.csv','.list')
    #
    with open(outlist,'w') as fid:
      for i in range(len(urls)):
          # print(urls[i])
          #
          cfile = urls[i].split('/')[-1]
          fid.write('%s\n' % urls[i])
          #
      #
    #
    #
    if download:
       #
       #
       goGetit = 'pSAR_alask_s1downloading_url.py %s aria -usr %s -pwd %s' % \
                 (outlist,usr,passwd)
       #
       print(" %s" % goGetit)
       os.system(goGetit)

