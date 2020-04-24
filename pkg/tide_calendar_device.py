"""Tide calendar adapter for Mozilla WebThings Gateway."""

from gateway_addon import Device
import datetime
import requests
import threading
import time

from .tide_calendar_property import TideCalendarProperty
from .util import get_tzinfo_from_abbreviation


_POLL_INTERVAL = 60 * 6


class StationException(Exception):
    """Generic exception to indicate an issue with the station."""

    pass


class TideCalendarDevice(Device):
    """Tide calendar device type."""

    def __init__(self, adapter, _id, station_id, unit):
        """
        Initialize the object.

        adapter -- the Adapter managing this device
        _id -- ID of this device
        station_id -- the NOAA station ID
        unit -- the unit to use, either english or metric
        """
        Device.__init__(self, adapter, _id)
        self._type = []

        self.station_id = station_id
        self.unit = unit

        self.get_station_info()

        self.high_tides = []
        self.low_tides = []

        if self.have_tide_predictions:
            self.properties['lowTideTime'] = TideCalendarProperty(
                self,
                'lowTideTime',
                {
                    'title': 'Low Tide Time',
                    'type': 'string',
                    'readOnly': True,
                },
                ''
            )

            self.properties['lowTideLevel'] = TideCalendarProperty(
                self,
                'lowTideLevel',
                {
                    'title': 'Low Tide Level',
                    'type': 'number',
                    'unit': 'foot' if self.unit == 'english' else 'meter',
                    'multipleOf': 0.1,
                    'readOnly': True,
                },
                0
            )

            self.properties['lowTide'] = TideCalendarProperty(
                self,
                'lowTide',
                {
                    'title': 'Low Tide',
                    'type': 'boolean',
                    'readOnly': True,
                },
                False
            )

            self.properties['highTideTime'] = TideCalendarProperty(
                self,
                'highTideTime',
                {
                    'title': 'High Tide Time',
                    'type': 'string',
                    'readOnly': True,
                },
                ''
            )

            self.properties['highTideLevel'] = TideCalendarProperty(
                self,
                'highTideLevel',
                {
                    'title': 'High Tide Level',
                    'type': 'number',
                    'unit': 'foot' if self.unit == 'english' else 'meter',
                    'multipleOf': 0.1,
                    'readOnly': True,
                },
                0
            )

            self.properties['highTide'] = TideCalendarProperty(
                self,
                'highTide',
                {
                    'title': 'High Tide',
                    'type': 'boolean',
                    'readOnly': True,
                },
                False
            )

            self.properties['status'] = TideCalendarProperty(
                self,
                'status',
                {
                    'title': 'Status',
                    'type': 'string',
                    'enum': [
                        'low',
                        'high',
                        'rising',
                        'falling',
                    ],
                    'readOnly': True,
                },
                ''
            )

        if self.have_water_levels:
            self._type = ['MultiLevelSensor']
            self.properties['currentLevel'] = TideCalendarProperty(
                self,
                'currentLevel',
                {
                    'title': 'Current Level',
                    '@type': 'LevelProperty',
                    'type': 'number',
                    'unit': 'foot' if self.unit == 'english' else 'meter',
                    'multipleOf': 0.1,
                    'minimum': -50 if self.unit == 'english' else -15.2,
                    'maximum': 50 if self.unit == 'english' else 15.2,
                    'readOnly': True,
                },
                0
            )

        self.links = [
            {
                'rel': 'alternate',
                'mediaType': 'text/html',
                'href': 'https://tidesandcurrents.noaa.gov/noaatidepredictions.html?id={}'.format(self.station_id),  # noqa
            },
        ]

        t = threading.Thread(target=self.poll)
        t.daemon = True
        t.start()

        t = threading.Thread(target=self.check_events)
        t.daemon = True
        t.start()

    def get_station_info(self):
        """Try to retrieve station info."""
        url = 'https://tidesandcurrents.noaa.gov/mdapi/latest/webapi/stations/{}.json'.format(self.station_id)  # noqa

        try:
            r = requests.get(url, params={'expand': 'products'})
            r.raise_for_status()
            data = r.json()
        except requests.exceptions.RequestException:
            raise StationException(
                'Error fetching station info for station {}.'
                .format(self.station_id)
            )

        try:
            info = data['stations'][0]
            products = info['products']['products']
        except KeyError:
            raise StationException(
                'Error fetching station info for station {}.'
                .format(self.station_id)
            )

        self.tzinfo = get_tzinfo_from_abbreviation(info['timezone'])
        self.name = 'Tide Calendar ({})'.format(info['name'])
        self.description = self.name

        self.have_water_levels = False
        self.have_tide_predictions = False

        for product in products:
            if product['name'] == 'Water Levels':
                self.have_water_levels = True
            elif product['name'] == 'Tide Predictions':
                self.have_tide_predictions = True

        if not self.have_water_levels and not self.have_tide_predictions:
            raise StationException(
                'Water levels and tide predictions are both unavailable for '
                'station {}'.format(self.station_id)
            )

    def poll(self):
        """Poll NOAA for changes."""
        while True:
            now = datetime.datetime.now(tz=self.tzinfo).replace(tzinfo=None)

            if self.have_tide_predictions:
                url = 'https://tidesandcurrents.noaa.gov/api/datagetter'

                try:
                    r = requests.get(
                        url,
                        params={
                            'product': 'predictions',
                            'application': 'NOS.COOPS.TAC.WL',
                            'begin_date': '{}{:02d}{:02d}'.format(now.year, now.month, now.day),  # noqa
                            'range': '36',
                            'datum': 'MLLW',
                            'station': '{}'.format(self.station_id),
                            'time_zone': 'lst_ldt',
                            'units': self.unit,
                            'interval': 'hilo',
                            'format': 'json',
                        }
                    )
                    r.raise_for_status()
                    data = r.json()
                except requests.exceptions.RequestException as e:
                    print('Error fetching tide predictions: {}'.format(e))
                else:
                    try:
                        predictions = data['predictions']
                    except KeyError:
                        print('Invalid tide prediction data for station {}'
                              .format(self.station_id))
                    else:
                        self.high_tides = []
                        self.low_tides = []

                        set_high = False
                        set_low = False

                        for prediction in predictions:
                            parsed = datetime.datetime.strptime(
                                prediction['t'],
                                '%Y-%m-%d %H:%M'
                            )

                            if parsed < now:
                                continue

                            level = round(float(prediction['v']), 1)
                            timestamp = prediction['t'].split(' ')[1]

                            if prediction['type'] == 'H':
                                self.high_tides.append({
                                    'datetime': parsed,
                                    'level': level,
                                    'timestamp': timestamp,
                                })

                                if not set_high:
                                    self.properties['highTideLevel'].update(
                                        level
                                    )
                                    self.properties['highTideTime'].update(
                                        timestamp
                                    )
                                    set_high = True
                            elif prediction['type'] == 'L':
                                self.low_tides.append({
                                    'datetime': parsed,
                                    'level': level,
                                    'timestamp': timestamp,
                                })

                                if not set_low:
                                    self.properties['lowTideLevel'].update(
                                        level
                                    )
                                    self.properties['lowTideTime'].update(
                                        timestamp
                                    )
                                    set_low = True

            if self.have_water_levels:
                url = 'https://tidesandcurrents.noaa.gov/api/datagetter'

                try:
                    r = requests.get(
                        url,
                        params={
                            'product': 'water_level',
                            'application': 'NOS.COOPS.TAC.WL',
                            'date': 'latest',
                            'datum': 'MLLW',
                            'station': '{}'.format(self.station_id),
                            'time_zone': 'lst_ldt',
                            'units': self.unit,
                            'format': 'json',
                        }
                    )
                    r.raise_for_status()
                    data = r.json()
                except requests.exceptions.RequestException as e:
                    print('Error fetching water levels: {}'.format(e))
                else:
                    try:
                        level = data['data'][0]
                    except KeyError:
                        print('Invalid water level data for station {}'
                              .format(self.station_id))
                    else:
                        self.properties['currentLevel'].update(
                            round(float(level['v']), 1)
                        )

            time.sleep(_POLL_INTERVAL)

    def check_events(self):
        """Check for current tide events."""
        while True:
            time.sleep(1)

            now = datetime.datetime.now(tz=self.tzinfo).replace(
                tzinfo=None,
                second=0,
                microsecond=0
            )

            status_set = False

            if len(self.high_tides) > 0:
                next_high_tide = self.high_tides[0]['datetime']

                if now == next_high_tide:
                    self.properties['highTide'].update(True)
                    self.properties['status'].update('high')
                    status_set = True
                else:
                    if next_high_tide < now:
                        self.high_tides.pop(0)

                        if len(self.high_tides) > 0:
                            next_high_tide = self.high_tides[0]
                            self.properties['highTideLevel'].update(
                                next_high_tide['level']
                            )
                            self.properties['highTideTime'].update(
                                next_high_tide['timestamp']
                            )

                    self.properties['highTide'].update(False)

            if len(self.low_tides) > 0:
                next_low_tide = self.low_tides[0]['datetime']

                if now == next_low_tide:
                    self.properties['lowTide'].update(True)
                    self.properties['status'].update('low')
                    status_set = True
                else:
                    if next_low_tide < now:
                        self.low_tides.pop(0)

                        if len(self.low_tides) > 0:
                            next_low_tide = self.low_tides[0]
                            self.properties['lowTideLevel'].update(
                                next_low_tide['level']
                            )
                            self.properties['lowTideTime'].update(
                                next_low_tide['timestamp']
                            )

                    self.properties['lowTide'].update(False)

            if len(self.high_tides) > 0 and \
                    len(self.low_tides) > 0 and \
                    not status_set:
                next_low_tide = self.low_tides[0]
                next_high_tide = self.high_tides[0]

                if next_low_tide['datetime'] < next_high_tide['datetime']:
                    self.properties['status'].update('falling')
                else:
                    self.properties['status'].update('rising')
