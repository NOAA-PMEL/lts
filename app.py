# Dash
import dash
from dash import Dash, callback, html, dcc, dash_table, Input, Output, State, MATCH, ALL, CeleryManager, DiskcacheManager
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import dash_design_kit as ddk
import colorcet as cc


# pytyony stuff
import os
import sys

# Standard tools and utilities
import pandas as pd
import json
import pprint
import numpy as np
import datetime
import flask
import urllib

# My stuff
from sdig.erddap.info import Info

if os.environ.get("DASH_ENTERPRISE_ENV") == "WORKSPACE":
    # For testing...
    import diskcache
    cache = diskcache.Cache("./cache")
    background_callback_manager = DiskcacheManager(cache)
else:
    # For production...
    from celery import Celery
    celery_app = Celery(__name__, broker=os.environ['REDIS_URL'], backend=os.environ['REDIS_URL'])
    background_callback_manager = CeleryManager(celery_app)

version = 'v1.5.1'  # Set range on time axis of profile. Set title.
empty_color = '#999999'
has_data_color = 'black'

seconds_in_day = 24 * 60 * 60
month_step = 60 * 60 * 24 * 30.25
d_format = "%Y-%m-%d"

max_time_series_points = 88000
max_profile_points = 60000  # At most plot max_profile_points point in a profile plot

height_of_row = 450
height_of_profile_row = 500
profile_legend_gap = height_of_profile_row * .88
legend_gap = height_of_row * .88
line_rgb = 'rgba(.04,.04,.04,.2)'
plot_bg = 'rgba(1.0, 1.0, 1.0 ,1.0)'

discover_error = '''
You must configure a DISCOVERY_JSON env variable pointing to the JSON file that defines the which collections
of variables are to be in the discovery radio button list.
'''

graph_config = {'displaylogo': False, 'modeBarButtonsToRemove': ['select2d', 'lasso2d'],
                'doubleClick': 'reset+autosize',
                'toImageButtonOptions': {'height': None, 'width': None, },
                }

# platform_file = os.getenv('PLATFORM_JSON')
platform_file = 'lts_sites.json'
if platform_file is None:
    platform_file = os.getenv('PLATFORMS_JSON')

platform_json = {}
if platform_file is not None:
    with open(platform_file) as platform_stream:
        platform_json = json.load(platform_stream)

variables_by_did = {}
locations_by_did = {}
units_by_did = {}

all_start = None
all_end = None
all_start_seconds = 999999999999999
all_end_seconds = -999999999999999

for dataset in platform_json['config']['datasets']:
    url = dataset['url']
    locations_url = dataset['locations']
    did = url[url.rindex('/') + 1:]
    dataset['id'] = did
    info = Info(url)
    start_date, end_date, start_date_seconds, end_date_seconds = info.get_times()
    dsg_type = info.get_dsg_type()
    if start_date_seconds < all_start_seconds:
        all_start_seconds = start_date_seconds
        all_start = start_date
    if end_date_seconds > all_end_seconds:
        all_end_seconds = end_date_seconds
        all_end = end_date
    title = info.get_title()
    dataset['title'] = title
    variables_list, long_names, units, standard_names, d_types = info.get_variables()
    units_by_did[did] = units
    variables_by_did[did] = variables_list
    mdf = pd.read_csv(locations_url, skiprows=[1],
                      dtype={'wmo_platform_code': str, 'site_code': str, 'latitude': np.float64, 'longitude': np.float64})
    
    if mdf.shape[0] > 1 and mdf.site_code.nunique() <= 1:
        platform = mdf['wmo_platform_code'].unique()
        site = mdf['site_code'].unique()
        adf = mdf.mean(axis=0, numeric_only=True)
        mdf = pd.DataFrame(columns=['latitude', 'longitude', 'site_code', 'wmo_platform_code'], index=[0], )
        mdf['latitude'] = adf.loc['latitude']
        mdf['longitude'] = adf.loc['longitude']
        mdf['site_code'] = site
        mdf['wmo_platform_code'] = platform
    mdf['did'] = did
    locations_by_did[did] = json.dumps(mdf.to_json())

ESRI_API_KEY = os.environ.get('ESRI_API_KEY')

discovery_file = 'lts_discovery.json'
if discovery_file is None:
    discovery_file = os.getenv('DISCOVERY_FILE')

if discovery_file is not None:
    with open(discovery_file) as discovery_stream:
        discover_json = json.load(discovery_stream)
else:
    print('No config information found')
    sys.exit(-1)

radio_options = []
for key in discover_json['discovery']:
    q = discover_json['discovery'][key]
    radio_options.append({'label': q['question'], 'value': key})

radio_value = None
if len(radio_options) >= 1:
    radio_value = radio_options[0]['value']

time_marks = Info.get_time_marks(all_start_seconds, all_end_seconds)

app = dash.Dash(__name__,
                external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP],
                background_callback_manager=background_callback_manager
                )

app._favicon = 'favicon.ico'
app.title = 'LTS'
server = app.server

