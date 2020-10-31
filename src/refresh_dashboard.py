from plotutils import plotts
from bokeh.io import save, output_file
from bokeh.layouts import Column, Row
from bokeh.models.widgets import DatePicker
from bokeh.models import HoverTool, CustomJS, Div, ColumnDataSource, DataRange1d, TapTool, Button, Band, Legend
from bokeh.plotting import figure
from bokeh.models.widgets import Panel, Tabs

import glob
import os
import time
from pathlib import Path
import pandas as pd
import numpy as np
import dask
import dask.dataframe as dd
from dask.diagnostics import ProgressBar
from datetime import datetime

from wodupcrawler import WodUp
import json


plot_window = pd.Timedelta('31 days')
datadir_hrsum = '/Users/hasannagib/Documents/s3stage/wahoo/heartrate_sumstat/'

df = dd.read_csv(Path(f'{datadir_hrsum}*.csv')).compute()
df = df.rename(columns={'Unnamed: 0': 'timestamp'})
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.set_index('timestamp')
df_bar = df.copy()
df_bar['L0'] = 22
df_bar['L1'] = 53
df_bar['L2'] = 59
df_bar['L3'] = 66

df_bar = df_bar.reset_index()
df_bar['timestamp'] = pd.to_datetime(df_bar['timestamp'].dt.strftime('%Y-%m-%d 07:00:00'))
df_bar = df_bar.set_index('timestamp')

ts_files = sorted(glob.glob('/Users/hasannagib/Documents/s3stage/wahoo/heartrate_ts/*.csv'))

@dask.delayed
def read_ts(file):
    df = pd.read_csv(file, parse_dates=['timestamp']
                     ).set_index('timestamp').sort_index().reset_index()[
        ['heart_rate']
    ].rename(columns={
        'heart_rate': pd.to_datetime(os.path.basename(file)[:-11]).strftime('%a %b %d %Y'),

    })
    return df


dfs = [read_ts(file) for file in ts_files]

with ProgressBar():
    dfs = dask.compute(dfs)[0]

df_ts = pd.concat(dfs, axis=1).reset_index().rename(columns={'index': 's'})
df_ts['Time'] = df_ts['s'].apply(lambda x: time.strftime('%H:%M:%S', time.gmtime(x)))

# Pick latest date for HR data
df_ts['BPM'] = df_ts.iloc[:, -2]


def plot_cal_ts(df_ts):
    p = figure(
        width=450,
        height=325,
        title='Heart Rate',
        x_axis_label='Time (seconds)',
        y_axis_label='BPM',
        toolbar_location="above",
        tooltips=[
            ('Time', '@Time'),
            ('BPM', '@BPM'),
        ]
    )

    cds = ColumnDataSource(df_ts)
    p.line('s', 'BPM', source=cds, color="black", alpha=0)

    band = Band(base='s', upper='BPM', source=cds, level='underlay',
                fill_alpha=0.95, fill_color='#ab383a')
    p.add_layout(band)
    return p, cds


with open('../data/session_urls.json') as json_file:
    urls = json.load(json_file)

with open('../data/session_wods.json') as json_file:
    wods = json.load(json_file)

# Get list of dates to look urls for
dts = []
for f in ts_files:
    dt = os.path.basename(f)[:10]
    if pd.to_datetime(dt) > pd.to_datetime('2020-09-01'):
        dts.append(dt)

if set(dts) - set(wods.keys()):
    wu = WodUp(
        email='hasan.nagib@gmail.com',
        password=os.environ['wodify_password'],
        username='hasannagib'
    )

    wu.session_urls = urls
    wu.session_wods = wods

    # Add missing urls
    urls = wu.get_session_urls(dts)
    wods = wu.get_session_wods()

    # Save json
    with open('../data/session_urls.json', 'w') as outfile:
        json.dump(urls, outfile)

    with open('../data/session_wods.json', 'w') as outfile:
        json.dump(wods, outfile)

    wu.browser.quit()

