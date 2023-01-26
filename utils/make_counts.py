import pandas as pd
import json
import dateutil.parser
import numpy as np
import os
import pprint

import sdig.erddap.info as info

pp = pprint.PrettyPrinter(indent=4)

with open('lts_sites.json') as platform_stream:
    platform_json = json.load(platform_stream)

datasets = platform_json['config']['datasets']
for dataset in datasets:
    if 'locations' in dataset and 'url' in dataset:
        locations_url = dataset['locations']
        url = dataset['url']
        print('loading ' + url)
        dataset_info_url = info.get_info_url(url)
        info_df = pd.read_csv(dataset_info_url)
        dataset['id'] = url[url.rindex('/') + 1:]

        # Add the info for each data set into the dictionary for use when the menu choice changes
        title = info.get_title(info_df)
        variables, long_names, units, standard_names = info.get_variables(info_df)
        dataset['title'] = info.get_title(info_df)
        if 'site_code' not in variables:
            variables.append('site_code')
        if 'HEIGHT' in variables:
            variables.remove('HEIGHT')
        if 'HEIGHTZS' in variables:
            variables.remove('HEIGHTZS')
        if 'wmo_platform_code' not in variables:
            variables.append('wmo_platform_code')
        # Treat separately below
        if 'time' in variables:
            variables.remove('time')
        if 'latitude' in variables:
            variables.remove('latitude')
        if 'longitude' in variables:
            variables.remove('longitude')
        dataset['variables'] = variables
        dataset['long_names'] = long_names
        dataset['units'] = units

        start_date, end_date, start_date_seconds, end_date_seconds = info.get_times(info_df)

        dataset['start_date'] = start_date
        dataset['end_date'] = end_date
        mdf = pd.read_csv(locations_url, skiprows=[1],
                          dtype={'site_code': str, 'wmo_platform_code': str, 'latitude': np.float64, 'longitude': np.float64})

        if mdf.shape[0] > 1 and mdf.wmo_platform_code.nunique() <= 1:
            adf = mdf.mean(axis=0, numeric_only=True)
            adf['wmo_platform_code'] = mdf['wmo_platform_code'].iloc[0]
            mdf = pd.DataFrame(columns=['latitude', 'longitude', 'wmo_platform_code', 'site_code'], index=[0], )
            mdf['latitude'] = adf.loc['latitude']
            mdf['longitude'] = adf.loc['longitude']
            mdf['wmo_platform_code'] = adf.loc['wmo_platform_code']
            mdf['site_code'] = adf.loc['site_code']
        dataset['platforms'] = mdf['site_code'].to_list()

    count = 0

    pp.pprint(platform_json)

for dataset in platform_json['config']['datasets']:
    durl = dataset['url']
    did = durl[durl.rindex('/')+1:]
    print('Requesting ' + did)
    # start_at = datetime.datetime.strptime(dataset['start_date'], "%Y-%m-%d")
    # start_on = start_at.replace(day=1)
    # end_at = datetime.datetime.strptime(dataset['end_date'], "%Y-%m-%d")
    # end_on = end_at.replace(day=1)
    # # months = pd.date_range(start_on.isoformat(), end_on.isoformat(), freq="MS").to_list()
    # months = pd.date_range(start_on.isoformat(), '2005-01-01', freq="MS").to_list()
    # for platform in dataset['platforms']:
    df = None
    # for itx, month in enumerate(months):
    #     next_month = month.replace(day=28) + datetime.timedelta(days=4)
    #     last_day = next_month - datetime.timedelta(days=next_month.day)
    #     last_day = last_day.replace(hour=23, minute=59, second=59)
    all_count_url = durl + '.csv?' + ','.join(dataset['variables'])+',time' + '&orderByCount(\"wmo_platform_code,site_code,time/1month\")'
    if 'WHOI' in all_count_url:
        all_count_url = all_count_url + '&Deployment=1'
    print('with url:')
    print(all_count_url)
    try:
        df = pd.read_csv(all_count_url, skiprows=[1])
        pdir = 'counts/'+did
        isExist = os.path.exists(pdir)
        if not isExist:
            os.makedirs(pdir)
        print('Writing file for ' + dataset['title'])
        df = df.set_index('time')
        df.to_csv(pdir + '/counts.csv')
        print('For data set ' + did)
        print('There are '+str(len(dataset['platforms'])) + ' platforms.')
        print(' and ' + str(df.shape[0]) + ' months.')
        counts = df.apply(pd.value_counts).groupby('site_code')
        print('There are: ')
        icount = 0
        for key, item in counts:
            icount = icount + counts.get_group(key).shape[0]
        print(icount, "\n\n")
        print('months with no data.')
        # array = df.to_xarray()
        # array.to_netcdf(pdir+'/'+platform+'.nc')
    except Exception as e:
        print('Failed on counts for ' + did + ' with:')
        print(e)

