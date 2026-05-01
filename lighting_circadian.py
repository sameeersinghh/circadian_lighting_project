import time
import requests
import csv
import board
import busio
import os  # to check if the file already exists
from adafruit_ina219 import INA219
import RPi.GPIO as GPIO

# --- 1. SYSTEM SETTINGS ---
API_KEY = "43de4d94f636061a56be3403f216b2ae"
CITY = "Mohali"  # Try any city here!
COOL_PIN = 18
WARM_PIN = 19

# --- 2. STARTING THE HARDWARE ---
print(f"Waking up the sensor and syncing to {CITY} time...")

i2c = busio.I2C(board.SCL, board.SDA)
ina219 = INA219(i2c)

GPIO.setmode(GPIO.BCM)
GPIO.setup(COOL_PIN, GPIO.OUT)
GPIO.setup(WARM_PIN, GPIO.OUT)

pwm_cool = GPIO.PWM(COOL_PIN, 1000)
pwm_warm = GPIO.PWM(WARM_PIN, 1000)
pwm_cool.start(0)
pwm_warm.start(0)

# --- 3. THE SMART LOGIC ---
def get_color_mix(hour):
    if 6 <= hour < 12:    return 0.8, 0.2  # Morning
    elif 12 <= hour < 17: return 1.0, 0.0  # Midday
    elif 17 <= hour < 21: return 0.3, 0.7  # Evening
    else:                 return 0.0, 1.0  # Night

def get_city_data():
    """Fetches weather and calculates the exact local date and time for the target city."""
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={API_KEY}"
        data = requests.get(url, timeout=5).json()
        
        weather = data['weather'][0]['main']
        timezone_offset = data['timezone'] 
        
        # Calculate the city's exact local time and date
        city_time = time.gmtime(time.time() + timezone_offset)
        city_hour = city_time.tm_hour
        city_date_str = time.strftime("%Y-%m-%d", city_time) # Extracts the Date
        city_clock_str = time.strftime("%H:%M:%S", city_time) # Extracts the Time
        
        # If the sun is out, dim the lights by 50%
        if weather == "Clear":
            power_saver = 0.5
        else:
            power_saver = 1.0 
            
        return power_saver, weather, city_hour, city_date_str, city_clock_str
        
    except Exception as e:
        print(f"API Error: {e}")
        # Fallback to local Pi time if internet breaks
        return 1.0, "Error", time.localtime().tm_hour, time.strftime("%Y-%m-%d"), time.strftime("%H:%M:%S")

# --- 4. THE MAIN LOOP ---
print("System running! Logging data...")

# Check if the file already exists before we open it
filename = 'energy_log.csv'
file_exists = os.path.isfile(filename)

# Changed 'w' to 'a' so it appends data to the bottom instead of overwriting
with open(filename, 'a', newline='') as file:
    writer = csv.writer(file)
    
    # Only write the header row if the file is brand new
    if not file_exists:
        writer.writerow(["Date", "Time", "Weather", "Cool%", "Warm%", "Power_mW"])

    try:
        while True:
            # Grab the location-aware data (now including the date)
            power_saver, weather, city_hour, city_date, clock_time = get_city_data()
            cool_ratio, warm_ratio = get_color_mix(city_hour)

            final_cool = (cool_ratio * power_saver) * 100
            final_warm = (warm_ratio * power_saver) * 100

            pwm_cool.ChangeDutyCycle(final_cool)
            pwm_warm.ChangeDutyCycle(final_warm)

            power_used = ina219.power

            # Print and save the data
            print(f"[{city_date} | {CITY}: {clock_time}] Weather: {weather} | Cool: {final_cool:^5}% | Warm: {final_warm:^5}% | Power: {power_used:.1f}mW")
            writer.writerow([city_date, clock_time, weather, final_cool, final_warm, power_used])
            file.flush() 

            time.sleep(300) 

    except KeyboardInterrupt:
        print("\nTurning off lights...")
        pwm_cool.stop()
        pwm_warm.stop()
        GPIO.cleanup()