app.layout = \
    html.Div(
        style={'padding-left': '15px', 'padding-right': '25px'},
        children=[
            dcc.Location(id='location', refresh=False),
            dcc.Store(id='active-platforms'),
            dcc.Store(id='inactive-platforms'),
            dcc.Store(id='selected-platform'),
            dcc.Store(id='map-info'),
            dcc.Store(id='initial-time-start'),  # time from initial load query string
            dcc.Store(id='initial-time-end'),  # time from initial load query string
            dcc.Store(id='initial-site'),  # A site coming in on the query string
            html.Div(id='data-div', style={'display': 'none'}),
            dbc.Navbar(
                [
                    # Use row and col to control vertical alignment of logo / brand
                    dbc.Row(
                        style={'width': '100%'},
                        align="center",
                        children=[
                            dbc.Col(width=2, children=[
                                html.Img(src='assets/os_logo.gif',
                                         style={'height': '97px', 'width': '150px'})
                            ]),
                            dbc.Col(width=3, style={'display': 'flex', 'align-items': 'left'}, children=[
                                html.A(
                                    dbc.NavbarBrand(
                                        'Long time series ', className="ml-2",
                                        style={
                                            'padding-top': '160px',
                                            'font-size': '2.5em',
                                            'font-weight': 'bold'
                                        }
                                    ),
                                    href='https://www.pmel.noaa.gov/gtmba/oceansites',
                                    style={'text-decoration': 'none'}
                                )]
                                    ),
                              dbc.Col(width=4), # empty space, replace with message if needed
                            # dbc.Col(width=4, children=[
                            #     html.Div(children=[
                            #     html.Div('Parts of the US government are closed. This site will not be updated; however, NOAA websites and social media channels necessary to protect lives and property will be maintained. See ', style={'display':'inline'}), 
                            #     html.A('www.weather.gov', href='https://www.weather.gov', style={'display':'inline'}), 
                            #     html.Div(' for critical weather information. To learn more, see ', style={'display': 'inline'}), 
                            #     html.A('www.commerce.gov', href='https://www.commerce.gov', style={'display':'inline'}), 
                            #     html.Div('.', style={'display':'inline'}),
                            #     ], style={'display':'inline'})
                            # ]),
                            dbc.Col(width=3, children=[
                                dcc.Loading(id='nav-loader', children=[
                                    html.Div(id='loading-div'),
                                    html.Div(children=[
                                        dbc.Button("Download Data", id='download-button', className="me-1"),
                                        dbc.Modal(children=
                                        [
                                            dbc.ModalHeader(dbc.ModalTitle("Download Data")),
                                            dbc.ModalBody(id='download-body'),
                                            dbc.ModalFooter(
                                                dbc.Button(
                                                    "Close", id="close-download", className="ms-auto", n_clicks=0
                                                )
                                            ),
                                        ],
                                            id="download-dialog",
                                            is_open=False,
                                        )
                                    ]),
                                ])
                            ])
                        ]
                    )
                ]
            ),
            dbc.Row(children=[
                dbc.Col(width=3, children=[
                    dbc.Card(children=[
                        dbc.CardHeader(children=["Discover:"]),
                        dbc.CardBody(children=[
                            dbc.RadioItems(
                                options=radio_options,
                                value=radio_value,
                                id="radio-items",
                            ),
                        ])
                    ]),
                    dbc.Card(children=[
                        dbc.CardHeader(children=['In the selected time range:']),
                        dbc.Row(children=[
                            dbc.Col(width=6, children=[
                                dbc.Card(children=[
                                    dbc.CardHeader(children=['Start Date']),
                                ]),
                                dbc.Input(id='start-date', debounce=True, value=all_start)
                            ]),
                            dbc.Col(width=6, children=[
                                dbc.Card(children=[
                                    dbc.CardHeader(children=['End Date']),
                                ]),
                                dbc.Input(id='end-date', debounce=True, value=all_end)
                            ])
                        ]),
                        dbc.Row(children=[
                            dbc.Col(width=12, children=[
                                html.Div(style={'padding-right': '40px', 'padding-left': '40px',
                                                'padding-top': '20px', 'padding-bottom': '45px'}, children=[
                                    dcc.RangeSlider(id='time-range-slider',
                                                    value=[all_start_seconds, all_end_seconds],
                                                    min=all_start_seconds,
                                                    max=all_end_seconds,
                                                    step=month_step,
                                                    marks=time_marks,
                                                    updatemode='mouseup',
                                                    allowCross=False)
                                ])
                            ])
                        ]),
                    ]),
                ]),
                dbc.Col(width=9, children=[
                    dbc.Card(children=[
                        dbc.CardHeader([
                            'Select the type of data and date range. Black dots have data, gray dots do not.',
                            dcc.Loading(html.Div(id='map-loading'))
                        ]),
                        dbc.CardBody(
                            ddk.Graph(id='location-map', config=graph_config),
                        )
                    ])
                ])
            ]),
            dbc.Row(id='plot-row', style={'display': 'none'}, children=[
                dbc.Card(id='plot-card', children=[
                    dbc.CardHeader(id='plot-card-title'),
                    dbc.CardBody(id='plot-card-body', children=[
                        dcc.Loading(
                            ddk.Graph(id='plot-graph', config=graph_config)
                        )
                    ])
                ]),
                dbc.Card(id='profile-card', children=[
                    dbc.CardHeader(id='profile-card-title'),
                    dbc.CardBody(id='profile-card-body', children=[
                        dcc.Loading(
                            ddk.Graph(id='profile-graph', config=graph_config)
                        )
                    ])
                ])
            ]),
            dbc.Row(style={'margin-bottom': '10px'}, children=[
                dbc.Col(width=12, children=[
                    dbc.Card(children=[
                        dbc.Row(children=[
                            dbc.Col(width=1, children=[
                                html.Img(src='https://www.pmel.noaa.gov/sites/default/files/PMEL-meatball-logo-sm.png',
                                         height=100,
                                         width=100),
                            ]),
                            dbc.Col(width=10, children=[
                                html.Div(children=[
                                    dcc.Link('National Oceanic and Atmospheric Administration',
                                             href='https://www.noaa.gov/'),
                                ]),
                                html.Div(children=[
                                    dcc.Link('Pacific Marine Environmental Laboratory',
                                             href='https://www.pmel.noaa.gov/'),
                                ]),
                                html.Div(children=[
                                    dcc.Link('oar.pmel.webmaster@noaa.gov', href='mailto:oar.pmel.webmaster@noaa.gov')
                                ]),
                                html.Div(children=[
                                    dcc.Link('DOC |', href='https://www.commerce.gov/'),
                                    dcc.Link(' NOAA |', href='https://www.noaa.gov/'),
                                    dcc.Link(' OAR |', href='https://www.research.noaa.gov/'),
                                    dcc.Link(' PMEL |', href='https://www.pmel.noaa.gov/'),
                                    dcc.Link(' Privacy Policy |', href='https://www.noaa.gov/disclaimer'),
                                    dcc.Link(' Disclaimer |', href='https://www.noaa.gov/disclaimer'),
                                    dcc.Link(' Accessibility', href='https://www.pmel.noaa.gov/accessibility')
                                ])
                            ]),
                            dbc.Col(width=1, children=[
                                html.Div(style={'font-size': '1.0em', 'position': 'absolute', 'bottom': '0'},
                                         children=[version])
                            ])
                        ])
                    ])
                ])
            ])
        ]
    )


