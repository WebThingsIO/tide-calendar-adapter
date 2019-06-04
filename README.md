# tide-calendar-adapter

Tide calendar adapter for Mozilla WebThings Gateway.

# Configuration

To configure the adapter, navigate to _Settings -> Add-ons_ in the user interface and click the _Configure_ button on the entry for this adapter.

## Stations

Each station is a numeric station ID. You can find the station ID by searching on [this website](https://tidesandcurrents.noaa.gov/) for the station closest to you.

## Unit

This is the tide level unit you want, either feet (english) or meters (metric).

# Requirements

If you're running this add-on outside of the official gateway image for the Raspberry Pi, i.e. you're running on a development machine, you'll need to do the following (adapt as necessary for non-Ubuntu/Debian):

```
sudo apt install python3-dev libnanomsg-dev
sudo pip3 install nnpy
sudo pip3 install git+https://github.com/mozilla-iot/gateway-addon-python.git
```
