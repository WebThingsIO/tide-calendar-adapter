"""Tide calendar adapter for Mozilla WebThings Gateway."""

from gateway_addon import Adapter, Database

from .tide_calendar_device import TideCalendarDevice, StationException


class TideCalendarAdapter(Adapter):
    """Adapter for NOAA tide calendars."""

    def __init__(self, verbose=False):
        """
        Initialize the object.

        verbose -- whether or not to enable verbose logging
        """
        self.name = self.__class__.__name__
        Adapter.__init__(self,
                         'tide-calendar-adapter',
                         'tide-calendar-adapter',
                         verbose=verbose)

        self.pairing = False
        self.start_pairing()

    def start_pairing(self, timeout=None):
        """
        Start the pairing process.

        timeout -- Timeout in seconds at which to quit pairing
        """
        if self.pairing:
            return

        self.pairing = True

        database = Database('tide-calendar-adapter')
        if not database.open():
            return

        config = database.load_config()
        database.close()

        if not config or 'stations' not in config or 'unit' not in config:
            return

        unit = config['unit']

        for station in config['stations']:
            _id = 'tide-calendar-{}'.format(station)
            if _id not in self.devices:
                try:
                    device = TideCalendarDevice(self, _id, station, unit)
                except StationException as e:
                    print(e)
                else:
                    self.handle_device_added(device)

        self.pairing = False

    def cancel_pairing(self):
        """Cancel the pairing process."""
        self.pairing = False
