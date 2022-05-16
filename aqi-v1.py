#!/usr/bin/env python3

"""
That script will sent particular matter (PM2.5 and PM10) and CO2 over LoRaWAN or WiFi
Meaures are log into a json file.

Mote: MQTT part has never bee tested yet

Important:
To schedule the script, use sudo crontab -e. sudo is mendatory
expl: #*/2 * * * * cd /opt/ecoaqi/ && ./aqi-v1.py >/var/log/aqi-v1.log 2>&1
"""

import sys
import subprocess
import time, json
import smbus
from digitalio import DigitalInOut, Direction, Pull
from datetime import datetime
#import paho.mqtt.publish as publish
import psutil

# MQTT
#import subprocess

#config
stabilisation_delay = 10 #delay to have the sds011 stabilized
pm_n_measures = 5 # Number of measures for sds011 sebsors
LEDs = True
OLED = True
LORA = True
if(LORA):
    C_URL = False
else:
    C_URL = True
Z2G = False
GPS = False
CO2 = False

if CO2:
    import mh_z19

import ttnkeys
#dev_id = ttnkeys.dev_id

if C_URL:
    import  pycurl
    from io import StringIO

# SDS011
from sds011 import SDS011
import aqi

# zerotogo board
if Z2G:
    i2c_ch = 1
    bus = smbus.SMBus(i2c_ch)
    addr_z2g = 0x24

# OLED LCD
if OLED:
    import adafruit_ssd1306

import board, busio
# Create the I2C interface.
if OLED:
    i2c = busio.I2C(board.SCL, board.SDA)


#batteries
bat1 = 0
bat2 = 0
bat3 = 0

# 128x64 OLED Display
if OLED:
    display = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c)

    # Clear the display.
    display.fill(0)
    display.show()
    width = display.width
    height = display.height
    display.poweroff()


# LEDs
d18Output = DigitalInOut(board.D18)
d18Output.direction = Direction.OUTPUT
d18Output.value = False

d19Output = DigitalInOut(board.D19)
d19Output.direction = Direction.OUTPUT
d19Output.value = False

d20Output = DigitalInOut(board.D20)
d20Output.direction = Direction.OUTPUT
d20Output.value = False


# GPS
import pynmea2, serial
if GPS:
    gps_power = DigitalInOut(board.D13) # Check pin
    gps_power.direction = Direction.OUTPUT
    gps_power.value = False
lat=0
lon=0

# JSON
JSON_FILE = '/var/www/html/aqi.json'

# LOG
LOG_FILE = '/opt/ecoaqi/log/log.txt'

# MQTT
MQTT_HOST = ''
MQTT_TOPIC = '/weather/particulatematter'


# TinyLora
if LORA:
    from adafruit_tinylora.adafruit_tinylora import TTN, TinyLoRa

    # TinyLoRa Configuration
    spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
    cs = DigitalInOut(board.CE1)
    irq = DigitalInOut(board.D5)
    rst = DigitalInOut(board.D25)

    # TTN Device Address, 4 Bytes, MSB
    devaddr = bytearray(ttnkeys.devaddr)
    # TTN Network Key, 16 Bytes, MSB
    nwkey = bytearray(ttnkeys.nwkey)
    # TTN Application Key, 16 Bytess, MSB
    app = bytearray(ttnkeys.app)

    # Initialize ThingsNetwork configuration
    ttn_config = TTN(devaddr, nwkey, app, country='EU')
    lora = TinyLoRa(spi, cs, irq, rst, ttn_config)
    # 2b array to store sensor data
    data_pkt = bytearray(2)
    # time to delay periodic packet sends (in seconds)
    data_pkt_delay = 5.0

#sds011
sensor = SDS011("/dev/ttyUSB0", use_query_mode=True)


#print("SDS011 sensor info:")
#print(sensor)
#print(sensor.deviceid)
#print("Device firmware: ", sensor.firmware)

"""
print("Device ID: ", sensor.device_id)
print("Device firmware: ", sensor.firmware)
print("Current device cycle (0 is permanent on): ", sensor.dutycycle)
print(sensor.workstate)
print(sensor.reportmode)
"""

def get_co2():
    print('[INFO: Getting CO2]')
    #print(mh_z19.read_all())
    co_2 = mh_z19.read()
    print("co2: " + str(co_2['co2']))
    return co_2['co2']

