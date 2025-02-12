#!/usr/bin/env python3
import requests
import os.path
import time


#year=2020
#days=range(1,25)
year=2023
days=range(25,30)
hours=[0,6,12,18]

#url = "https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.20240701/00/atmos/gfs.t00z.pgrb2.0p25.f000"

max_retries=4
timeout=1

for day in days:
    for hour in hours:
        for fchr in range(0,6):
            url_base = "https://noaa-gfs-bdp-pds.s3.amazonaws.com/"
            url_path = f"gfs.{year}07{day:02}/{hour:02}/atmos/gfs.t{hour:02}z.pgrb2.0p25.f{fchr:03}"
            url = url_base + url_path
            #
            output_file = f"{year}/{year}07{day:02}-{hour:02}-gfs.t{hour:02}z.pgrb2.0p25.f{fchr:03}"
            print(f"{url} -> {output_file}")
            #
            temp_output_file="in_progress_download"
            retries = 0
            #
            if os.path.isfile(output_file):
                print("  file exists")
            else:
                while retries < max_retries:
                    try:
                        # Make the request to download the GRIB2 file
                        print(f"Starting download ({retries + 1})", end="", flush=True)
                        response = requests.get(url, stream=True, timeout=timeout)
                        response.raise_for_status()  # Check for HTTP errors
                        
                        # Save the file locally
                        with open(temp_output_file, "wb") as file:
                            for chunk in response.iter_content(chunk_size=819200):
                                if chunk:
                                    print(".",end='', flush=True)
                                    file.write(chunk)
                        
                        print(f"complete")
                        os.rename(temp_output_file,output_file)
                        break
                    except (requests.exceptions.Timeout, requests.exceptions.RequestException) as e:
                        retries += 1
                        print(f"\nError during download: {e}. Retrying ({retries}/{max_retries})...")
                        time.sleep(10**retries)  # wait an increasing amount
                if retries == max_retries:
                    print("Max retries reached. Download failed.")
                    raise Exception("Failed to download file after multiple attempts.")
                            