# Add rest day descriptions
for dt in pd.date_range('2020-09-01', datetime.today()):
    dt_str = dt.strftime('%Y-%m-%d')
    if dt_str not in wods.keys():
        wods[dt_str] = ['Rest day', '']


p1, p1_cds = plotts(
    df_bar[['L0', 'L1', 'L2', 'L3', '120_sec_rec']],
    units=['bpm'],
    x_range=DataRange1d(end=datetime.today()+pd.Timedelta('1 days'), follow='end', follow_interval=plot_window),
    styles=['--'] * 4 + 2 * ['|'],
    alpha=0.5,
    title='120 sec HR recovery trend',
    ylabel='Beats',
    plot_height=325,
    plot_width=450,
    show_plot=False
);

p2, p2_cds = plotts(
    (df.rolling(7).sum().dropna() / 60),
    ys=['174_', '152_173', '138_151'],
    styles=['o-'],
    units=['min'],
    title='Time spent in HR zones (7 day rolling sum)',
    x_range=p1.x_range,
    ylabel='Minutes',
    plot_height=325,
    plot_width=450,
    trace=True,
    show_plot=False
);

p3, p3_cds = plot_cal_ts(df_ts)

html ="""
<div style="width: 100%; overflow: hidden;">
     <div style="margin-left: 50px; width: 350px; float: left;"> {A} &nbsp; {B} </div>
</div>
"""

div = Div(text=html.format(A=wods[dts[-1]][0], B=wods[dts[-1]][1]))

dp_callback = CustomJS(
    args={
        'source': p3_cds,
        'div': div,
        'wods': wods,
        'html': html
    },

    code=
    """
    console.log('div: ', cb_obj.value)
    console.log('test: ', html.replace("{A}", wods[cb_obj.value][0]))

    div.text = html.replace("{A}", wods[cb_obj.value][0]).replace("{B}", wods[cb_obj.value][1])

    var yval = cb_obj.value;
    source.data['BPM'] = source.data[yval];
    source.change.emit()

    """
)

datePicker = DatePicker(width=100, value=df_ts.columns[-3])
datePicker.js_on_change('value', dp_callback)

tap_code = """
        console.log('DatePicker: ', dp.value)

        var dt_idx = p.selected.indices[0]
        var dt = p.data['ts_str'][dt_idx]

        console.log('Data selected: ', dt)
        dp.value = dt
        dp.change.emit()
        p.change.emit()
        r.change.emit()
        """

tap1_callback = CustomJS(args={'p': p1_cds, 'r': p2, 'dp': datePicker}, code=tap_code)
tap2_callback = CustomJS(args={'p': p2_cds, 'r': p1, 'dp': datePicker}, code=tap_code)

p1.add_tools(TapTool(callback=tap1_callback))
p2.add_tools(TapTool(callback=tap2_callback))

url = "https://www.wodup.com/timeline?date=@dt_str"

button = Button(width=100, label="WodUp", button_type="success")
button.js_on_click(CustomJS(
    args={
        'dp': datePicker,
        'urls': urls
    },
    code="""    
    var url = "https://www.wodup.com"

    function formatDate(date) {
    var d = new Date(date),
        month = '' + (d.getMonth() + 1),
        day = '' + d.getDate(),
        year = d.getFullYear();

    if (month.length < 2) 
        month = '0' + month;
    if (day.length < 2) 
        day = '0' + day;

    return [year, month, day].join('-');
    }

    var dt = dp.value
    console.log('Date:', formatDate(dt))

    if (typeof dt === 'string') {

      window.open(url.concat(urls[formatDate(Date.parse(dt))][0]))
    }
    else {
        var day = 60 * 60 * 24 * 1000;
        window.open(url.concat(urls[formatDate(dt+day)][0]))
    }
    """
)
)