def get_pm_25_10(n):
        print('[INFO] Waking up SDS011')

        if OLED:
            display.text('Waking up SDS011', 0, 18, 1)

        sensor.sleep(sleep=False)
        pmt_2_5 = 0
        pmt_10 = 0
        #stabilisation_delay = 3

        if OLED:
            display.text('Wait ' + str(stabilisation_delay) + 's to stabilize', 0, 28, 1)
            display.show()

        print('[INFO] Wait ' + str(stabilisation_delay) + 's to stabilize ...')
        time.sleep(stabilisation_delay)
        print('[INFO] Measuring ' + str(n) + ' times')

        if OLED:
            display.text('Mesuring ' + str(n) + 'times', 0, 38, 1)
            display.show()

        for i in range (n):
            x = sensor.query()
            pmt_2_5 = pmt_2_5 + x[0]
            pmt_10 = pmt_10 + x[1]
            print(str(i) + '. pm2.5: ' + str(pmt_2_5) + ' µg/m3  pm10:' + str(pmt_10) + ' µg/m3')
            if OLED:
                display.text('|', i, 48, 1)
                display.show()
            time.sleep(1)

        pmt_2_5 = round(pmt_2_5/n, 1)
        pmt_10 = round(pmt_10/n, 1)

        print('[INFO] SDS011 go to sleep')
        sensor.sleep(sleep=True)
        time.sleep(2)
        return pmt_2_5, pmt_10

def conv_aqi(pmt_2_5, pmt_10):
    aqi_2_5 = aqi.to_iaqi(aqi.POLLUTANT_PM25, str(pmt_2_5))
    aqi_10 = aqi.to_iaqi(aqi.POLLUTANT_PM10, str(pmt_10))
    return aqi_2_5, aqi_10

"""
# NOT USED
def save_excel():
    with open("/YOUR PATH/air_quality.csv", "a") as log:
        dt = datetime.now()
        log.write("{},{},{},{},{}\n".format(dt, pmt_2_5, aqi_2_5, pmt_10, aqi_10))
    log.close()
"""

def save_log(type,txt):
    with open("/opt/ecoaqi/log/log.txt", "a+") as log:
        dt = datetime.now()
        log.write("{},{},{}\n".format(dt, type, txt))
    log.close()

# NOT USED
def send_pi_data(data):
    # Encode float as int
    print('data',data)
    data = int(data)
    #data.encode(ascii)
    print('data len',data)
    # Encode payload as bytes
    data_pkt[0] = (data >> 8) & 0xff
    data_pkt[1] = data & 0xff
    # Send data packet
    lora.send_data(data_pkt, len(data_pkt), lora.frame_counter)
    lora.frame_counter += 1
    #if OLED:
        #display.text('Sent Data to TTN!',0 , 50, 1)
        #display.show()
    time.sleep(0.5)

def send_curl(data):
    if C_URL:
        print('[INFO] Sending data with PycURL')
        save_log("INFO","Sending data with PycURL")
        # https://stackoverflow.com/questions/31826814/curl-post-request-into-pycurl-code/31827961#31827961
        try:
            c = pycurl.Curl()
            c.setopt(c.URL, 'http://demo.website.com/path/save_aqi_n.php')
            c.setopt(c.HTTPHEADER, ['Accept: application/json','Content-Type: application/json'])
            c.setopt(c.POST, 1)

            # If you want to set a total timeout, say, 3 seconds
            #c.setopt(c.TIMEOUT_MS, 3000)
            ## depending on whether you want to print details on stdout, uncomment either
            #c.setopt(c.VERBOSE, 1) # to print entire request flow
            ## or
            c.setopt(c.WRITEFUNCTION, lambda x: None) # to keep stdout clean

            # preparing body the way pycurl.READDATA wants it
            # NOTE: you may reuse curl object setup at this point
            #  if sending POST repeatedly to the url. It will reuse
            #  the connection.
            #body_as_dict = {"dev_id": "12", "path": "def", "target": "ghi"}
            body_as_dict = data
            body_as_json_string = json.dumps(body_as_dict) # dict to json
            #print(body_as_json_string)
            body_as_file_object = StringIO(body_as_json_string)
            #print(body_as_file_object)
            # prepare and send. See also: pycurl.READFUNCTION to pass function instead
            c.setopt(c.READDATA, body_as_file_object) 
            c.setopt(c.POSTFIELDSIZE, len(body_as_json_string))
            c.perform()

            # you may want to check HTTP response code, e.g.
            status_code = c.getinfo(pycurl.RESPONSE_CODE)
            if status_code != 200:
                print("Server returned HTTP status code {}".format(status_code))
                save_log("ERROR","Server returned HTTP status code {}".format(status_cocde))
                #print('Device error: {}'.format(e))

            # don't forget to release connection when finished
            c.close()
            return 1

        except Exception as e:
            c.close()
            save_log("ERROR","c.setopt error %s" % e)
            return -1

    else:
        return 0

