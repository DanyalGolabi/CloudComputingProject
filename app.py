from flask import Flask, render_template, request, jsonify, current_app, g
from flask.cli import with_appcontext
from fuzzywuzzy import fuzz
import sqlite3,os,json,requests,requests_cache

# The below creates instances of the application and applies the configuration file to it's config property. 
# Addition globally used variables are assigned here as well, these are the host url for TFL's api, a credential string, setting 
# 'stations' as an array and filling tube_lines with an array of the accepted strings by TFL. 

app = Flask(__name__, instance_relative_config=True)
app.config.from_object('config') 
app.config.from_pyfile('config.py')

base_url = 'https://api.tfl.gov.uk'
creds = '?app_key='+app.config['API_KEY']+'&app_id='+app.config['APP_ID']
stations = []
tube_lines = ['bakerloo', 'central', 'circle', 'district', 'hammersmith-city', 'jubilee', 'metropolitan', 'northern', 'piccadilly', 'victoria', 'waterloo-city']

# (Below) When the app first boots it tries to create and populate a db table 'tflLookups' from a sql script. Once achieving this or by using
# and existing db, the app populates 'stations' with a list of all station names. The below three functions act as a group. 
# The database is used to contain two columns in a relation. The columns are 'station' and 'code', with station being the common name
# and code being the tfl code used to query the API. 
@app.before_first_request
def activate_db():
	try:
	    db = get_db()
	    with app.open_resource('stations.sql', mode='r') as f:
	        db.cursor().executescript(f.read())
	    db.commit()
	except Exception as e:
		print(e)
	db = get_db()
	cur = db.execute('select station from tflLookups')
	stations_rows = cur.fetchall()
	for row in stations_rows:
		stations.append(row[0])

def connect_db():
    rv = sqlite3.connect(app.config['DATABASE'])
    rv.row_factory = sqlite3.Row
    return rv

def get_db():
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db


# This function takes in a string-name for a station inputted by the user and iterates over the stations array checking for which 
# has the closest match. It uses the Levenshtein Distance contained in the fuzzywuzzy package to perform string matching, the threshold
# is set to 71 so a match would require at least that number of similarity to return results. This is to cover cases like Warren Street and
# Baker Street having a fairly high degree of simularity. 
def fuzzy_find_station(station):
	highest=0
	return_station=""
	for row in stations:
		ratio = fuzz.ratio(station.lower(),row.lower())
		if (ratio>highest):
			highest = ratio
			return_station = row
	if (highest < 70):
		return None
	return return_station

# This function does almost the same as the above, however it uses the tube_lines array and a lower threshold due to there being a greater
# degree of difference between them. The lower the threshold the easier it is for a user's inputs to be fuzzy matched. 
def fuzzy_find_line(line):
	highest=0
	return_line=""
	for entry in tube_lines:
		ratio = fuzz.ratio(line.lower(),entry.lower())
		if (ratio>highest):
			highest = ratio
			return_line = entry
	if (highest < 70):
		return None
	return return_line

# This function performs a simple query to the database looking for the relevant code of a station given its common name. 
def get_station_code_from_db(station):
	db = get_db()
	cur = db.execute('select code from tflLookups where station = "'+station+'"')
	station_codes = cur.fetchone()
	station_code = station_codes[0]
	return station_code

# This function appends given tfl code to the url pathway for station arrivals. 
def get_arrivals_by_code(code):
	return '/StopPoint/%s/arrivals' %code

# This function creates and returns an array of all tube lines found in the provided json.
def get_lines_from_json(result_json):
	lines = []
	for result in result_json:
		if (result.get('lineName', 'None')) not in lines:
			lines.append(result.get('lineName', 'None'))
	return lines

# This function returns the time in minutes (rounded) given the time in seconds.
def get_mins(time_in_secs):
	if (time_in_secs=='None'):
		return 'no'
	else:
		return str(round(int(time_in_secs)/60))


