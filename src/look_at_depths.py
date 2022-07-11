import sdig.erddap.info as info
import pandas as pd
import math

url = 'https://dunkel.pmel.noaa.gov:8930/erddap/tabledap/keo_temp_on_pres.html'

info_url = info.get_info_url(url)
info_df = pd.read_csv(info_url)
dsg_type = info.get_dsg_type(info_df)
depth_name, dsg_id = info.get_dsg_info(dsg_type, info_df)
depths = info.get_depths(depth_name, url)
depths = [item for item in depths if not(math.isnan(item)) == True]
print(len(depths), ' unique depths were found.')
print('between ', depths[0], ' and ', depths[-1])

delta = (depths[-1] - depths[0])/10.0

a_depths = []
for i in range(0, 11):
    a_depths.append(math.floor(depths[0] + i*delta))

print(a_depths)