def get_blank(platform, b_start_date, b_end_date):
    message = 'No data available at ' + platform + ' for ' + b_start_date + ' to ' + b_end_date
    blank_graph = go.Figure(go.Scatter(x=[0, 1], y=[0, 1], showlegend=False))
    blank_graph.add_trace(go.Scatter(x=[0, 1], y=[0, 1], showlegend=False))
    blank_graph.update_traces(visible=False)
    blank_graph.update_layout(
        xaxis={"visible": False},
        yaxis={"visible": False},
        title=message,
        plot_bgcolor=plot_bg,
        annotations=[
            {
                "text": message,
                "xref": "paper",
                "yref": "paper",
                "showarrow": False,
                "font": {
                    "size": 14
                }
            },
        ]
    )
    return blank_graph


def make_gaps(pdf, fre):
    if pdf.shape[0] > 3:
        # This magic inserts missing values between rows that are more than two deltas apart.
        # Make time the index to the data
        pdf2 = pdf.set_index('time')
        pdf2 = pdf2[~pdf2.index.duplicated()]
        # make a index at the expected delta
        fill_dates = pd.date_range(pdf['time'].iloc[0], pdf['time'].iloc[-1], freq=fre)
        # sprinkle the actual values out along the new time axis, by combining the regular
        # intervals index and the data index
        all_dates = fill_dates.append(pdf2.index)
        all_dates = all_dates[~all_dates.duplicated()]
        fill_sort = sorted(all_dates)
        # reindex the data which causes NaNs everywhere in the regular index that don't
        # exactly match the data, with the data in between the NaNs
        pdf3 = pdf2.reindex(fill_sort)
        # remove the NaN rows that are by themselves because there is data near enough
        mask1 = ~pdf3['site_code'].notna() & ~pdf3['site_code'].shift().notna()
        mask2 = pdf3['site_code'].notna()
        pdf4 = pdf3[mask1 | mask2]
        # Reindex to 0 ... N
        pdf = pdf4.reset_index()
    return pdf


@app.callback(
    [
        Output('initial-time-start', 'data'),
        Output('initial-time-end', 'data'),
        Output('radio-items', 'value'),
        Output('initial-site', 'data')
    ],
    [
        Input('data-div', 'n_clicks')
    ],
    [
        State('location', 'search')
    ]
)
def process_query(aclick, qstring):
    qurl = flask.request.referrer
    parts = urllib.parse.urlparse(qurl)
    params = urllib.parse.parse_qs(parts.query)
    # get defaults from initial load
    initial_start_time = all_start
    initial_end_time = all_end
    dq = ''
    if 'start_date' in params:
        initial_start_time = params['start_date'][0]
    if 'end_date' in params:
        initial_end_time = params['end_date'][0]
    if 'q' in params:
        dq = params['q'][0]
    else:
        dq = radio_value
    initial_site_json = {}
    if 'site_code' in params and 'lat' in params and 'lon' in params:
        initial_site_code = params['site_code'][0]
        initial_lat = params['lat'][0]
        initial_lon = params['lon'][0]
        initial_site_json = {'site_code': initial_site_code, 'lat': initial_lat, 'lon': initial_lon}
    return [initial_start_time, initial_end_time, dq, json.dumps(initial_site_json)]


