#!/usr/bin/env python3
import requests
import os.path


year=2024
days=range(1,15)
hours=[0,6,12,18]

#url = "https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.20240701/00/atmos/gfs.t00z.pgrb2.0p25.f000"



for day in days:
    for hour in hours:
        for fchr in range(0,6):
            url_base = "https://noaa-gfs-bdp-pds.s3.amazonaws.com/"
            url_path = f"gfs.{year}07{day:02}/{hour:02}/atmos/gfs.t{hour:02}z.pgrb2.0p25.f{fchr:03}"
            url = url_base + url_path
            #
            output_file = f"{year}/{year}07{day:02}-{hour:02}-gfs.t{hour:02}z.pgrb2.0p25.f{fchr:03}"
            #
            print(f"{url} -> {output_file}")
            #
            if os.path.isfile(output_file):
                print("  file exists")
            else:
                try:
                    temp_output_file="in_progress_download"
                    # Make the request to download the GRIB2 file
                    print(f"Starting download", end="", flush=True)
                    response = requests.get(url, stream=True)
                    response.raise_for_status()  # Check for HTTP errors
                    
                    # Save the file locally
                    with open(temp_output_file, "wb") as file:
                        for chunk in response.iter_content(chunk_size=819200):
                            print(".",end='', flush=True)
                            file.write(chunk)
                    
                    print(f"complete")
                    os.rename(temp_output_file,output_file)
                except requests.exceptions.RequestException as e:
                    print(f"Error downloading GRIB2 file: {e}")
                    raise e
                

