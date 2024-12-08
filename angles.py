#computes the altitude and azimuth for days between start_date() and stop_date()
#and for minutes between start_time() and stop_time()

#adjust for daylight savings (see hours_adjustment)
#further selects values around altitude of 0 degrees and
#azimuths of 90 (east), 135 (southeast), 180 (south), 225 (southwest) and 270 (west)

#python 2.7.x code heavily uses ...
#  1. python date library described in https://docs.python.org/2/library/datetime.html#
#  2. python astronomical library described in http://rhodesmill.org/pyephem/index.html
#      pyephem installs in /Library/Python/2.7/site-packages/ephem after invoking ...
#          sudo pip install ephem
          
#longitudes, latitudes, and independent verification of angle calculations ...
#  https://www.esrl.noaa.gov/gmd/grad/solcalc/azel.html
  
#python3 -m pip install --upgrade pyephem

#https://ericasadun.com/2016/12/04/running-python-in-xcode-step-by-step/

#to run ...
#  open xcode
#  select angles.py
#  run

import ephem
import math
import sys
from datetime import date, time, datetime, tzinfo, timedelta
from geopy.geocoders import Nominatim
import functools as ft

hours_adjustment = 7 # adjust for daylight savings
adjusted_datetime = lambda d, t: datetime.combine(d, t) + timedelta(hours=hours_adjustment)
test_altitude = lambda angle, desired_angle: abs(angle - desired_angle) < 0.3
test_azimuth = lambda angle, desired_angle: abs(angle - desired_angle) < 0.3
round_angle = lambda angle: int(round(angle, 0))
degree_symbol = "\xb0" #u"\N{DEGREE SIGN}".encode('utf-8') # latest update to xcode required .encode(blah)
format_angle = lambda angle: ("{0}{1}").format(round_angle(angle), degree_symbol)

def today():
    return datetime.now().date()
def current_year():
    return today().year
def vernal_equinox(year=current_year()):
    return date(year, 3, 21)
def summer_solstice(year=current_year()):
    return date(year, 6, 21)
def autumnal_equinox(year=current_year()):
    return date(year, 9, 21)
def winter_solstice(year=current_year()):
    return date(year, 12, 21)


def email_address():
  return 'beaver@electronhead.com'




def compute_portland_altitude_azimuth(d, t):
  return compute_altitude_azimuth(portland(), d, t)

def compute_altitude_azimuth(o, d, t):
  altitude, azimuth = compute_altitude_azimuth_radians(o, d, t)
  return math.degrees(altitude), math.degrees(azimuth)

def compute_altitude_azimuth_radians(o, d, t):
  adt = adjusted_datetime(d, t)
  o.date = '{0} {1}'.format(adt.date().isoformat(), adt.time().isoformat())
  s = ephem.Sun(o)
  return s.alt, s.az




# the model here is an inclined surface. The angle of sunlight on the surface
# depends on the solar altitude, solar azimuth, the surface incline, and the rotation
# of the surface relative to due south (e.g. - south-facing 0, west-facing 90)
def compute_surface_incident_angle(altitude, azimuth, incline, rotation):
  if altitude < 0:
    return 0
  else:
    rotated_azimuth = rotate_azimuth(azimuth, rotation)
    return max(0, altitude + incline * ((rotated_azimuth / 90) - 1))

def rotate_azimuth(azimuth, rotation):
  rotated = azimuth - rotation
  if rotated < 0:
    rotated += 360
  if rotated > 180:
    rotated = 360 - rotated
  return rotated



def roof_angle():
  return angle_from_sides(5, 12)

def angle_from_sides(opposite, hypoteneuse):
  return math.degrees(math.asin(opposite / hypoteneuse))

def generate_datetimes(date_time_1, date_time_2, minutes=5):
  delta_minutes = timedelta(minutes=minutes)
  dt = date_time_1
  while dt <= date_time_2:
    yield dt
    dt += delta_minutes

def generate_datetimes_for_time_window(date_1, date_2, time_1, time_2, minutes=5):
  delta_minutes = timedelta(minutes=minutes)
  delta_days = timedelta(days=1)
  d = date_1
  while d <= date_2:
    t = time_1
    while t <= time_2:
      dt = datetime.combine(d,t)
      yield dt
      dt += delta_minutes
      t = dt.time()
    d += delta_days

def compute_angles_for_datetime(o, dt, incline):
  d = dt.date()
  t = dt.time()
  altitude, azimuth = compute_altitude_azimuth(o,d,t)
  south = compute_surface_incident_angle(altitude, azimuth, incline, 0)
  west = compute_surface_incident_angle(altitude, azimuth, incline, 90)
  return [dt, d,t,altitude,azimuth,south,west]

def compute_angles(o, date_time_1, date_time_2, incline=roof_angle(), minutes=5):
  datetimes = generate_datetimes(date_time_1, date_time_2, minutes=minutes)
  return [compute_angles_for_datetime(o, dt, incline) for dt in datetimes]