@app.callback(
    Output("download-dialog", "is_open"),
    [Input("download-button", "n_clicks"), Input("close-download", "n_clicks")],
    [State("download-dialog", "is_open")],
)
def toggle_modal(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open


@app.callback([
    Output('map-info', 'data')
], [
    Input('location-map', 'relayoutData')
]
)
def record_map_change(relay_data):
    center = {'lon': 0.0, 'lat': 0.0}
    zoom = 1.4
    if relay_data is not None:
        if 'mapbox.center' in relay_data:
            center = relay_data['mapbox.center']
        if 'mapbox.zoom' in relay_data:
            zoom = relay_data['mapbox.zoom']
    map_info = {'center': center, 'zoom': zoom}
    return [json.dumps(map_info)]


@app.callback(
    [
        Output('active-platforms', 'data'),
        Output('inactive-platforms', 'data'),
        Output('map-loading', 'children')
    ],
    [
        Input('start-date', 'value'),
        Input('end-date', 'value'),
        Input('radio-items', 'value'),
    ], prevent_initial_call=True
)
def update_platform_state(in_start_date, in_end_date, in_data_question):
    print('update platform state')
    time_constraint = ''
    all_with_data = None
    all_without_data = None
    vars_to_get = []
    # check to see which platforms have data for the current variables
    if in_start_date is not None and in_end_date is not None:
        n_start_obj = datetime.datetime.strptime(in_start_date, d_format)
        n_start_obj.replace(day=1, hour=0)
        time_constraint = time_constraint + '&time>=' + n_start_obj.isoformat()

        n_end_obj = datetime.datetime.strptime(in_end_date, d_format)
        n_end_obj.replace(day=1, hour=0)
        time_constraint = time_constraint + '&time<=' + n_end_obj.isoformat()
        if n_start_obj.year != n_end_obj.year:
            count_by = '1year'
        elif n_start_obj.year == n_end_obj.year and n_start_obj.month != n_end_obj.month:
            count_by = '1month'
        else:
            count_by = '1day'
    if in_data_question is not None and len(in_data_question) > 0:
        for qin in discover_json['discovery']:
            if qin == in_data_question:
                search_params = discover_json['discovery'][qin]['search']
                for search in search_params:
                    vars_to_get = search['short_names'].copy()
                    vars_to_get.append('time')
                    vars_to_get.append('site_code')
                    short_names = ','.join(vars_to_get)
                    # join_type == "or" then sum of short name columns > 0.
                    # join_type == "and" then s1 > 0 && s2 > 0 ...
                    join_type = search['join']
                    for dataset_to_check in search['datasets']:
                        cur_did = dataset_to_check[dataset_to_check.rindex('/') + 1:]
                        locations_to_map = pd.read_json(json.loads(locations_by_did[cur_did]),
                                                        dtype={'site_code': str,
                                                               'latitude': np.float64,
                                                               'longitude': np.float64})
                        have_url = dataset_to_check + '.csv?' + short_names + urllib.parse.quote(time_constraint, safe='&()=:/')
                        have = None
                        try:
                            print(have_url)
                            have = pd.read_csv(have_url, skiprows=[1])
                        except Exception as he:
                            print(he)
                            if 'httpError' in type(he).__class__.__name__:
                                html_response = he.read()
                                encoding = he.headers.get_content_charset('utf-8')
                                decoded_html = html_response.decode(encoding)
                                print(decoded_html)
                                print('exception getting counts on ' + have_url)
                                pass
                        if have is not None:
                            csum = have.groupby(['site_code']).sum().reset_index()
                            csum['site_code'] = csum['site_code'].astype(str)
                            sum_n = None
                            if join_type == 'or':
                                csum['has_data'] = csum[search['short_names']].sum(axis=1)
                                csum = csum.sort_values('site_code')
                                locations_to_map = locations_to_map.sort_values('site_code')
                                sum_n = csum.loc[csum['has_data'] > 0]
                            if join_type == 'and':
                                chk_vars = search['short_names']
                                criteria = ''
                                for vix, v in enumerate(chk_vars):
                                    if vix > 0:
                                        criteria = criteria + ' & '
                                    criteria = criteria + '(csum[\'' + v + '\']' + ' > 0)'
                                criteria = 'csum[(' + criteria + ')]'
                                # eval dereferences all the stuff in the string and runs it
                                sum_n = pd.eval(criteria)
                            if sum_n is not None and sum_n.shape[0] > 0:
                                # sum_n is the platforms that have data.
                                # This merge operation (as explained here:
                                # https://stackoverflow.com/questions/53645882/pandas-merging-101/53645883#53645883)
                                # combines the locations data frame with
                                # the information about which sites have observations to make something
                                # that can be plotted.
                                some_data = locations_to_map.merge(sum_n, on='site_code', how='inner')
                                some_data['platform_color'] = has_data_color
                                if all_with_data is None:
                                    all_with_data = some_data
                                else:
                                    all_with_data = pd.concat([all_with_data, some_data])
                                criteria = locations_to_map.site_code.isin(some_data.site_code) == False
                                no_data = locations_to_map.loc[criteria].reset_index()
                                no_data['platform_color'] = empty_color
                                if all_without_data is None:
                                    all_without_data = no_data
                                else:
                                    all_without_data = pd.concat([all_without_data, no_data])
                        else:
                            locations_to_map['platform_color'] = empty_color
                            if all_without_data is None:
                                all_without_data = locations_to_map
                            else:
                                all_without_data = pd.concat([all_without_data, locations_to_map])
    else:
        for map_did in locations_by_did:
            locations_to_map = pd.read_json(json.loads(locations_by_did[map_did]),
                                            dtype={'wmo_platform_code': str, 'site_code': str, 'latitude': np.float64,
                                                   'longitude': np.float64})

            locations_to_map['platform_color'] = empty_color
            if all_without_data is None:
                all_without_data = locations_to_map
            else:
                all_without_data = pd.concat([all_without_data, locations_to_map])
    locations_with_data = json.dumps(
        pd.DataFrame(columns=['latitude', 'longitude', 'site_code', 'platform_color'], index=[0], ).to_json())
    locations_without_data = json.dumps(
        pd.DataFrame(columns=['latitude', 'longitude', 'site_code', 'platform_color'], index=[0], ).to_json())
    if all_with_data is not None:
        all_with_data.reset_index(inplace=True, drop=True)
        locations_with_data = json.dumps(all_with_data.to_json())
    if all_without_data is not None:
        all_without_data.reset_index(inplace=True, drop=True)
        locations_without_data = json.dumps(all_without_data.to_json())
    return [locations_with_data, locations_without_data, '']


@app.callback(
    [
        Output('location-map', 'figure'),
    ],
    [
        Input('active-platforms', 'data'),
        Input('inactive-platforms', 'data'),
        Input('selected-platform', 'data'),
    ],
    [
        State('map-info', 'data')
    ], prevent_initial_call=True)
def make_location_map(in_active_platforms, in_inactive_platforms, in_selected_platform, in_map):
    center = {'lon': 0.0, 'lat': 0.0}
    zoom = 1.4
    if in_map is not None:
        map_inf = json.loads(in_map)
        center = map_inf['center']
        zoom = map_inf['zoom']
    location_map = go.Figure()
    selected_plat = None
    if in_selected_platform is not None:
        selected_plat = json.loads(in_selected_platform)
    if in_active_platforms is not None and in_inactive_platforms is not None:
        data_for_yes = pd.read_json(json.loads(in_active_platforms))
        data_for_no = pd.read_json(json.loads(in_inactive_platforms))
        no_trace = None
        if data_for_no.shape[0] > 0:
            no_trace = go.Scattermapbox(lat=data_for_no['latitude'],
                                        lon=data_for_no['longitude'],
                                        hovertext=data_for_no['site_code'],
                                        hoverinfo='lat+lon+text',
                                        customdata=data_for_no['site_code'],
                                        marker={'color': data_for_no['platform_color'], 'size': 10},
                                        mode='markers')
        yes_trace = None
        if data_for_yes.shape[0] > 0:
            yes_trace = go.Scattermapbox(lat=data_for_yes['latitude'],
                                         lon=data_for_yes['longitude'],
                                         hovertext=data_for_yes['site_code'],
                                         hoverinfo='lat+lon+text',
                                         customdata=data_for_yes['site_code'],
                                         marker={'color': data_for_yes['platform_color'], 'size': 10},
                                         mode='markers')
        if no_trace is not None:
            location_map.add_trace(no_trace)
        if yes_trace is not None:
            location_map.add_trace(yes_trace)

    if selected_plat is not None and 'lat' in selected_plat and 'lon' in selected_plat and 'site_code' in selected_plat:
        yellow_trace = go.Scattermapbox(lat=[selected_plat['lat']],
                                        lon=[selected_plat['lon']],
                                        hovertext=[selected_plat['site_code']],
                                        hoverinfo='lat+lon+text',
                                        customdata=[selected_plat['site_code']],
                                        marker={'color': 'yellow', 'size': 15},
                                        mode='markers')
        location_map.add_trace(yellow_trace)
    location_map.update_layout(
        showlegend=False,
        mapbox_style="white-bg",
        mapbox_layers=[
            {
                "below": 'traces',
                "sourcetype": "raster",
                "sourceattribution": "Powered by Esri",
                "source": [
                    "https://ibasemaps-api.arcgis.com/arcgis/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}?token=" + ESRI_API_KEY
                ]
            }
        ],
        mapbox_zoom=zoom,
        mapbox_center=center,
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        legend=dict(
            orientation="v",
            x=-.01,
        ),
        modebar_orientation='v',
    )

    return [location_map]


@app.callback(
    [
        Output('selected-platform', 'data'),
    ],
    [
        Input('location-map', 'clickData'),
        Input('initial-site', 'data')
    ], prevent_initial_call=True
)
def update_selected_platform(click, initial_site):
    selection = None
    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if trigger_id == 'initial-site':
        selection = initial_site
    else:
        if click is not None:
            if 'points' in click:
                point_dict = click['points'][0]
                selected_platform = point_dict['customdata']
                selected_lat = point_dict['lat']
                selected_lon = point_dict['lon']
                selection = json.dumps({'site_code': selected_platform, 'lat': selected_lat, 'lon': selected_lon})
    return [selection]


@app.callback(
    [
        Output('plot-row', 'style'),
        Output('plot-card-title', 'children'),
        Output('plot-graph', 'figure'),
        Output('location', 'search'),
    ],
    [
        Input('selected-platform', 'data'),
        Input('start-date', 'value'),
        Input('end-date', 'value'),
        Input('active-platforms', 'data'),
    ],
    [
        State('radio-items', 'value'),
        State('time-range-slider', 'value')
    ], prevent_initial_call=True, background=True
)
def plot_timeseries_for_platform(selection_data, plot_start_date, plot_end_date, active_platforms, question_choice,
                                 slider_values):
    figure = {}
    query = ''
    row_style = {'display': 'block'}
    plot_title = 'No data found.'
    active = None
    selected_platform = None
    if selection_data is not None:
        selected_json = json.loads(selection_data)
        if 'site_code' in selected_json:
            selected_platform = selected_json['site_code']
        else:
            raise dash.exceptions.PreventUpdate
    else:
        raise dash.exceptions.PreventUpdate
    if active_platforms is not None:
        active = pd.read_json(json.loads(active_platforms))
    if active is not None and selected_platform is not None:
        plot_time = '&time>=' + plot_start_date + '&time<=' + plot_end_date
        to_plot = active.loc[active['site_code'] == selected_platform]
        if to_plot.empty:
            return [row_style, plot_title, get_blank(selected_platform, plot_start_date, plot_end_date), '']
        dids = to_plot['did'].to_list()
        current_search = None
        for a_search in discover_json['discovery']:
            if a_search == question_choice:
                current_search = discover_json['discovery'][a_search]
        col = dbc.Col(width=12)
        col.children = []
        p_did = dids[0]
        current_dataset = next(
            (item for item in platform_json['config']['datasets'] if item['id'] == p_did), None)
        p_url = current_dataset['url']
        row = dbc.Row()
        card = dbc.Card()
        card.children = [dbc.CardHeader(current_dataset['title'] + ' at ' + selected_platform)]
        row.children = [card]
        col.children.append(row)
        for search in current_search['search']:
            for pd_data_url in search['datasets']:
                if p_did in pd_data_url:
                    plot_title = 'Timeseries of ' + ','.join(search['short_names']) + ' at ' + selected_platform
                    vlist = search['short_names'].copy()
                    vlist.append('time')
                    vlist.append('site_code')
                    # TODO do we need to find the depth_name for every data set?
                    vlist.append('depth')
                    pvars = ','.join(vlist)
                    sub_title = selected_platform
                    bottom_title = current_dataset['title']
                    p_url = p_url + '.csv?' + pvars + urllib.parse.quote(plot_time, safe='&()=:/') + '&site_code=' + urllib.parse.quote('"' + selected_platform + '"', safe='&()=:/')
                    # p_url = p_url + '&depth<3.5'  # use only surface for time series
                    p_var = search['short_names'][0]
                    days_in_request = (slider_values[1] - slider_values[0]) / seconds_in_day
                    factor = int((days_in_request * 24) / max_time_series_points)
                    print('days=', days_in_request,'maxpoints=', max_time_series_points, 'factor=',factor)
                    if factor > 0:
                        sub_sample = '"depth,time/' +  str(factor) + 'day"' 
                        p_url = p_url + '&orderByClosest(' + urllib.parse.quote(sub_sample, safe='&()=:/') + ')'
                        fre = factor * 24
                        sfre = str(fre) + 'H'
                        if factor == 1:
                            end = ' per day)'
                        else:
                            end = ' every ' + str(factor) + ' days)'
                        sub_title = sub_title + ' (timeseries sub-sampled to one observation' + end
                    else:
                        sfre = '1H'
                    print('Making a timeseries plot of: ' + p_url)
                    read_data = pd.read_csv(p_url, skiprows=[1])
                    read_depths = read_data['depth'].unique()

                    read_data = read_data[read_data[p_var].notna()]
                    read_data = read_data[read_data['time'].notna()]
                    read_data['site_code'] = read_data['site_code'].astype(str)
                    read_data.loc[:, 'text_time'] = read_data['time'].astype(str)
                    read_data.loc[:, 'time'] = pd.to_datetime(read_data['time'])

                    figure = go.Figure()
                    plot_units = ''
                    if p_var in units_by_did[p_did]:
                        plot_units = '(' + units_by_did[p_did][p_var] + ')'
                    y_title = p_var + ' ' + plot_units
                    for idx, gap_depth in enumerate(sorted(read_depths)):
                        data_at_depth = read_data.loc[read_data['depth']==gap_depth]
                        data_at_depth = data_at_depth.sort_values('time')
                        data_nan_gaps = make_gaps(data_at_depth, sfre)
                        trace = px.line(data_nan_gaps, x='time', y=p_var, hover_data=['time', p_var, 'depth'])
                        trace.update_traces(showlegend=True, name=str(gap_depth),line=dict(color=cc.b_glasbey_bw_minc_20[idx]))
                        figure.add_trace(list(trace.select_traces())[0])

        figure.update_yaxes(title=y_title)
        figure.update_traces(showlegend=True, connectgaps=False)
        figure['layout'].update(height=height_of_row, margin=dict(l=80, r=80, b=80, t=80, ))
        figure.update_layout(plot_bgcolor=plot_bg, paper_bgcolor="white",
                             title = {'text': sub_title, 'x':.01, 'font_size': 22, 'xanchor': 'left', 'xref': 'paper'},
                             legend=dict(orientation="v", yanchor="top", y=1.01, xanchor="right", x=1.08, bgcolor='white', font_size=16))
        figure.update_annotations(x=.01, font_size=22, xanchor='left', xref='x domain')

        figure.add_annotation(
            xref='x domain',
            yref='y domain',
            xanchor='right',
            yanchor='bottom',
            x=1.0,
            y=-.20,
            font_size=22,
            text=bottom_title,
            showarrow=False,
            bgcolor='rgba(255,255,255,.85)',
        )

        figure.update_xaxes({
            'ticklabelmode': 'period',
            'showticklabels': True,
            'gridcolor': line_rgb,
            'zeroline': True,
            'zerolinecolor': line_rgb,
            'showline': True,
            'linewidth': 1,
            'linecolor': line_rgb,
            'mirror': True,
            'tickfont': {'size': 16},
            'tickformatstops' : [
                    dict(dtickrange=[1000, 60000], value="%H:%M:%S\n%d%b%Y"),
                    dict(dtickrange=[60000, 3600000], value="%H:%M\n%d%b%Y"),
                    dict(dtickrange=[3600000, 86400000], value="%H:%M\n%d%b%Y"),
                    dict(dtickrange=[86400000, 604800000], value="%e\n%b %Y"),
                    dict(dtickrange=[604800000, "M1"], value="%b\n%Y"),
                    dict(dtickrange=["M1", "M12"], value="%b\n%Y"),
                    dict(dtickrange=["M12", None], value="%Y")
                ]
            })
        figure.update_yaxes({'gridcolor': line_rgb,
                             'zeroline': True,
                             'zerolinecolor': line_rgb,
                             'showline': True,
                             'linewidth': 1,
                             'linecolor': line_rgb,
                             'mirror': True,
                             'tickfont': {'size': 16},
                             'titlefont': {'size': 16},
                             })

        query = '?start_date=' + plot_start_date + '&end_date=' + plot_end_date + '&q=' + question_choice
        query = query + '&site_code=' + selected_platform + '&lat=' + str(selected_json['lat'])
        query = query + '&lon=' + str(selected_json['lon'])
    return [row_style, plot_title, figure, query]


@app.callback(
    [
        Output('profile-card-title', 'children'),
        Output('profile-graph', 'figure'),
        Output('download-body', 'children'),
        Output('loading-div', 'children')
    ],
    [
        Input('selected-platform', 'data'),
        Input('start-date', 'value'),
        Input('end-date', 'value'),
        Input('active-platforms', 'data'),
    ],
    [
        State('radio-items', 'value'),
        State('time-range-slider', 'value'),
    ], prevent_initial_call=True, background=True
)
def plot_profile_for_platform(selection_data, plot_start_date, plot_end_date, active_platforms, question_choice,
                              slider_values,):
    figure = {}
    query = ''
    row_style = {'display': 'block'}
    plot_title = 'No data found.'
    active = None
    list_group = html.Div()
    list_group.children = []
    if selection_data is not None:
        selected_json = json.loads(selection_data)
        if 'site_code' in selected_json:
            selected_platform = selected_json['site_code']
        else:
            raise dash.exceptions.PreventUpdate
    else:
        raise dash.exceptions.PreventUpdate
    if active_platforms is not None:
        active = pd.read_json(json.loads(active_platforms))
    if active is not None and selected_platform is not None:
        plot_time = '&time>=' + plot_start_date + '&time<=' + plot_end_date
        to_plot = active.loc[active['site_code'] == selected_platform]
        if to_plot.empty:
            return [plot_title, get_blank(selected_platform, plot_start_date, plot_end_date), list_group, '']
        dids = to_plot['did'].to_list()
        current_search = None
        for a_search in discover_json['discovery']:
            if a_search == question_choice:
                current_search = discover_json['discovery'][a_search]
        col = dbc.Col(width=12)
        col.children = []
        row_h = []

        for p_did in dids:
            current_dataset = next(
                (item for item in platform_json['config']['datasets'] if item['id'] == p_did), None)
            p_url = current_dataset['url']
            d_name = current_dataset['vertical_axis_name']
            row = dbc.Row()
            card = dbc.Card()
            card.children = [dbc.CardHeader(current_dataset['title'] + ' at ' + selected_platform)]
            row.children = [card]
            col.children.append(row)
            for search in current_search['search']:
                link_group = dbc.ListGroup(horizontal=True)
                link_group.children = []
                for pd_data_url in search['datasets']:
                    if p_did in pd_data_url:
                        list_group.children.append(link_group)
                        plot_title = 'Profile of ' + ','.join(search['short_names']) + ' at ' + selected_platform
                        row_h.append(1 / len(dids))
                        vlist = search['short_names'].copy()
                        vlist.append('time')
                        vlist.append('site_code')
                        # TODO do we need to find the depth_name for every data set?
                        vlist.append(d_name)
                        pvars = ','.join(vlist)
                        meta_item = dbc.ListGroupItem(current_dataset['title'] + ' at ' + selected_platform,
                                                      href=p_url, target='_blank')
                        link_group.children.append(meta_item)
                        sub_title = selected_platform
                        bottom_title = current_dataset['title']
                        p_url = p_url + '.csv?' + pvars + plot_time + '&site_code="' + selected_platform + '"'
                        # make the data URL's at the full resoltion without subsampling
                        item = dbc.ListGroupItem('.html', href=p_url.replace('.csv', '.htmlTable'), target='_blank')
                        link_group.children.append(item)
                        item = dbc.ListGroupItem('.csv', href=p_url.replace('.htmlTable', '.csv'), target='_blank')
                        link_group.children.append(item)
                        item = dbc.ListGroupItem('.nc', href=p_url.replace('.csv', '.ncCF'), target='_blank')
                        link_group.children.append(item)
                        days_in_request = (slider_values[1] - slider_values[0]) / seconds_in_day
                        has_data = active.loc[active['site_code'] == selected_platform]['has_data'].values[0]
                        factor = int(has_data/max_profile_points)
                        if factor > 1:
                            p_url = p_url + '&orderByClosest("' + d_name + ',time/' + str(factor) + 'hour")'
                            end = ' every ' + str(factor) + ' hours)'
                            sub_title = sub_title + ' (profile sub-sampled to one observation' + end

                        print('Making a profile plot of: ' + p_url)
                        read_data = pd.read_csv(p_url, skiprows=[1])
                        read_data = read_data.sort_values('time')
                        read_data['site_code'] = read_data['site_code'].astype(str)
                        read_data.loc[:, 'text_time'] = read_data['time'].astype(str)
                        read_data.loc[:, 'time'] = pd.to_datetime(read_data['time'])
                        plot_units = ''
                        for vidx, p_var in enumerate(search['short_names']):
                            read_data = read_data[read_data[p_var].notna()]
                            read_data = read_data[read_data['time'].notna()]
                            if d_name in units_by_did[p_did]:
                                plot_units = '(' + units_by_did[p_did][d_name] + ')'
                            read_data['text'] = p_var + '<br>' + read_data['text_time'] + '<br>' + \
                                                d_name + '=' + read_data[d_name].astype(str) + '<br>' + \
                                                p_var + '=' + read_data[p_var].apply(lambda x: '{0:.2f}'.format(x))
                            y_title = d_name + ' ' + plot_units
                            trace = go.Scattergl(x=read_data['time'], y=read_data[d_name],
                                                 connectgaps=False,
                                                 name=p_var,
                                                 mode='markers',
                                                 hovertext=read_data['text'],
                                                 marker=dict(
                                                     cmin=read_data[p_var].min(),
                                                     cmax=read_data[p_var].max(),
                                                     color=read_data[p_var],
                                                     colorscale='inferno',
                                                     colorbar=dict(
                                                        title_side='right',
                                                        title_font_size=16,
                                                        tickfont_size=16,
                                                        title_text=p_var + ' (' + units_by_did[p_did][p_var] + ')'
                                                     )
                                                 ),
                                                 hoverinfo="text",
                                                 hoverlabel=dict(namelength=-1),
                                                 )

                            
        figure = go.Figure()
        figure.add_trace(trace)
        graph_height = height_of_profile_row 
        figure.update_annotations(x=.01, font_size=22, xanchor='left', xref='x domain')
        figure.update_yaxes(title=y_title)
        figure.add_annotation(
            xref='x domain',
            yref='y domain',
            xanchor='right',
            yanchor='bottom',
            x=1.0,
            y=-.25,
            font_size=22,
            text=bottom_title,
            showarrow=False,
            bgcolor='rgba(255,255,255,.85)',
        )
        figure['layout'].update(height=graph_height, margin=dict(l=80, r=80, b=80, t=80, ), paper_bgcolor="white", plot_bgcolor='white')
        figure.update_layout(plot_bgcolor=plot_bg, legend_tracegroupgap=profile_legend_gap,  title = {'text': sub_title, 'x':.01, 'font_size': 22, 'xanchor': 'left', 'xref': 'paper'},)
        figure.update_xaxes({
            'range':[read_data['time'].min(), read_data['time'].max()],
            # 'autorange': True,
            'ticklabelmode': 'period',
            'showticklabels': True,
            'gridcolor': line_rgb,
            'zeroline': True,
            'zerolinecolor': line_rgb,
            'showline': True,
            'linewidth': 1,
            'linecolor': line_rgb,
            'mirror': True,
            'tickfont': {'size': 16},
            'tickformatstops' : [
                    dict(dtickrange=[1000, 60000], value="%H:%M:%S\n%d%b%Y"),
                    dict(dtickrange=[60000, 3600000], value="%H:%M\n%d%b%Y"),
                    dict(dtickrange=[3600000, 86400000], value="%H:%M\n%d%b%Y"),
                    dict(dtickrange=[86400000, 604800000], value="%e\n%b %Y"),
                    dict(dtickrange=[604800000, "M1"], value="%b\n%Y"),
                    dict(dtickrange=["M1", "M12"], value="%b\n%Y"),
                    dict(dtickrange=["M12", None], value="%Y")
                ]            
            }
            )
        figure.update_yaxes({
            'autorange': 'reversed',
            'gridcolor': line_rgb,
            'zeroline': True,
            'zerolinecolor': line_rgb,
            'showline': True,
            'linewidth': 1,
            'linecolor': line_rgb,
            'mirror': True,
            'tickfont': {'size': 16},
            'titlefont': {'size': 16},
            })

    return [plot_title, figure, list_group, '']


@app.callback(
    [
        Output('time-range-slider', 'value'),
        Output('start-date', 'value'),
        Output('end-date', 'value')
    ],
    [
        Input('time-range-slider', 'value'),
        Input('start-date', 'value'),
        Input('end-date', 'value'),
        Input('initial-time-start', 'data'),
        Input('initial-time-end', 'data')
    ], prevent_initial_call=True
)
def set_date_range_from_slider(slide_values, in_start_date, in_end_date, initial_start, initial_end):
    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if trigger_id == 'initial-time-start' or trigger_id == 'initial-time-end':
        start_output = initial_start
        end_output = initial_end
        try:
            in_start_date_obj = datetime.datetime.strptime(initial_start, d_format)
            start_seconds = in_start_date_obj.timestamp()
        except:
            start_seconds = all_start_seconds

        try:
            in_end_date_obj = datetime.datetime.strptime(initial_end, d_format)
            end_seconds = in_end_date_obj.timestamp()
        except:
            end_seconds = all_end_seconds

    else:
        if slide_values is None:
            raise dash.exceptions.PreventUpdate

        range_min = all_start_seconds
        range_max = all_end_seconds

        ctx = dash.callback_context
        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        start_seconds = slide_values[0]
        end_seconds = slide_values[1]

        start_output = in_start_date
        end_output = in_end_date

        if trigger_id == 'start-date':
            try:
                in_start_date_obj = datetime.datetime.strptime(in_start_date, d_format)
            except:
                in_start_date_obj = datetime.datetime.fromtimestamp(start_seconds)
            start_output = in_start_date_obj.date().strftime(d_format)
            start_seconds = in_start_date_obj.timestamp()
            if start_seconds < range_min:
                start_seconds = range_min
                in_start_date_obj = datetime.datetime.fromtimestamp(start_seconds)
                start_output = in_start_date_obj.date().strftime(d_format)
            elif start_seconds > range_max:
                start_seconds = range_max
                in_start_date_obj = datetime.datetime.fromtimestamp(start_seconds)
                start_output = in_start_date_obj.date().strftime(d_format)
            elif start_seconds > end_seconds:
                start_seconds = end_seconds
                in_start_date_obj = datetime.datetime.fromtimestamp(start_seconds)
                start_output = in_start_date_obj.date().strftime(d_format)
        elif trigger_id == 'end-date':
            try:
                in_end_date_obj = datetime.datetime.strptime(in_end_date, d_format)
            except:
                in_end_date_obj = datetime.datetime.fromtimestamp((end_seconds))
            end_output = in_end_date_obj.date().strftime(d_format)
            end_seconds = in_end_date_obj.timestamp()
            if end_seconds < range_min:
                end_seconds = range_min
                in_end_date_obj = datetime.datetime.fromtimestamp(end_seconds)
                end_output = in_end_date_obj.date().strftime(d_format)
            elif end_seconds > range_max:
                end_seconds = range_max
                in_end_date_obj = datetime.datetime.fromtimestamp(end_seconds)
                end_output = in_end_date_obj.date().strftime(d_format)
            elif end_seconds < start_seconds:
                end_seconds = start_seconds
                in_end_date_obj = datetime.datetime.fromtimestamp(end_seconds)
                end_output = in_end_date_obj.date().strftime(d_format)
        elif trigger_id == 'time-range-slider':
            in_start_date_obj = datetime.datetime.fromtimestamp(slide_values[0])
            start_output = in_start_date_obj.strftime(d_format)
            in_end_date_obj = datetime.datetime.fromtimestamp(slide_values[1])
            end_output = in_end_date_obj.strftime(d_format)

    return [[start_seconds, end_seconds],
            start_output,
            end_output
            ]


if __name__ == '__main__':
    app.run_server(debug=True)
