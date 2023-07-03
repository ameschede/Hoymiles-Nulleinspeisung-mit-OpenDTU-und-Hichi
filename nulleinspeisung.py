#!/usr/bin/env python3
import requests, time, sys
from requests.auth import HTTPBasicAuth


# Diese Daten müssen angepasst werden:
serial = "112100000000" # Seriennummer des Hoymiles Wechselrichters
maximum_wr = 600 # Maximale Ausgabe des Wechselrichters
minimum_wr = 20 # Minimale Ausgabe des Wechselrichters

dtu_ip = '192.168.0.55' # IP Adresse von OpenDTU
dtu_nutzer = 'admin' # OpenDTU Nutzername
dtu_passwort = 'openDTU42' # OpenDTU Passwort

tasmota_ip = '192.168.0.54' # IP Adresse des Tasmota-Lesekopfs
tasmota_zaehlername = '' # Falls im Skript des Lesekopfes ein Name des Stromzählers angegeben wurde, diesen hier angeben
tasmota_schluessel = 'aktuelle_wirkleistung' #Der im Skript des Lesekopfes vergebene Schlüsselname, aus dem der aktuelle Leistungssaldo des Stromzählers ausgelesen werden kann

grid_sum = 0

while True:
	try:
		# Nimmt Daten von der openDTU Rest-API und übersetzt sie in ein json-Format
		r = requests.get(url = f'http://{dtu_ip}/api/livedata/status/inverters' ).json()

		# Selektiert spezifische Daten aus der json response
		reachable   = r['inverters'][0]['reachable'] # Ist DTU erreichbar?
		producing   = int(r['inverters'][0]['producing']) # Produziert der Wechselrichter etwas?
		altes_limit = int(r['inverters'][0]['limit_absolute']) # Altes Limit
		power_dc    = r['inverters'][0]['AC']['0']['Power DC']['v']  # Lieferung DC vom Panel
		power       = r['inverters'][0]['AC']['0']['Power']['v'] # Abgabe BKW AC in Watt
	except:
		print('Fehler beim Abrufen der Daten von openDTU')
	try:
		# Nimmt Daten vom Tasmota-Lesekopf und übersetzt sie in ein json-Format
		r = requests.get(url = f'http://{tasmota_ip}/cm?cmnd=status%2010' ).json()
		grid_sum = int(r['StatusSNS'][tasmota_zaehlername][tasmota_schluessel])
	except:
		print('Fehler beim Abrufen der Daten vom Lesekopf')

	# Werte setzen
	print(f'\nBezug: {round(grid_sum, 1)} W, Produktion: {round(power, 1)} W, Verbrauch: {round(grid_sum + power, 1)} W')
	if reachable:
		setpoint = grid_sum + power # Neues Limit in Watt. Alternative: altes_limit statt power. Führt aber zu Leistungsexkursionen beim Wechsel aus dem Batterieprioritätsmodus. Es gibt Bereiche der Reglerkennlinie, die der Hoymiles-Wechselrichter schlecht anfahren kann (und dann bis zu 15 W unterhalb des Nullpunkts liegt). In solchen Bereichen hat er mit altes_limit zumindest die Chance, sich iterativ dem Nullpunkt anzunähern.
		
		#in schlecht anfahrbaren Bereichen eine auf altes_limit basierende Setpoint-Findung durchführen
		if ((setpoint > 30 ) and (setpoint < 92 )):
			setpoint = grid_sum + altes_limit
			print(f'Setpoint-Anpassung schlecht anfahrbarer Bereich auf {setpoint} W')
			

		# Fange oberes Limit ab
		if setpoint > maximum_wr:
			setpoint = maximum_wr
			print(f'Setpoint auf Maximum: {maximum_wr} W')
        # Fange unteres Limit ab
		elif setpoint < minimum_wr:
			setpoint = minimum_wr
			print(f'Setpoint auf Minimum: {minimum_wr} W')
		else:
			print(f'Setpoint berechnet: {round(grid_sum, 1)} W + {round(power, 1)} W  = {round(setpoint, 1)} W')

		if (setpoint > (altes_limit + 5)) or (setpoint < (altes_limit - 5)): #Limitänderungen von weniger als 5 Watt werden nicht an den Wechselrichter kommandiert
			print(f'Setze Inverterlimit von {round(altes_limit, 1)} W auf {round(setpoint, 1)} W... ', end='')
			# Neues Limit setzen
			try:
				r = requests.post(
					url = f'http://{dtu_ip}/api/limit/config',
					data = f'data={{"serial":"{serial}", "limit_type":0, "limit_value":{setpoint}}}',
					auth = HTTPBasicAuth(dtu_nutzer, dtu_passwort),
					headers = {'Content-Type': 'application/x-www-form-urlencoded'}
				)
				print(f'Konfiguration gesendet ({r.json()["type"]})')
			except:
				print('Fehler beim Senden der Konfiguration')

	sys.stdout.flush() # write out cached messages to stdout
	time.sleep(5) # Längere Wartezeiten haben sich nicht bewährt - sie führen z.B. beim Betrieb einer Mikrowelle in der Küche dazu, dass der Wechselrichter oft sehr heftig regelt zwischen Volllast und Teillast, was die Komponenten vermutlich stark belastet.
	