import requests
from string import Template
from datetime import datetime, date, timedelta, timezone, time
import time as _time
import csv
import os
import glob
import re
import pandas as pd
import numpy as np
import angles as a
import base64

def system():
  return os.environ['ENPHASE_SYSTEM_ID']

# v2
def version():
  return os.environ['ENPHASE_API_VERSION']

def userid():
  return os.environ['ENPHASE_APP_USER_ID']

def key():
  return os.environ['ENPHASE_APP_KEY']

def path():  
  return os.environ['ENPHASE_STATS_PATH']

def print_environ():
  print('ENPHASE_API_VERSION:', version())
  print('ENPHASE_SYSTEM_ID:', system())
  print('ENPHASE_APP_USER_ID:', userid())
  print('ENPHASE_APP_KEY:', key())
  print('ENPHASE_STATS_PATH:', path())

# v4
def v4_client_id():
  os.environ['ENPHASE_V4_CLIENT_ID']

def v4_client_secret():
  os.environ['ENPHASE_V4_CLIENT_SECRET']

def v4_version():
  return os.environ['ENPHASE_V4_API_VERSION']

def v4_api_key():
  return os.environ['ENPHASE_V4_API_KEY']

def v4_encoded_client_secret():
  id_secret = '{0}:{1}'.format(v4_client_id(),v4_client_secret())
  encoded_bytes = base64.b64encode(id_secret, "utf-8")
  return str(encoded_bytes, "utf-8")

def v4_stats_path():
  return os.environ['ENPHASE_V4_STATS_PATH']

# ========================================
# from enphase to files
#
# save_to_files
# ========================================

def compute_file_names():
  return sorted(glob.glob(path() + "stats_*.csv"))

def compute_next_date():
  file_names = compute_file_names()
  if not file_names:
    return date(2020,3,4)
  else:  
    d_re = re.compile('_(.*)\\.') # select characters between '_' and '.', as in stats_2020-10-14.csv
    date_strs = [d_re.findall(file_name)[0] for file_name in sorted(file_names)]
    last_date_str = date_strs[-1]
    return date.fromisoformat(last_date_str) + timedelta(days=1)

# return /stats response for a provided date
def request_stats(adate):
  cmd = Template("https://api.enphaseenergy.com/api/$version/systems/$system/stats").substitute({'version':'v2', 'system':system()})
  start_at = int(_time.mktime(adate.timetuple()))
  payload = {'datetime_format':'iso8601', 'key':key(), 'user_id':userid(), 'start_at':start_at}
  return requests.get(cmd, payload)

def request_stats_v4_orig(adate):
  cmd = Template("https://api.enphaseenergy.com/api/$version/systems/$system/stats").substitute({'version':'v4', 'system':system()})
  start_at = int(_time.mktime(adate.timetuple()))
  payload = {'datetime_format':'iso8601', 'key':key(), 'user_id':userid(), 'start_at':start_at}
  return requests.get(cmd, payload)

# request tokens
def request_tokens():
    cmd = 'https://api.enphaseenergy.com/oauth/token'
    headers = {'Authorization': 'Basic YmQ4Y2Q0ODkxYmI4YTEwNjUxMDM4OTdkODMzYjdmOGE6NGFhNWIyYjRhNWM5YzYwNDk3NDNiOTY1ZjA5ZDJmMDQ='}
    params = {
        'grant_type': 'authorization_code',
        'redirect_uri': 'https://api.enphaseenergy.com/oauth/redirect_uri',
        'code': 'CPolri'
    }
    response = requests.get(cmd, headers=headers, params=params)
    return response
# revenue-grade meters
def request_stats_v4(adate):
  url = "https://api.enphaseenergy.com/api/{0}}/systems/{1}}/rgm_stats".format(v4_version(), system())
  params = {""}
  cmd = Template("https://api.enphaseenergy.com/api/$version/systems/$system/rgm_stats").substitute({'version':'v4', 'system':system()})
  start_at = int(_time.mktime(adate.timetuple()))
  payload = {}
  return requests.get(cmd, payload)



