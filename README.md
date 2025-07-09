#### OceanSITES Long term Timeseries Dashboard 
This is the code for the 
[OceanSITES long term timeseries data dashboard](https://data.pmel.noaa.gov/oceansites/lts/). This is a Dash application
which uses the [Dash Bootstrap Components](https://dash-bootstrap-components.opensource.faculty.ai/) for widgets and 
layout.

Currently, the dashboard has temperature and salinity observations from:
 - [KEO (both)](https://data.pmel.noaa.gov/generic/erddap/tabledap/keo_hourly.html)
 - [PAPA TEMP](https://data.pmel.noaa.gov/generic/erddap/tabledap/papa_hourly_temp.html)
 - [PAPA PSAL](https://data.pmel.noaa.gov/generic/erddap/tabledap/papa_hourly_psal.html)
 - [RAMA TEMP](https://data.pmel.noaa.gov/generic/erddap/tabledap/rama_hourly_temp.html)
 - [RAMA PSAL](https://data.pmel.noaa.gov/generic/erddap/tabledap/rama_hourly_psal.html)  
 - [PIRATA TEMP](https://data.pmel.noaa.gov/generic/erddap/tabledap/pirata_hourly_temp.html)
 - [PIRATA PSAL](https://data.pmel.noaa.gov/generic/erddap/tabledap/pirata_hourly_psal.html)
 - [NTAS TEMP](https://data.pmel.noaa.gov/pmel/erddap/tabledap/NTAS_met.html)
 - [NTAS PSAL](https://data.pmel.noaa.gov/pmel/erddap/tabledap/NTAS_met.html)
 - [Status TEMP](https://data.pmel.noaa.gov/pmel/erddap/tabledap/Stratus_met.html)
 - [Stratus PSAL](https://data.pmel.noaa.gov/pmel/erddap/tabledap/Status_met.html)
 - [WHOTS TEMP](https://data.pmel.noaa.gov/pmel/erddap/tabledap/WHOTS_met.html)
 - [WHOTS PSAL](https://data.pmel.noaa.gov/pmel/erddap/tabledap/WHOTS_met.html)


But, you should really use the dashboard link above which lets you find the data of interest, see plots of 
it and then download that data quickly and easily. :wink:


#### For our folks who are running this the site, here are the steps to add a new data set to the dashboard.

Currently the site uses only temperature and salinity data from the included ERDDAP data sets. If you have an ERDDAP site
which includes TEMP and/or PSAL to be included in the long time-series site, follow the instructions below to add it.

1. Add the TEMP ERDDAP URL to the datasets.json file in the "temperature" section and the PSAL ERDDAP URL to the "salinity" section. You must enter a URL for each variable even if the data are included in the same ERDDAP data set.
2. run the config.ipynb notebook. This will read the datasets.json file and build the sites.json file.
1. Create the "counts" database and save it to Postgress by running the make_nobs_db.ipynb
1. Add and commit the new datasets.json, sites.json and README.md files.
1. Deploy the new site to all the places (plotly for local testing and "prod" for public release after testings is complete)
3. Add the URLs to the list above.

#### Legal Disclaimer
*This repository is a software product and is not official communication
of the National Oceanic and Atmospheric Administration (NOAA), or the
United States Department of Commerce (DOC).  All NOAA GitHub project
code is provided on an 'as is' basis and the user assumes responsibility
for its use.  Any claims against the DOC or DOC bureaus stemming from
the use of this GitHub project will be governed by all applicable Federal
law.  Any reference to specific commercial products, processes, or services
by service mark, trademark, manufacturer, or otherwise, does not constitute
or imply their endorsement, recommendation, or favoring by the DOC.
The DOC seal and logo, or the seal and logo of a DOC bureau, shall not
be used in any manner to imply endorsement of any commercial product
or activity by the DOC or the United States Government.*