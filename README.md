# Nulleinspeisung f�r Hoymiles-Wechselrichter + Zendure SolarFlow mit OpenDTU & Python-Steuerung

Dies ist ein Python-Skript, das den aktuellen Hausverbrauch aus einem Tasmota-basierten Lesekopf (z.B. Hichi IR wifi) ausliest, die Nulleinspeisung berechnet und die Ausgangsleistung eines Hoymiles-Wechselrichters mit Hilfe von OpenDTU entsprechend anpasst. Somit wird kein unn�tiger Strom ins �ffentliche Netz abgegeben und ein vorhandener Akku bestm�glich genutzt. Wenn der Akku voll ist, wird die Nulleinspeisung ausgesetzt und somit die Energiewende vorangebracht.

Ich selbst nutze das Skript mit einem Zendure SolarFlow und Hoymiles HM-600. Das Skript ist teilweise auf die Bed�rfnisse dieser Komponenten parametriert. Andere Hardware verh�lt sich m�glicherweise anders und erfordert Anpassungen.

## Tipp f�r den Fehlerfall

Es kann immer mal sein, dass es in der Kette Stromz�hler - Lesekopf - Python-Server - DTU - Wechselrichter an irgendeiner Stelle zu vor�bergehenden Problemen kommt, und das Limit des Wechselrichters deshalb zeitweise nicht verstellt werden kann. Besonders �rgerlich ist das, wenn der Wechselrichter wieder hochkommt, nachdem der Akku leer war. Auf Werkseinstellungen wird der Wechselrichter dann mit Volldampf einzuspeisen versuchen und den Akku sofort wieder leer ziehen. OpenDTU bietet die M�glichkeit, ein dauerhaftes Wechselrichter-Limit zu setzen. Dieses dauerhafte Limit bleibt auch erhalten, wenn der Wechselrichter spannungslos wurde. Im laufenden Betrieb wird es dann vom tempor�ren Limit �berschrieben, aber es w�rde immer dann greifen wenn nach dem Start des Wechselrichters kein tempor�res Limit �bermittelt wird.

Dieses Skript ist ein Fork von: https://github.com/Selbstbau-PV/Selbstbau-PV-Hoymiles-nulleinspeisung-mit-OpenDTU-und-Shelly3EM