def convert_intervals_to_rows(json):
  return [[interval['end_at'], interval['powr'], interval['enwh']] for interval in json['intervals']]

# save to a csv file
def save_to_file(adate):
  response = request_stats(adate)
  stats_data = response.json()
  if response.status_code != requests.codes.ok:
    print("FAILURE:", stats_data)
    return False
  else:
    rows = sorted(convert_intervals_to_rows(stats_data), key = lambda row: row[0])
    adate_str = adate.strftime("%Y-%m-%d")
    new_file_name = path() + Template('stats_$d.csv').substitute({'d':adate_str})
    with open(new_file_name, 'w') as csvfile:
      writer = csv.writer(csvfile, delimiter=',')
      for row in rows:
        writer.writerow(row)
    print("SUCCESS:", len(rows), "rows written to ", new_file_name)
    return True

# save to csv files
# start_date: overwrite forward from start_date or last date in files if earlier
# complete_days:
#     True: ignore data for today, which may not represent the whole day
#     False: save today's data
def save_to_files(complete_days=True, start_date=None):  
  dates_processed = 0
  next_date = compute_next_date()
  last_date = None
  if start_date != None:
    next_date = min([start_date, next_date])
  while next_date < (datetime.now().date() + timedelta(days=0 if complete_days else 1)):
    if save_to_file(next_date):
      last_date = next_date
      _time.sleep(6.1) # enphase API no cost plan has a max of 10 requests per minute
      next_date = next_date + timedelta(days=1)
      dates_processed += 1
    else:
      break
  return {'dates_processed':dates_processed, 'last_date_processed':last_date}

# ========================================
# from files to python calcs
#
# retrieve_from_files
# select_rows
# ========================================
            
def transform_row(row):  
  date_time, watts, watt_hours = row
  dt = datetime.fromisoformat(date_time)
  d = dt.date()
  t = dt.timetz()
  w = int(watts)
  wh = int(watt_hours)
  return [d,t,dt,w,wh]

def retrieve_rows_from_file(file):
  with open(file) as csvfile:
    rdr = csv.reader(csvfile, delimiter=',')
    rows = [transform_row(row) for row in rdr]
    # sort by date-time
    rows = sorted(rows, key=lambda row: row[2])
    # remove duplicates
    result = []
    old_datetime = datetime(1,1,1,0,0,0)
    for row in rows:
      new_datetime = row[2]
      if new_datetime != old_datetime:
        result.append(row)
        old_datetime = new_datetime
    return result
    
def update_rows(transformed_rows):  
  sort1 = sorted(transformed_rows, key=lambda x: x[1])
  rows = sorted(sort1, key=lambda x: x[0])
  # include forward totals
  date1 = date(1,1,1)
  for row in rows:
    date2, t, date_time, watts, watt_hours = row
    if date2 != date1:
      forward = watt_hours
      date1 = date2
    else:
      forward = forward + watt_hours
    row.append(forward)
  # include backward totals and peak tests
  r = range(len(rows)-1,-1,-1)
  date1 = date(1,1,1)
  for i in r:
    date2, t, date_time, watts, watt_hours, forward = rows[i]
    if date2 != date1:
      backward = 0
      date1 = date2
    else:
      backward = backward + watt_hours
    rows[i].append(backward)
    # peak == 1 when forward number is close to backward number -- energy roughly at mid-day peak
    if forward > 0 and backward > 0 and abs(1 - (forward / backward)) < 0.025:
       peak = 1
    else:
       peak = 0
    rows[i].append(peak)
  return rows

def retrieve_rows_from_files():
  file_names = compute_file_names()
  rows = []
  for file_name in file_names:
    rows.extend(update_rows(retrieve_rows_from_file(file_name)))
  return rows

