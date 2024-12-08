import requests
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
import json

# ========================================
# environment variables
#   [defined in ~/.profile]
# ========================================

def system_id():
  return os.environ['ENPHASE_SYSTEM_ID']

def stats_path():
  return os.environ['ENPHASE_V4_STATS_PATH']

def token_path():
  return os.environ['ENPHASE_V4_TOKEN_PATH']

def api_version():
  return os.environ['ENPHASE_V4_API_VERSION']

def api_key():
  return os.environ['ENPHASE_V4_API_KEY']

def redirect_uri():
  return os.environ['ENPHASE_V4_REDIRECT_URI']

def client_id():
  return os.environ['ENPHASE_V4_CLIENT_ID']

def client_secret():
  return os.environ['ENPHASE_V4_CLIENT_SECRET']

def encoded_client_secret():
  id_secret = f"{client_id()}:{client_secret()}"
  encoded_bytes = base64.b64encode(id_secret.encode("utf-8"))
  return str(encoded_bytes, "utf-8")

def client_code():
  with open(token_path() + 'access_token', 'r') as file:
    return file.read().rstrip('\n')
  #return 'WTLu7S'
  #  return os.environ['ENPHASE_V4_CLIENT_CODE']

def authorization_code():
  with open(token_path() + 'authorization_code', 'r') as file:
    return file.read().rstrip('\n')
  #return 'WTLu7S'
  #  return os.environ['ENPHASE_V4_CLIENT_CODE']

def print_environ():
  print('ENPHASE_SYSTEM_ID:', system_id())
  print('ENPHASE_STATS_PATH:', stats_path())
  print('ENPHASE_API_VERSION:', api_version())
  print('ENPHASE_API_KEY:', api_key())
  print('ENPHASE_CLIENT_ID', client_id())
  print('ENPHASE_CLIENT_SECRET', client_secret())
  print('ENPHASE_ENCODED_CLIENT_SECRET', encoded_client_secret())
  print('ENPHASE_CLIENT_CODE', client_code())
  
def refresh_token_exists():
  refresh_token_file_path = token_path() + 'refresh_token'
  return os.path.exists(refresh_token_file_path) and os.path.getsize(refresh_token_file_path) > 0

# ========================================
# request data from enphase
#
#   request_access_token
#   request_tokens
#   request_refresh_token
#   request_stats
# ========================================

def request_client_code():
  cmd = f"https://api.enphaseenergy.com/oauth/authorize"
  params = {
    "response_type": "code",
    "client_id": client_id(),
    "redirect_uri": "https://api.enphaseenergy.com/oauth/redirect_uri"
  }
  response = requests.post(cmd, params = params)
  return response

# return access_token using two functions, request_tokens() and request_refresh_token
# request_tokens() is the initial call that creates and populates the file, refresh_token, using a fresh
#   authorization code
# if the file, refresh_token, exists and its value is fresh enough relative to the authorizing authorization code,
#   then the function will produce a valid refresh_token and the computation can proceed
# if the authorization code contained in the file, authorization_code, is stale, the computation will fail, requiring
#   another authorization step
def request_access_token():
  response = ''
  if refresh_token_exists():
    response = request_refresh_token()
  else:
    response = request_tokens()
  if response.status_code == requests.codes.ok:
    response_data = response.json()
    access_token = response_data['access_token']
    refresh_token = response_data['refresh_token']
    with open(token_path() + 'access_token', 'w') as file:
      file.write(access_token)
    with open(token_path() + 'refresh_token', 'w') as file:
      file.write(refresh_token)
    return access_token
  else:
    print("\nrequest_access_token FAILURE:", response.json())
    return None

# request tokens (access and refresh tokens) 'grant_type': 'authorization_code'
def request_tokens():
  cmd = 'https://api.enphaseenergy.com/oauth/token'
  headers = {
    'Authorization': f"Basic {encoded_client_secret()}"
  }
  params = {
    'grant_type': 'authorization_code',
    'redirect_uri': redirect_uri(),
    'code': authorization_code()
  }
  response = requests.post(
    cmd, 
    headers = headers, 
    params = params
  )
  # print('\nrequest_tokens response data...\n')
  # print({
  #   'response': response,
  #   'response_json': response.json()
  # })
  return response

