#El LED de la Pico W enciende cuando está conectada
LED = machine.Pin("LED", machine.Pin.OUT)
LED.on()

from machine import Pin, PWM, I2C
from utime import sleep, sleep_ms
from ssd1306 import SSD1306_I2C
import framebuf
import time 
import ustruct
#Bibliotecas para Wifi y Telegram
import rp2
import network
import ubinascii
import urequests as requests
from secrets import *

"""          Configuración de Wifi          """
# Configurar pais para evitar posibles errores
rp2.country('MX')
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

"""           Telegram                       """
# Se cargan los datos de ssid y password desde la biblioteca secrets
ssid = secrets['ssid']
pw = secrets['password']
botToken = '6327550035:AAFem-UqKI5duAT-tYQhCNWx_16DFJBywnk'
#ID del canal de Telegram
chatId = '-1001965761639'
startupText = 'Acelerografo activado :O!'
text = 'Movimiento detectado.'

# Telegram manda un mensaje URL
sendURL = 'https://api.telegram.org/bot' + botToken + '/sendMessage'

# Manda mensaje de Telegram a un ID de usario dado
def send_message (chatId, message):
    response = requests.post(sendURL + "?chat_id=" + str(chatId) + "&text=" + message)
    # Cerrar para evitar llenar la RAM
    response.close()

# Define blinking function for onboard LED to indicate error codes    
def blink_onboard_led(num_blinks):
    for i in range(num_blinks):
        LED.on()
        time.sleep(.2)
        LED.off()
        time.sleep(.2)
        
def is_wifi_connected():
    wlan_status = wlan.status()
    if wlan_status != 3:
        return False
    else:
        return True

def connect_wifi():
    while True:
        if (is_wifi_connected()):
            blink_onboard_led(3)
            LED.on()
            status = wlan.ifconfig()
            print('ip = ' + status[0])
            send_message(chatId, startupText)
            break
        else:
            print('El WiFi esta desconectado. Intentando conectarse...')
            LED.off()
            wlan.connect(ssid, pw)
            time.sleep(3)

# Conectar al WiFi
connect_wifi()


"""          ADXL345 Configuración          """
# Constantes
ADXL345_ADDRESS = 0x53 # dirección para el acelerómtro 
ADXL345_POWER_CTL = 0x2D # direccion 'power control'
ADXL345_DATA_FORMAT = 0x31 # configuracion 'data format'
ADXL345_DATAX0 = 0x32 # direccion donde el 'eje x' data comienza
 
# Inicializa la comucicación I2C
#Se define pin 17 para scl, pin 16 para sda del acelerometro
i2c = I2C(0, sda=Pin(16), scl=Pin(17), freq=400000)
 
# Inicializa el ADXL345
def init_adxl345():
    # Se establece el bit 3 al 1 para activar el modo de medición
    i2c.writeto_mem(ADXL345_ADDRESS,
                    ADXL345_POWER_CTL,
                    bytearray([0x08]))
    # Se ajusta el formato de datos a resolución completa, +/- 16g
    i2c.writeto_mem(ADXL345_ADDRESS,
                    ADXL345_DATA_FORMAT,
                    bytearray([0x0B]))
    #Muestra un mensaje cuando el acelerómetro a inicializado
    print('ADXL345 Listo')

"""Leer los datos del acelerómetro
NOTAS:
-los valores de x,y,z se multiplican por 0.0039 para obtener los valores en 'g'
-el multiplicador puede cambiar de acuerdo a la resolución
 (checar datasheet del ADXL345)   """
def lee_data_acel():
    data = i2c.readfrom_mem(ADXL345_ADDRESS,
                            ADXL345_DATAX0, 6)
    x, y, z = ustruct.unpack('<3h', data)
    x = x*0.0039
    y = y*0.0039
    z = z*0.0039
    return x, y, z

"""Función para calibrar valores del acelerómetro.
Los valores mostrados están previamente medidos y calculados"""
def lee_ejes_calibrados():
    x, y, z = lee_data_acel()
    
    xoffset = (-0.004890439*x) + 0.01679346
    yoffset = (-0.006115634*y) + 0.01870895
    zoffset = (-0.02166251*z) + (-0.1114808)
    
    x_cal = x-xoffset
    y_cal = y-yoffset
    z_cal = z-zoffset
    
    return x_cal, y_cal, z_cal

"""----------------------------------------------------------------------------- """
"""    Configuración del OLED      """
#Se define el ancho y el largo de la pantalla
WIDTH = 128
HEIGHT = 64

#se configura el I2C de la pantalla
#i2c = I2C(1, scl = Pin(19), sda = Pin(18), freq = 200000)
oled = SSD1306_I2C(WIDTH, HEIGHT, i2c)