def compute_angles_for_time_window(o, date_1, date_2, time_1, time_2, incline=roof_angle(), minutes=5):
  datetimes = generate_datetimes_for_time_window(date_1, date_2, time_1, time_2, minutes=minutes)
  return [compute_angles_for_datetime(o, dt, incline) for dt in datetimes]




@ft.cache
def retrieve_geocode(address):
  return Nominatim(user_agent=email_address()).geocode(address)

# see https://rhodesmill.org/pyephem/ for comment about ephem handling of longitude and latitude
# Instead of making angular units explicit in your code, PyEphem tried to be clever
# but only wound up being obscure. An input string '1.23' is parsed as degrees of
# declination (or hours, when setting right ascension) but a float 1.23 is assumed 
# to be in radians. Angles returned by PyEphem are even more confusing: print them,
# and they display degrees; but do math with them, and you will find they are radians. 
# This causes substantial confusion and makes code much more difficult to read, but 
# can never be fixed without breaking programs that already use PyEphem.
def compute_observer(address, elevation):   #="2827 SE 49th Avenue, Portland, Oregon, US", elevation=62.1):
  o = ephem.Observer()
  # for some reasone Nominatim is not working as of 4/10/2023
  # hard-coded longitude and latitude for home address
  o.lon, o.lat, o.elevation, o.name = str(-122.61232886437568), str(45.5021065), elevation, address
  #g = retrieve_geocode(address)
  #o.lon, o.lat, o.elevation, o.name = str(g.longitude), str(g.latitude), elevation, address
  return o

def portland():
  return compute_observer("2827 SE 49th Avenue, Portland, Oregon, US", 62.1)

observer = portland




def compute_table(o, date_1, date_2, time_1, time_2):
  result = []
  datetimes = generate_datetimes_for_time_window(date_1, date_2, time_1, time_2, minutes=1)
  prior_date = date(1970, 1, 1)
  for dt in datetimes:
    d = dt.date()
    if d != prior_date:
      last_rez3 = ""
      last_rez2 = ""
      prior_date = d
    t = dt.time()
    altitude, azimuth = compute_altitude_azimuth(o,d,t)
    alt, azi = ft.partial(test_altitude, altitude), ft.partial(test_azimuth, azimuth)
    if alt(0) or azi(90) or azi(135) or azi(180) or azi(225) or azi(270):
      rez0 = d.strftime("%Y-%m-%d")
      rez1 = t.strftime("%H:%M")
      if alt(0):
        rez2 = "RISE" if azimuth < 180 else "SET"
      else:
        rez2 = format_angle(altitude)
      if azi(90) and rez2 != "RISE":
        rez3 = "E"
      elif azi(135):
        rez3 = "SE"
      elif azi(180):
        rez3 = "S"
      elif azi(225):
        rez3 = "SW"
      elif azi(270) and rez2 != "SET":
        rez3 = "W"
      else: # http://stackoverflow.com/questions/3215168/how-to-get-character-in-a-string-in-python
        rez3 = format_angle(azimuth)
      if rez3 != last_rez3:
        if rez2 != last_rez2:
          result.append([rez0, rez1, rez2, rez3])
          last_rez2 = rez2
          last_rez3 = rez3
  return len(result), result

def print_table(observer, count, table):
  print('location:', observer.name, 'lon:', observer.lon, 'lat:', observer.lat)
  print('count:', count)
  print ("python version: ", sys.version)
  for x in table:
    print ("{0}\t{1}\t{2}\t{3}".format(x[0],x[1],x[2],x[3]))

# class Surface:
#   def __init__(self, slope=25, rotation=0):
#     self.slope = slope
#     self.rotation = rotation

#   def compute_solar_incidence_angle(self, altitude, azimuth):
#     if altitude < 0:
#       return 0
#     else:
#       rotated_azimuth = rotate_azimuth(azimuth)
#       return max(0, altitude + self.slope * ((rotated_azimuth / 90) - 1))

#   def rotate_azimuth(self, azimuth):
#     rotated = azimuth - self.rotation
#     if rotated < 0:
#       rotated += 360
#     if rotated > 180:
#       rotated = 360 - rotated
#     return rotated

# class Location:
#   def __init__(self, email_address, address, elevation=100):
#     self.email_address
#     self.address = address
#     self.elevation = elevation
#     init()
    
#   def init(self):
#     self.o = ephem.Observer()
#     g = self.retrieve_geocode()
#     self.o.lon, self.o.lat, self.o.elevation, self.o.name = str(g.longitude), str(g.latitude), elevation, address

#   @ft.cache
#   def retrieve_geocode(self):
#     return Nominatim(user_agent=self.email_address).geocode(self.address)

#   def compute_altitude_azimuth_radians(self, d, t):
#     adt = adjusted_datetime(d, t)
#     self.o.date = '{0} {1}'.format(adt.date().isoformat(), adt.time().isoformat())
#     s = ephem.Sun(self.o)
#     return s.alt, s.az