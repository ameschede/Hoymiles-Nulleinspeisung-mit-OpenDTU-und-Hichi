#!/usr/bin/env python3
import requests, time, sys, json
from requests.auth import HTTPBasicAuth
from paho.mqtt import client as mqtt_client


# Diese Daten müssen angepasst werden:
serial = "112100000000" # Seriennummer des Hoymiles Wechselrichters
maximum_wr = 600 # Maximale Ausgangsleistung des Wechselrichters
minimum_wr = 20 # Minimale Ausgangsleistung des Wechselrichters. Bei weniger als 20 Watt kann es zu spontanen Neustarts des Wechselrichters kommen, weil er offenbar so tief limitiert nicht gut fahren kann.

dtu_ip = '192.168.0.55' # IP Adresse von OpenDTU
dtu_nutzer = 'admin' # OpenDTU Nutzername
dtu_passwort = 'openDTU42' # OpenDTU Passwort

tasmota_ip = '192.168.0.54' # IP Adresse des Tasmota-Lesekopfs
tasmota_zaehlername = '' # Falls im Skript des Lesekopfes ein Name des Stromzählers angegeben wurde, diesen hier angeben
tasmota_schluessel = 'aktuelle_wirkleistung' #Der im Skript des Lesekopfes vergebene Schlüsselname, aus dem der aktuelle Leistungssaldo des Stromzählers ausgelesen werden kann

# Zugangsdaten zum MQTT-Server für den Zendure SolarFlow
# Um die hier benötigten Zugangsdaten zu bekommen, muss einmalig wie unter https://github.com/Zendure/developer-device-data-report beschrieben ein appKey angefragt werden
mqtt_broker = 'mqtt.zen-iot.com'
mqtt_port = 1883
mqtt_topic = "66666666/E3GUng9N/state" # Das anzufragende Topic setzt sich aus dem appKey und einer Gerätekennung zusammen. Die Gerätekennung muss ggfs. durch händischen Login in den MQTT-Broker ermittelt werden.
mqtt_username = '66666666' # Username entspricht bei Zendure dem appKey
mqtt_password = '777777777777777777777777777777777' # Passwort entspricht dem secret bei Zendure
# Ende der anzupassenden Daten

grid_sum = 0
power_solar = 0
fuellstand = 0
client_id = f'python-mqtt'

FIRST_RECONNECT_DELAY = 1
RECONNECT_RATE = 2
MAX_RECONNECT_COUNT = 12
MAX_RECONNECT_DELAY = 60

def on_disconnect(client, userdata, rc):
	logging.info("MQTT-Verbindung abgebrochen, Code: %s", rc)
	reconnect_count, reconnect_delay = 0, FIRST_RECONNECT_DELAY
	while reconnect_count < MAX_RECONNECT_COUNT:
		logging.info("Neuer Verbindungsversuch in %d Sekunden...", reconnect_delay)
		time.sleep(reconnect_delay)

		try:
			client.reconnect()
			logging.info("MQTT-Verbindung wiederhergestellt")
			return
		except Exception as err:
			logging.error("%s. MQTT-Reconnect gescheitert. Neuer Versuch...", err)

		reconnect_delay *= RECONNECT_RATE
		reconnect_delay = min(reconnect_delay, MAX_RECONNECT_DELAY)
		reconnect_count += 1
	logging.info("MQTT-Reconnect %s mal gescheitert. Abbruch...", reconnect_count)
	
def connect_mqtt():
	def on_connect(client, userdata, flags, rc):
		if rc == 0:
			print("Verbunden mit MQTT-Broker")
		else:
			print("Verbindungsfehler, Code %d\n", rc)
	client = mqtt_client.Client(client_id)
	client.username_pw_set(mqtt_username, mqtt_password)
	client.on_connect = on_connect
	client.on_disconnect = on_disconnect
	client.connect(mqtt_broker, mqtt_port)
	return client

def subscribe(client: mqtt_client):
	def on_message(client, userdata, msg):
		r = json.loads(str(msg.payload.decode()))
		# prüfen ob Message relevante Daten enthielt:
		try:
			global power_solar
			power_solar = int(r['solarInputPower'])
		except:
			pass
		try:
			global fuellstand
			fuellstand = int(r['electricLevel'])
		except:
			pass
	client.subscribe(mqtt_topic)
	client.on_message = on_message	


client = connect_mqtt()
subscribe(client)
client.loop_start()


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
	
	print(f'PV-Leistung: {power_solar} W, Akku: {fuellstand} %')

	# Werte setzen
	print(f'Bezug: {round(grid_sum, 1)} W, Produktion: {round(power, 1)} W, Verbrauch: {round(grid_sum + power, 1)} W')
	if reachable:
		setpoint = grid_sum + power # Neues Limit in Watt. Alternative: altes_limit statt power. Führt aber zu Leistungsexkursionen beim Wechsel aus dem Batterieprioritätsmodus. Es gibt Bereiche der Reglerkennlinie, die der Hoymiles-Wechselrichter schlecht anfahren kann (und dann bis zu 15 W unterhalb des Nullpunkts liegt). In solchen Bereichen hat er mit altes_limit zumindest die Chance, sich iterativ dem Nullpunkt anzunähern.
		
		# in schlecht anfahrbaren Bereichen eine auf altes_limit basierende Setpoint-Findung durchführen
		if ((setpoint > 30 ) and (setpoint < 92 )):
			setpoint = grid_sum + altes_limit
			print(f'Setpoint-Anpassung schlecht anfahrbarer Bereich auf {setpoint} W')
		
		# Bei vollem Akku die Nulleinspeisung abschalten
		if ((fuellstand > 98 ) and (power_solar > (grid_sum + power))): # Hier ist als Grenzwert 98 % festgelegt, da zwischen 99 und 100 % der SolarFlow mitunter schon die PV abregelt.
			setpoint = power_solar # Durch die Verluste zwischen dem Eingang des PV-Hubs und dem Ausgang des Wechselrichters kommt es zu einem (wünschenswerten) langsamen Hochfahren der PV-Leistung
			print('Nulleinspeisung aufgrund vollem Akku deaktiviert')
			
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
	print('')
	sys.stdout.flush() # write out cached messages to stdout
	time.sleep(15) 
	# Hier muss man einen Kompromiss finden. Bei 5 Sekunden kann es dazu kommen, dass das Skript schon wieder die nächste Anpassung kommandiert, noch bevor der Wechselrichter die letzte Anpassung ausgeregelt hat. Das führt dann zu heftigem Pendeln um den Nullwert. Bei 15 Sekunden ist die Regelung meist angenehm stabil, aber es kann bei stark intermittierenden Verbrauchern (Mikrowelle in der Küche) dazu kommen, dass der Wechselrichter oft sehr heftig regelt zwischen Volllast und Teillast, was die Komponenten vermutlich stark belastet. 

client.loop_stop()
	