def Abrir_Icono(ruta_icono):
    doc = open(ruta_icono, "rb")
    doc.readline()
    xy = doc.readline()
    x = int(xy.split()[0])
    y = int(xy.split()[1])
    
    buffer = bytearray(doc.read())
    doc.close
    return framebuf.FrameBuffer(buffer, x, y, framebuf.MONO_HLSB)

"""----------------------------------------------------------------------------- """
"""     Configuración de Alarma     """
#Se asigna el Pin 15 para la bocina de alerta
bocina = PWM(Pin(15))
#Se crea un arreglo con los tonos que emite la bocina
tones = (312, 312, 312, 312, 312, 312, 312, 312, 312, 312)

# Función para reproducir un solo tono y luego parar.
#Se tiene como argumento la frecuencia (freq)
def emite_sonido(freq):
    # Se establece uns frecuencia.
    bocina.freq(freq)
    # Se establece el ciclo de trabajo (afecta el volumen)
    bocina.duty_u16(15000);
    # Espacio entre notas
    sleep_ms(1000);
    # Se apaga el sonido para dar paso a la siguiente nota
    bocina.duty_u16(0);
    # Espacio de tiempo entre tonos
    sleep_ms(100);

"""----------------------------------------------------------------------------- """
"""Promedio de los valores del ADXL345"""
def calcula_promedio():
    #Se define una variable entera "valores" para sabar el promedio de 10 valores
    valores = 10
    #se inicializan los valores para la suma acumulada de los 10 valores 
    sumax = 0.0
    sumay = 0.0
    sumaz = 0.0
    
    #Se crea un contador para generar la suma acumulativa de valores 
    for i in range(10):
        x, y, z = lee_ejes_calibrados()
        
        sumax += x
        sumay += y
        sumaz += z      
        time.sleep(0.1)

    #Se calculan los promedios para cada eje 
    promx = sumax / valores
    promy = sumay /valores
    promz = sumaz / valores
    
    return promx,promy,promz

#Se manda a inicializar el ADXL345
init_adxl345()

#Se calculan los promedios anteriores
promedioxa,promedioya,promedioza = calcula_promedio()

"""Empieza el ciclo infinito y se calculan los promedios de
10 valores leídos por el acelerómetro"""
while True:
    if (not is_wifi_connected()):
        connect_wifi()
    
    #Se calculan los promedios actuales
    promediox,promedioy,promedioz = calcula_promedio()
    #Se toman las diferencias de (promedios actuales - promedios anteriores) en cada eje
    diferenciax = promediox - promedioxa
    diferenciay = promedioy - promedioya
    diferenciaz = promedioz - promedioza
    
    """Se crea una condición para activar la alarma en base a la diferencia
    de promedios y considerando un valor absoluto """
    if abs(diferenciaz) >= 0.08 or abs(diferenciay) >=0.03 or abs(diferenciax) >=0.03:
        oled.fill(0) #Se borra toda la pantalla
        oled.text("Movimiento", 17, 16)
        oled.text("Detectado", 17, 30)
        oled.show() #muestra el texto en la pantalla
        time.sleep(2)
        send_message(chatId, text)
        #Se emite un sonido de alerta por medio de la bocina
        for tone in range(len(tones)):
            emite_sonido(tones[tone])
        
    #Se iguala el promedio anterior para irlo actualizando 
    promedioxa = promediox
    promedioya = promedioy
    promedioza = promedioz
    
    #se redondean los promedios a un decimal
    Ejex=round(promediox,2)#2
    Ejey=round(promedioy,2)#2
    Ejez=round(promedioz,2)
    
    """Se muestran los valores del acelerómetro en unidades 'g'
    #1 g = 9.81 m/s^2"""
    
    #promedios actuales redondeados a un decimal
    print('x:',Ejex,'y:',Ejey,'z:',Ejez)
    
    
    """Se muestran los valores en el OLED"""
    oled.fill(0) #Se borra toda la pantalla
    #Nota: se agregan los textos en la memoria interna del OLED
    oled.blit(Abrir_Icono("/images/ipnm.pbm"), 86, 20)
    oled.text("Sismografo",20,0)
    oled.text("x:", 1, 16) 
    oled.text(str(round(Ejex,1)), 20, 16) # Se agrega un texto; la posición en'x'; la posición en 'y'
    oled.text("y:", 1, 30)
    oled.text(str(round(Ejey,1)), 20, 30)
    oled.text("z:", 1, 46)
    oled.text(str(Ejez), 20, 46)
    oled.show() #muestra el texto en la pantalla
    #sleep_ms(3000)
    
    oled.fill(0)
    
    """Pruebas para verificar el cálculo de promedios"""
#     print("promedio anterior")
#     print('x:',promedioxa,'y:',promedioya,'z:',promedioza)
#     
#     print("promedio actual")
#     print('x:',promediox,'y:',promedioy,'z:',promedioz)
#     
#     print ("diferencia z:")
#     print(diferenciaz)
#     print ("diferencia y:")
#     print(diferenciay)
#     print ("diferencia x:")
#     print(diferenciax)