df_sleep = pd.read_csv('../data/sleep.csv', parse_dates=['start', 'end', 'date'])
df_sleep['7.5hr'] = 450
df_sleep['time_asleep'] = df_sleep['deep'] + df_sleep['rem'] + df_sleep['light']
df_sleep['7day_avg'] = df_sleep.set_index('date')['time_asleep'].rolling('7d', closed='right').mean().reset_index()['time_asleep']
df_sleep['date_str'] = df_sleep['date'].dt.strftime('%a %b %d %Y')

stages = ["deep", "rem", "light", "awake"]
colors = ['#154ba6', '#3f8dff', '#7ec4ff', '#e73360']
data = ColumnDataSource(df_sleep)

p4 = figure(
    x_range=DataRange1d(end=datetime.today()+pd.Timedelta('1 days'), follow='end', follow_interval=plot_window),
    x_axis_type="datetime",
    plot_height=325,
    plot_width=450,
    title="Sleep stages",
)
p4.add_layout(Legend(), 'below')
p4.vbar_stack(stages, x='date', width=24*60*60*900, color=colors, source=data, legend_label=[s for s in stages])
p4.line(x='date', y='7.5hr', source=data, color='grey', line_width=2, line_dash="4 4")
p4.line(x='date', y='7day_avg', source=data, line_width=3, legend_label='7day_avg')
p4.y_range.start = 0
p4.x_range.range_padding = 0.1
p4.xgrid.grid_line_color = None
p4.axis.minor_tick_line_color = None
p4.add_tools(HoverTool(
        tooltips=[
            ("Awake", "@awake"),
            ("REM", "@rem"),
            ("Light", "@light"),
            ("Deep", "@deep"),
            ("7day avg", "@7day_avg"),
            ("Date", "@date_str")
        ]
    ))
p4.outline_line_color = None
p4.legend.click_policy = 'hide'
p4.legend.orientation = "horizontal"
p4.yaxis.axis_label = 'Minutes'

p5, p5_cds = plotts(
    df_sleep,
    plot_height=325,
    plot_width=450,
    alpha=0.5,
    xvar='date',
    ys=['end_hour', 'start_hour'],
    units=['hour'],
    x_range=p4.x_range,
    ymin=22,
    styles=['|'],
    ylabel='Hour',
    title='Sleep schedule',
    show_plot=False
);

df_pr = pd.read_csv('../../WodUp-Scraper/data/hasannagib-pr-table.csv').query('reps > 0')

p6, p6_cds = plotts(
    df_pr,
    ys=['front_squat', 'back_squat', 'deadlift', 'barbell_bench_press'],
    hover_vars=['date_front_squat', 'date_back_squat', 'date_deadlift', 'date_barbell_bench_press'],
    xvar='reps',
    styles=['-o'],
    x_axis_type='linear',
    ylabel='Weight (lbs)',
    xlabel='Reps',
    title='Rep PRs',
    plot_height=427,
    plot_width=450,
    show_plot=False,
    legend_location='below',
    legend_orientation='vertical',

);

p6_tabs = Tabs(tabs=[Panel(child=p6, title="n-Rep PR")])

tabs = []
for i in [1, 2, 3, 4, 5]:

    df_plot = []
    for movement in ['front-squat', 'back-squat', 'deadlift', 'barbell-bench-press']:
        df_hist = pd.read_csv(f'../../WodUp-Scraper/data/hasannagib-{movement}.csv', parse_dates=['date'])
        df = df_hist.query(f'(reps>={i})').sort_values('date')
        df_plot.append(np.maximum.accumulate(df).set_index('date')[['weights']].rename(
            columns={'weights': movement.replace('-', '_')}).sort_index()
                       )

    p, _ = plotts(
        pd.concat(df_plot),
        xvar='date',
        styles=['o-'],
        units=['lbs'],
        x_axis_type='datetime',
        title=f'{i} rep max PR over time ',
        xlabel='Date',
        ylabel='Weigt (lbs)',
        plot_height=400,
        plot_width=450,
        show_plot=False,
        legend_location='below',
        legend_orientation='vertical',
    );

    tabs.append(Panel(child=p, title=f"{i} RM"))