# The arrivals pathway, takes in a station (provided in the url) and returns the next 5 arrivals for that station and the remaining
# minutes to go until that train arrives (rounded). This function uses fuzzy matching to find the inputted station's code. Then calls the API
# end point. Out of the returned data the API pulls out the first 5 destinations and their respective times and returns as a dict. 
# The dict also returns a HATEOAS redirect instruction to the url for each line associated with this station and its respective stations. 
@app.route('/arrivals/<station>', methods=['GET', 'POST'])
def get_arrivals(station):
	arrivals_dict = {}
	matched_station = fuzzy_find_station(station)
	if (matched_station == None):
		return "Station not found, please try again."
	station_code = get_station_code_from_db(matched_station)
	resp = requests.get(base_url+get_arrivals_by_code(station_code)+creds)
	print(base_url+get_arrivals_by_code(station_code)+creds)
	if resp.status_code == 200:
		lines = get_lines_from_json(resp.json())
		for line in lines:
			count = 0
			arrivals = []
			for result in resp.json():
				if str(line) == result.get('lineName', 'None'):
					count+=1
					arrivals.append(str(result.get('destinationName', 'None'))+" in "+ get_mins(result.get('timeToStation', 'None')) +" minutes")
					if count>4:
						arrivals.append('For a list of all stations in this line, please use url pathway /stations/' + line.lower())
						break
			arrivals_dict[line] = arrivals
	else:
		print(resp.reason)
		return jsonify(resp.reason), 400
	return jsonify(arrivals_dict), 200


# The default landing url directs the user to explore the API using the other endpoints available. 
@app.route('/', methods=['GET'])
def landing_page():
	home_page = {
		'Options' : 'To access TFL data, please use the following URL endpoints',
		'Endpoints' : {
		'/status/' : 'To get the status of all lines',
		'/arrivals/INSERT_STATION_NAME' : 'to get arrival information for a given station',
		'/lines/INSERT_STATION_NAME' : 'to get associated lines with a given station',
		'/stations/INSERT_LINE_NAME' : 'to get associated stations with a given line'}
	}
	return jsonify(home_page)

# This url returns all lines associated with the user provided station. It performs fuzzy matching on the provided station and calls the API
# to return all lines assocaited with the station. It uses HATEOAS principles to direct users to the status url for more information.
@app.route('/lines/<station>', methods=['GET', 'POST'])
def get_lines(station):
	matched_station = fuzzy_find_station(station)
	if (matched_station == None):
		return "Station not found, please try again."
	station_code = get_station_code_from_db(matched_station)
	resp = requests.get(base_url+get_arrivals_by_code(station_code)+creds)
	print(base_url+get_arrivals_by_code(station_code)+creds)
	if resp.status_code == 200:
		lines = get_lines_from_json(resp.json())
		lines.append('For the status of all lines, please use url pathway /status')
	else:
		print(resp.reason)
		return jsonify(resp.reason), 400
	return jsonify(lines), 200

# This url takes in no input from the user and provides the status for each line. It uses HATEOAS principles to direct users to the stations url
# for a list of all stations associated with that line provided, and therefore affected by negative status. 
@app.route('/status/', methods=['GET'])
def get_status():
	line_status = {}
	resp = requests.get(base_url+'/line/mode/tube/status'+creds)
	print(base_url+'/line/mode/tube/status'+creds)
	if resp.status_code == 200:
		for result in resp.json():
			line_status[result.get('name','None')] = [result.get('lineStatuses','None')[0].get('statusSeverityDescription','None'), 
			'For a list of all stations in this line, please use url pathway /stations/' + fuzzy_find_line(result.get('name','None'))]
	else:
		print(resp.reason)
		return jsonify(resp.reason), 400
	return jsonify(line_status), 200

# This route takes in a line and performs fuzzy matching against the tube_lines array to select the API friendly string for querying which station
# are associated with a given tubeline. It uses HATEOAS principles to direct the user towards the arrivals page for each station given. 
@app.route('/stations/<line>', methods=['GET','POST'])
def get_stations_for_line(line):
	line_stations = {}
	line = fuzzy_find_line(line)
	resp = requests.get(base_url+'/line/'+line+'/route/sequence/outbound'+creds)
	print(base_url+'/line/'+line+'/route/sequence/outbound'+creds)
	if resp.status_code == 200:
		for result in resp.json()['stations']:
			line_stations[result.get('name','None')] = "For arrivals please use url pathway /arrivals/" + result.get('name','None').replace(" ", "").replace("UndergroundStation",'')
	else:
		print(resp.reason)
		return jsonify(resp.reason), 400
	return jsonify(line_stations), 200


# On closedown of the app the db instance is closed. 
@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()

# When running the application, it is served on port 8080, with the debug on and is served on HTTPS using a certificate and Key model. 
if __name__=="__main__":
	app.run(port=8080, debug=True, ssl_context=('cert.pem', 'key.pem'))


