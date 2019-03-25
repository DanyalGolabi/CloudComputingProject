# London Tube Query REST API

This project allows the user to query the TFL API through a number of URL pathways that return information such as arrivals per station, associated lines with a station, stations associated with a line and the general status of all lines. 

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes. See deployment for notes on how to deploy the project on a live system.

### Prerequisites

To run the software you will need Python 3.X onwards and the following, all of which can be installed with pip. 

```
python3 -m pip install flask
python3 -m pip install fuzzywuzzy
```

The software also required a TFL API key and ID that need to be added to instance/config.py in the appropriate place: 

```
API_KEY = 'INSERT_HERE'
APP_ID = 'INSERT_HERE'
```

### Installing

To install and activate this project, in terminal navigate to the root folder of the project. 

Activate the virtual env

```
source flask_venv/bin/activate

or for windows

source flask_venv\bin\activate
```

Run the application

```
python3 app.py
```

And navigate to port 8080 on the localhost using https

```
https://127.0.0.1:8080/
```

To access the data use one of the following endpoints: 
/arrivals/INSERT_STATION_NAME to get arrival information for a given station
/lines/INSERT_STATION_NAME to get associated lines with a given station
/status/ to get the status of all lines
/stations/INSERT_LINE_NAME to get associated stations with a given line. 


## Built With

* [Flask](http://flask.pocoo.org/) - The python framework used
* [sqlite3](https://www.sqlite.org/index.html) - Database software
* [TFL API](https://api-portal.tfl.gov.uk/docs) - Source for tube data

## Authors

* **Danyal Golabi** - *ECS781P Cloud Computing*