p7_tabs = Tabs(tabs=tabs, tabs_location='above', margin=(0,0,0,0))


header = """
<div style="style=font-family:courier; color:grey; margin-left: 40px; width: 400px; height: 260px; float: left;"> 
<h1>Health & Fitness Data Blog</h1>  
<p>This dashboard contains my personal health and fitness data. The data is sourced Fitbit, Polar HR10 and Wahoo
TickerX heart rate belt & WodUp.com and refreshed daily. For details check out my GitHub. 
</p>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css">
<a href="https://www.instagram.com/hnagib/" class="fa fa-instagram"></a>
<a href="https://www.facebook.com/bigannasah/" class="fa fa-facebook"></a>
<a href="https://www.linkedin.com/in/hnagib?_l=en_US" class="fa fa-linkedin"></a>
<a href="https://github.com/hnagib" class="fa fa-github"></a>

<p></p>
<h2>Sleep Logs</h2>
<p>Sleep data is sourced from Fitbit sleep logs. 
My goal is to average 7.5 hours of time asleep & 9 hours time in bed
</p>
</div>
"""
div_header = Div(text=header)


hr_rec = """
<div style="style=font-family:courier; color:grey; margin-left: 40px; width: 400px; float: left;"> 
<h2>Heart Rate & Workouts</h2>
<p>Fun fact: Heart rate recovery greater than 53 bpm in 2 minutes indicates that biological age 
is younger than calendar age. Greater recovery rate generally indicates better heart health.
The bar chart below shows my 2-minute recovery heart rate following a workout. 
Click on any bar to see corresponding workout and HR profile.
</p>
</div>
"""
hr_rec = Div(text=hr_rec)

hr_zones = """
<div style="style=font-family:courier; color:grey; margin-left: 40px; width: 400px; float: left;">   
<p>&nbsp;</p>
<p>It's useful to monitor time spend in HR zones to modify training program. 
I generally aim to keep 7 day cumulative peak HR zone around or under 30-45 minutes depending on the goal of
a given training cycle. 
</p>
</div>
"""
hr_zones = Div(text=hr_zones)


hr_desc = """
<div style="style=font-family:courier; color:grey; margin-left: 40px; width: 400px; float: left;">   
<p>
Heart rate data is sourced from Polar HR10 and Wahoo TickerX's .fit files. 
The .fit files are synced to Dropbox from the Wahoo iOS app and 
parsed using the <a href="https://pypi.org/project/fitparse/">fitparse</a> python library.
</p>
</div>
"""
hr_desc = Div(text=hr_desc)

wod_desc="""
<div style="style=font-family:courier; color:grey; margin-left: 40px; width: 400px; float: left;">   
<p>Workout data is sourced from my <a href="https://www.wodup.com">WodUp</a> account. The data is scraped using selenium. 
WodUp currently does not have an API. 
</p>
</div>
"""
wod_desc = Div(text=wod_desc)

rep_pr_desc = """
<div style="style=font-family:courier; color:grey; margin-left: 40px; width: 400px; float: left;"> 
<h2>Weight Lifting PRs</h2>
<p>The views below show lift PRs for different movements and reps. A PR over time view is also included to help
visualize training plateaus.
</p>
</div>
"""
rep_pr_desc = Div(text=rep_pr_desc)


div_space = Div(text='<div style="width: 30px; height: 10px;"></div>')

dash = Column(
    div_header,
    Row(p4, p5),
    Row(rep_pr_desc),
    Row(p6, p7_tabs),
    Row(hr_rec, hr_zones),
    Row(p1, p2),
    Row(hr_desc, Column(wod_desc, Row(div_space, datePicker))),
    Row(p3,div)
)
output_dir = '/Users/hasannagib/Documents/s3stage/dashboards/416-dash.html'


output_file(output_dir, title="Hasan's Data Blog")
save(dash)
