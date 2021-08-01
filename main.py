from network import WLAN
import urequests as requests # from ubidots tutorial https://help.ubidots.com/en/articles/961994-connect-any-pycom-board-to-ubidots-using-wi-fi-over-http
from machine import I2C
import adafruit_sgp30 # from https://github.com/alexmrqt/micropython-sgp30
from machine import Pin
from dht import DHT # from https://github.com/JurassicPork/DHT_PyCom
import machine
import time

#Ubidots TOKEN
TOKEN = "INSERT UBIDOTS TOKEN HERE" 

#wifi setup
wlan = WLAN(mode=WLAN.STA)
wlan.antenna(WLAN.INT_ANT)

# Wi-Fi credentials 
wlan.connect("INSERT WIFI SSI", auth=(WLAN.WPA2, "INSERT WIFI PASSWORD"), timeout=5000)

while not wlan.isconnected ():
    machine.idle()
print("Connected to Wifi\n")

# Initialize I2C bus
i2c = I2C(0, I2C.MASTER)
i2c.init(I2C.MASTER, baudrate=100000)

# Create library object on our I2C port
sgp30 = adafruit_sgp30.Adafruit_SGP30(i2c)
print("SGP30 serial #", [hex(i) for i in sgp30.serial])

# Initialize SGP-30 internal drift compensation algorithm.
sgp30.iaq_init()
# Wait 15 seconds for the SGP30 to properly initialize
print("Waiting 15 seconds for SGP30 initialization.")
time.sleep(15)

# Retrieve previously stored baselines, if any (helps the compensation algorithm).
has_baseline = False
try:
    f_co2 = open('co2eq_baseline.txt', 'r')
    f_tvoc = open('tvoc_baseline.txt', 'r')

    co2_baseline = int(f_co2.read())
    tvoc_baseline = int(f_tvoc.read())
    #Use them to calibrate the sensor
    sgp30.set_iaq_baseline(co2_baseline, tvoc_baseline)

    f_co2.close()
    f_tvoc.close()

    has_baseline = True
except:
    print('No SGP30 baselines found')

#Store the time at which last baseline has been saved
baseline_time = time.time()

#Initialize dht22
th = DHT(Pin('P23', mode=Pin.OPEN_DRAIN), 1) #1 because dht22, change to 0 if using a DHT11
print("Waiting 2 seconds for DHT22 initialization.")
time.sleep(2)

# Builds the json to send the post request to ubidots
def build_json(variable1, value1, variable2, value2, variable3, value3, variable4, value4):
    try:
        #lat = 6.217
        #lng = -75.567
        data = {variable1: {"value": value1},
                variable2: {"value": value2},
                variable3: {"value": value3},
                variable4: {"value": value4}}
        return data
    except:
        return None

# Sends the post request to ubidots using the REST API
def post_var(device, value1, value2, value3, value4):
    try:
        url = "https://industrial.api.ubidots.com/"
        url = url + "api/v1.6/devices/" + device
        headers = {"X-Auth-Token": TOKEN, "Content-Type": "application/json"}
        data = build_json("temperature", value1, "humidity", value2, "CO2", value3, "TVOC", value4)
        if data is not None:
            print(data)
            req = requests.post(url=url, headers=headers, json=data)
            return req.json()
        else:
            pass
    except:
        pass

while True:
#gets the temperature and humidity measurements from dht22
    result = th.read()
    while not result.is_valid():
        time.sleep(.5)
        result = th.read()
    print('Temp.:', result.temperature)
    print('RH:', result.humidity)

#sends the humidity and temperature from DHT22 to SGP30 for a more accurate output
    sgp30.set_iaq_rel_humidity(result.humidity, result.temperature)

#gets the co2 and tvoc measurements
    co2_eq, tvoc = sgp30.iaq_measure()
    print('co2eq = ' + str(co2_eq) + ' ppm \t tvoc = ' + str(tvoc) + ' ppb')

#sends the data to Ubidots
    temperature = result.temperature
    humidity = result.humidity
    post_var("pycom", temperature, humidity, co2_eq, tvoc)

#sends the data to pybytes
    pybytes.send_signal(1,result.temperature)
    pybytes.send_signal(2,result.humidity)
    pybytes.send_signal(3,co2_eq)
    pybytes.send_signal(4,tvoc)

#writes baselines after 12 hours (first time) or 1 hour
    if (has_baseline and (time.time() - baseline_time >= 3600)) \
            or ((not has_baseline) and (time.time() - baseline_time >= 43200)):

        print('Saving baseline')
        baseline_time = time.time()

        try:
            f_co2 = open('co2eq_baseline.txt', 'w')
            f_tvoc = open('tvoc_baseline.txt', 'w')

            bl_co2, bl_tvoc = sgp30.get_iaq_baseline()
            f_co2.write(str(bl_co2))
            f_tvoc.write(str(bl_tvoc))

            f_co2.close()
            f_tvoc.close()

            has_baseline = True
        except:
            print('Impossible to write SGP30 baselines!')

            # Measures every 5 minutes (300 seconds)
    time.sleep(300)