# Sending with LoRa
def send_data(data):
    if LORA:
        print('[INFO] Sending data with LoRa')
        data_pkt = bytearray(data, 'utf-8')
        try:
             lora.send_data(data_pkt, len(data_pkt),lora.frame_counter)
             lora.frame_counter += 1
        except:
             print("Something went wrong")

        time.sleep(0.5)
        return 1
    else:
        return 0

def pub_mqtt(jsonrow):
    cmd = ['mosquitto_pub', '-h', MQTT_HOST, '-t', MQTT_TOPIC, '-s']
    print('Publishing using:', cmd)
    with subprocess.Popen(cmd, shell=False, bufsize=0, stdin=subprocess.PIPE).stdin as f:
        json.dump(jsonrow, f)


# NOT USED
def parseGPS(data):
    print ("raw:", data) #prints raw data
    print(data[0:6])
    sentence = data[0:6]
    if sentence.decode('UTF-8') == "$GPRMC":
        print('2')
        spdata = data.decode('UTF-8')
        sdata = spdata.split(",")
        if sdata[2] == 'V':
            print ('no satellite data available')
            return
        print('---Parsing GPRMC---')
        time = sdata[1][0:2] + ":" + sdata[1][2:4] + ":" + sdata[1][4:6]
        lat = decode(sdata[3]) #latitude
        dirLat = sdata[4]      #latitude direction N/S
        lon = decode(sdata[5]) #longitute
        dirLon = sdata[6]      #longitude direction E/W
        speed = sdata[7]       #Speed in knots
        trCourse = sdata[8]    #True course
        date = sdata[9][0:2] + "/" + sdata[9][2:4] + "/" + sdata[9][4:6]#date

        print("time : %s, latitude : %s(%s), longitude : %s(%s), speed : %s, True Course : %s, Date : %s" %  (time,lat,dirLat,lon,dirLon,speed,trCourse,date))
        return lat,lon,date

    #if str.find('GGA') > 0:
        #msg = pynmea2.parse(str)
        #msg.latitude
        #print "Timestamp: %s -- Lat: %s %s -- Lon: %s %s -- Altitude: %s %s -- Satellites: %s" % (msg.timestamp,msg.lat,msg.lat_dir,msg.lon,msg.lon_dir,msg.altitude,msg.altitude_units,msg.num_sats)

# NOT USED
def decode(coord):
    #Converts DDDMM.MMMMM > DD deg MM.MMMMM min
    x = coord.split(".")
    head = x[0]
    tail = x[1]
    deg = head[0:-2]
    min = head[-2:]
    return deg + " deg " + min + "." + tail + " min"

# that function only works for the  zero2go board
def get_batt_z2g():
    if Z2G:
        # Channel-A (input 1)
        val1 = bus.read_i2c_block_data(addr_z2g, 1)
        val2 = bus.read_i2c_block_data(addr_z2g, 2)
        ba1 = val1[0] + val2[0]/100

        # Channel-B (input 2)
        val3 = bus.read_i2c_block_data(addr_z2g, 3)
        val4 = bus.read_i2c_block_data(addr_z2g, 4)
        ba2 = val3[0] + val4[0]/100

        # Channel-B (input 3)
        val5 = bus.read_i2c_block_data(addr_z2g, 5)
        val6 = bus.read_i2c_block_data(addr_z2g, 6)
        ba3 = val5[0] + val6[0]/100

        return ba1, ba2, ba3
    else:
        print('[INFO] zero2go not active')
        return 0,0,0

def get_gps():
    print('[INFO] Getting GPS')

    try:
        with serial.Serial('/dev/ttyAMA0', baudrate=9600, timeout=1) as ser:
            gpsOk = False

            #print('[INFO] Warmup GPS')
            for i in range(100):
                warm = ser.readline()
                print(warm)

            # read 20 lines from the serial output
            for i in range(20):
                #print('Read ' + str(i))
                try:
                    data = ser.readline()
                    sdata=data[0:6].decode('UTF-8')
                    if sdata == "$GPRMC":
                        nmea  = pynmea2.parse(data.decode('UTF-8'),check=True)
                        gpsOk = True
                        break
                except serial.SerialException as e:
                    print('Device error: {}'.format(e))
                    break
                except pynmea2.ParseError as e:
                    print('Parse error: {}'.format(e))
                    continue

            # NOT USED
            # parseGPS(data)

    except Exception as e:
        print('Error reading serial port:' , e)

   # Power off GPS
    print('[INFO] Turn OFF GPS')
    gps_power.value = False

    if gpsOk:
        print('[INFO] OK')
        return nmea.latitude, nmea.longitude
    else:
        print('[ERROR] Cannot find GPRMC sentences')
        return 0.0,0.0