# request tokens (access and refresh tokens) 'grant_type': 'refresh_token'
# https://developer-v4.enphase.com/docs/quickstart.html#step_10
def request_refresh_token():
  with open(token_path() + 'refresh_token', 'r') as file:
    unique_refresh_token = file.read().rstrip('\n')
  cmd = f"https://api.enphaseenergy.com/oauth/token"
  headers = {
    'Authorization': f"Basic {encoded_client_secret()}"
  }
  params = {
    'grant_type': 'refresh_token',
    'refresh_token': unique_refresh_token
  }
  response = requests.post(
    cmd, 
    headers = headers, 
    params = params
  )
  # print('\nrequest_refresh_token response data...\n')
  # print({
  #   'response': response,
  #   'response_json': response.json()
  # })
  return response
    
# request stats for a provided date
def request_stats(adate, access_token):
  cmd = f"https://api.enphaseenergy.com/api/{api_version()}/systems/{system_id()}/telemetry/production_micro"
  headers = {
    'Authorization': f"Bearer {access_token}"
  }
  params = {
    'key': api_key()
  }
  #start_date_string = adate.strftime("%Y-%m-%d")
  #payload = {
  #  'start_date': start_date_string, # instead of start_at int
  #  'granularity': '5mins' # 'week', 'day', '15mins', '5mins'. Default is 'day'
  #}
  start_at = int(_time.mktime(adate.timetuple()))
  payload = {
    'start_at': start_at, 
    'granularity': '5mins' # 'week', 'day', '15mins', '5mins'. Default is 'day'
  }
  print(f"\npayload{payload}")
  response = requests.get(
    cmd, 
    params = params, 
    headers = headers, 
    data = payload
  )
  if False:
    print('\nstats response data...\n')
    print({
      'response': response,
      'response_json': response.json()
    })
  return response
    
# ========================================
# from enphase to files
#
# save_to_files
# ========================================

def compute_file_names():
  return sorted(glob.glob(stats_path() + "stats_*.csv"))

def compute_next_date():
  file_names = compute_file_names()
  if not file_names:
    return date(2020,3,4)
  else:  
    d_re = re.compile('_(.*)\\.') # select characters between '_' and '.', as in stats_2020-10-14.csv
    date_strs = [d_re.findall(file_name)[0] for file_name in sorted(file_names)]
    last_date_str = date_strs[-1]
    return date.fromisoformat(last_date_str) + timedelta(days=1)

def convert_interval_to_row(interval):
  end_at_int = interval['end_at']
  # https://stackoverflow.com/questions/2150739/iso-time-iso-8601-in-python
  end_at_string = datetime.fromtimestamp(end_at_int).astimezone().replace(microsecond=0).isoformat()
  #print(f"interval: {interval} end_at_int: {end_at_int} end_at_string: {end_at_string}")
  powr = interval['powr']
  enwh = interval['enwh']
  return [end_at_string, powr, enwh]

def convert_intervals_to_rows(json):
  return [convert_interval_to_row(interval) for interval in json['intervals']]

# save to a csv file
def save_to_file(adate, access_token):
  response = request_stats(adate, access_token)
  stats_data = response.json()
  if response.status_code != requests.codes.ok:
    print("\nSTATS FAILURE:", stats_data)
    return False
  else:
    rows = sorted(convert_intervals_to_rows(stats_data), key = lambda row: row[0])
    #rows = [row for row in rows if (row[1]>0 or row[2]>0)]
    adate_str = adate.strftime("%Y-%m-%d")
    new_file_name = stats_path() + f"stats_{adate_str}.csv"
    with open(new_file_name, 'w') as csvfile:
      writer = csv.writer(csvfile, delimiter=',')
      print(rows[0])
      print(adate)
      for row in rows:
        #print(row)
        writer.writerow(row)
    print("SUCCESS:", len(rows), "rows written to ", new_file_name)
    return True

# save to csv files
# access_token
# start_date: overwrite forward from start_date or last date in files if earlier
# complete_days:
#     True: ignore data for today, which may not represent the whole day
#     False: save today's data
def save_to_files(access_token, complete_days=True, start_date=None):
  dates_processed = 0
  next_date = compute_next_date()
  last_date = None
  if start_date != None:
    next_date = min([start_date, next_date])
  while next_date < (datetime.now().date() + timedelta(days=0 if complete_days else 1)):
    if save_to_file(next_date, access_token):
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
  #dt = make_time(datetime.fromisoformat(date_time))
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
  assert((0 == increment % 5) & (increment > 0) & (increment <= 61)), f"invalid increment: {increment}"
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