# selects rows based on specified increments specified in minutes
# enphase produces data in 5 minute increments
# transform results produced by retrieve_from_files with this function
def select_rows(raw_rows, increment=5):
  assert((0 == increment % 5) & (increment > 0) & (increment <= 61)), Template('invalid increment: $increment').substitute({"increment":increment})
  if increment != 5:
    row_test = lambda row: 0 == row[2].minute % increment
    rows = [row for row in raw_rows if row_test(row)]
  else:
    rows = raw_rows
  return rows
            
# ========================================
# all at once
#
# compute_data_frame
# ========================================

def compute_data_frame(increment=5):
  raw_rows = retrieve_rows_from_files()
  rows = select_rows(raw_rows, increment=increment)
  columns = [d, t, dt, w, wh, f, b, p]
  data = pd.DataFrame(rows, columns = columns)
  return data

def augment_data_frame(data):
  alt_azi = data.apply(lambda x: a.compute_portland_altitude_azimuth(x.date, x.time), axis=1).to_list()
  data[['altitude', 'azimuth']] = pd.DataFrame(alt_azi, index=data.index)

  south_angle = data.apply(lambda x: a.compute_surface_incident_angle(x.altitude, x.azimuth, a.roof_angle(), 0),axis=1)
  west_angle = data.apply(lambda x: a.compute_surface_incident_angle(x.altitude, x.azimuth, a.roof_angle(), 90),axis=1)
  data['south_angle'], data['west_angle'] = south_angle, west_angle

  data['combined_angle'] = data['south_angle'] + 0.9 * data['west_angle']

# ========================================
# aware date/time utilities
#
# make_time
# by_date
# by_time
# ========================================

#return an aware time object
def make_time(time_in_it):
  tz = timezone(timedelta(hours=-7), 'UTC')
  if isinstance(time_in_it, time):
    return time_in_it.replace(tzinfo=tz)
  elif isinstance(time_in_it, datetime):
    return time(time_in_it.hour, time_in_it.minute, time_in_it.second, tzinfo=tz)
  else:
    assert('arg should be time or datetime instances')
        
def by_date(data, start, stop):
  return data.loc[(data[d]>=start) & (data[d]<=stop)]

def by_time(data, start, stop):
  start = make_time(start)
  stop = make_time(stop)
  return data.loc[(data[t]>=start) & (data[t]<=stop)]

def pge_online_date():
  return date(2020,3,4)

def today():
  return a.today()

def yesterday():
  return today() + timedelta(days=-1)

def bom():
  return date(today().year, today().month, 1)

def hour(hr):
  return time(hr,0,0)

def start_time():
  return time(4, 45, 0, 0) # 5:15am PDT

def stop_time():
  return time(21, 15, 0, 0) # 9:15pm PDT

# ========================================
# column labels
# ========================================

d = 'date'
t = 'time'
dt = 'date_time'
w = 'watts'
wh = 'watt_hours'
f = 'forward'
b = 'backward'
p = 'peak'
alt = 'altitude'
azi = 'aximuth'
west = 'west_angle'
south = 'south_angle'
combined = 'combined_angle'

# ========================================
# transformation
# ========================================

def stats_by_time(data, column=wh, start_date=pge_online_date(), stop_date=today()):
  start_date = max([start_date, pge_online_date()])
  stop_date = min([stop_date, today()])
  selected = by_date(data, start_date, stop_date)
  grouped = selected.groupby(t)
  return grouped[column].agg([np.min,np.mean,np.max])

def pivot_by_date_time(data, values=w, start_date=pge_online_date(), stop_date=today(), start_time=start_time(), stop_time=stop_time()):
  start_date = max([start_date, pge_online_date()])
  stop_date = min([stop_date, today()])
  selected = by_date(data, start_date, stop_date)
  selected = by_time(selected, start_time, stop_time)
  return selected.pivot(index=d,columns=t,values=values)