"""
# NOT USED
channelID = "YOUR CHANNEL ID"
apiKey = "YOUR WRITE KEY"
topic = "channels/" + channelID + "/publish/" + apiKey
mqttHost = "mqtt.thingspeak.com"

tTransport = "tcp"
tPort = 1883
tTLS = None
"""

if True:
    if OLED:
        display.poweron()
        display.fill(0)
        display.show()
        display.text('ECO-SENSORS.CH', 0, 0, 1)
        display.text('Smart Air Quality', 0, 8, 1)
        display.show()

    """
    # read the raspberry pi cpu load
    cmd = "top -bn1 | grep load | awk '{printf \"%.1f\", $(NF-2)}'"
    CPU = subprocess.check_output(cmd, shell = True )
    CPU = float(CPU)
    print('[INFO] CPU load %' + str(CPU))
    """

    d18Output.value = 1
    d19Output.value = 1
    d20Output.value = 1

    # GPS
    if GPS:
        print('[INFO] Turn ON GPS' )
        gps_power.value = True
        #lat, lon = get_gps()
        #print('lat/lon:' + str(lat) + ' ' + str(lon))
        #lat=46.1234
        #lon=6.1234


    # Get batteries level with zero2go board
    if Z2G:
        print('[INFO] get battery levels')
        bat1, bat2, bat3 = get_batt_z2g()
        print('Bat1:', bat1)
        print('Bat2:', bat2)
        print('Bat3:', bat3)


    # get Co2 (MH-Z19
    co2=0
    if CO2:
        co2 = get_co2()

    # get SDS011 measures
    pmt_2_5, pmt_10 = get_pm_25_10(pm_n_measures)
    aqi_2_5, aqi_10 = conv_aqi(pmt_2_5, pmt_10)

    print(' ')
    print('---------------------------------------')
    if CO2:
        print(time.strftime("%Y-%m-%d (%H:%M:%S)"), end='')
        print(f"    CO2: {co2} ppm")
    print(time.strftime("%Y-%m-%d (%H:%M:%S)"), end='')
    print(f"    PM2.5: {pmt_2_5} µg/m3    ", end='')
    print(f"PM10: {pmt_10} µg/m3")
    print(time.strftime("%Y-%m-%d (%H:%M:%S)"), end='')
    print(f"    AQI (PMT2.5): {aqi_2_5}    ", end='')
    print(f"AQI(PMT10): {aqi_10}")

    if GPS:
        print('[INFO] Get GPS')
        lat, lon = get_gps()
        print('lat/lon:' + str(lat) + ' ' + str(lon))

    # a => pm2.5
    # b => pm10
    # c => aqi2.5
    # d => aqi10
    # e => lat
    # f => lon
    # g => time
    # h => bat1
    # i => bat2
    # j => bat3

    d18Output.value = 0

    # get date and time
    tnow = datetime.now()
    timestamp_now = datetime.timestamp(tnow)

    payload = 'a' + str(int(pmt_2_5 * 100)) + 'b' + str(int(pmt_10 * 100)) + 'c' + str(int(aqi_2_5 * 100)) + 'd' + str(int(aqi_10 * 100)) + 'e' + str(int(lat * 10000)) + 'f' + str(int(lon * 10000)) + 'g' + str(timestamp_now) + 'h' + str(int(bat1 * 100)) + 'i' + str(int(bat2 * 100)) + 'j' + str(int(bat3 * 100)) + 'k' + str(co2)

    print('[DEBUG] payload:' + payload)
    print(' ')

    if OLED:
        display.fill(0)
        display.show()
        display.text('AIR QUALITY', 0, 0, 1)
        display.text('PM2.5 :' + str(pmt_2_5) + 'µg/m3', 0, 8, 1)
        display.text('PM10  :' + str(pmt_10) + 'µg/m3', 0, 18, 1)
        display.text('AQI2.5:' + str(aqi_2_5) + 'ppm', 0, 28, 1)
        display.text('AQI10 :' + str(aqi_10) + 'ppm', 0, 38,1)
        if CO2:
            display.text('CO2 :' + str(co2) + '', 0, 48, 1)

        display.show()
    #print(aqi_2_5)
    #print(aqi_10))
    #tPayload = "field1=" + str(pmt_2_5)+ "&field2=" + str(aqi_2_5)+ "&field3=" + str(pmt_10)+ "&field4=" + str(aqi_10)

    # open stored data
    try:
        with open(JSON_FILE) as json_data:
            data = json.load(json_data)
    except IOError as e:
       data = []
       print('except')

    # check if length is more than 100 and delete first element
    if len(data) > 100:
        data.pop(0)

    # Build payload
    #payload_curl = {"dev_id":"12","p1":"1","p2":"2"}
    #payload_curl1 = {}
    #payload_curl1["app_id"] = "aqi-sds011"
    #payload_curl1["dev_id"] = ttnkeys.dev_id
    #payload_curl1["p1"] = int(pmt_2_5 * 100)   # p1 (pm2.5)
    #payload_curl1["p2"] = int(pmt_10 * 100)    # p2 (pm10)
    #payload_curl1["a1"] = int(aqi_2_5 * 100)   # a1 (aqi2.5)
    #payload_curl1["a2"] = int(aqi_10 * 100)    # a2 (aqi10)
    #payload_curl1["la"] = int(lat * 10000)     # la (lat)
    #payload_curl1["lo"] = int(lon * 10000)     # lo (lon)
    #payload_curl1["da"] = str(timestamp_now)   # da (timestamp)
    #payload_curl1["b1"] = int(bat1*100)                # b1 (input 1)
    #payload_curl1["b2"] = int(bat2*100)                # b2 (input 2)
    #payload_curl1["b3"] = int(bat3*100)                # b3 (inout 2)
    #payload_curl1["co"] = co2*100              # co (CO2)

    #print(payload_curl1)


    # append new values
    # "metadata":"time" must not be "metadata":"ti" as we send it to LoRa. jsonrow is used while the data is sent over WiFi (and not LoRa) amd ,ust be 
    #time instead of ti to match to the format receive from TTN in the PHP file 
    jsoncurl = {'dev_id': ttnkeys.dev_id,'payload_fields':{'p1': pmt_2_5*100, 'p2': pmt_10*100, 'a1': str(aqi_2_5*100), 'a2': str(aqi_10*100), 'co': str(co2*100) ,'la': lat*10000, 'lo': lon*10000, 'b1': bat1*100, 'b2': bat2*100, 'b3': bat3*100},'metadata':{ 'time': timestamp_now}}
    jsonrow = {'dev_id': ttnkeys.dev_id,'payload_fields':{'p1': pmt_2_5, 'p2': pmt_10, 'a1': str(aqi_2_5), 'a2': str(aqi_10), 'co': str(co2) ,'la': lat, 'lo': lon, 'b1': bat1, 'b2': bat2, 'b3': bat3},'metadata':{ 'time': timestamp_now}}
    data.append(jsonrow)

    print(jsonrow)
    print(jsoncurl)
    # save it
    with open(JSON_FILE, 'w') as outfile:
        json.dump(data, outfile)

    #if MQTT_HOST != '':
    #    pub_mqtt(jsonrow)

    d19Output.value = 0

    # Sent to TTN or PycURL

    if LORA:
        send_data(payload)
        print('[INFO] Data sent to TTN')
    elif C_URL:
        r = send_curl(jsoncurl)
        if r ==1:
            print('[INFO] Data sent with PycURL')
        elif r == 0:
            print ('[INFO] CURL inactive')
        elif r == -1:
            print('[ERROR] c.setoption ERROR. Check PycURL')
        else:
            print('[WARMING] send_curl() returned %s. That s not normal' % r)
    else:
        print('[WARNING] No data sent. LORA & C_URL inactive')

        #print ("[ERROR] Failure in sending data")
        #if OLED:
        #    display.text('[ERROR] Failure in sending data',0,55,1)
        #    display.show()
        #time.sleep(1)

    #sl=3600
    #sl=1800
    sl=120
    print('[INFO] Sleep for ' + str(sl)  + ' sec')
    print(' ')

    d20Output.value = 0
    time.sleep(10)

    # Turn off the OLD LCD
    if OLED:
        display.poweroff()

sys.exit('Exit the script and wait for the next cron')

#    time.sleep(sl-10)

