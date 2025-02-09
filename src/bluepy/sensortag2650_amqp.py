from btle import UUID, Peripheral, DefaultDelegate
from datetime import datetime
import struct
import math
import time
import pika

def tup2float(tup):
    return float('.'.join(str(x) for x in tup))
    
def _TI_UUID(val):
    return UUID("%08X-0451-4000-b000-000000000000" % (0xF0000000+val))
    
# Add some ampq commands to refactor
def addAndBind(channel, queue, exchange, routing_key=None):
    if routing_key is None:
        routing_key = queue
    channel.queue_declare(queue=queue)
    channel.queue_bind(queue=queue, exchange=exchange, routing_key=routing_key)
    print 'Added ' + queue + ' on exchange ' + exchange + ' with routing key ' + routing_key
    
    
class SensorBase:
    # Derived classes should set: svcUUID, ctrlUUID, dataUUID
    sensorOn  = struct.pack("B", 0x01)
    sensorOff = struct.pack("B", 0x00)
    sensorbarcal =  struct.pack("B", 0x02)
    sensormag = struct.pack("H", 0x0007)

    def __init__(self, periph):
        self.periph = periph
        self.service = None
        self.ctrl = None
        self.data = None

    def enable(self,sensorup):
        if self.service is None:
            self.service = self.periph.getServiceByUUID(self.svcUUID)
        if self.ctrl is None:
            self.ctrl = self.service.getCharacteristics(self.ctrlUUID) [0]
        if self.data is None:
            self.data = self.service.getCharacteristics(self.dataUUID) [0]
        if self.sensorOn is not None:
            self.sensorOn = sensorup
            self.ctrl.write(self.sensorOn,withResponse=True)

    def read(self):
        return self.data.read()

    def disable(self):
        if self.ctrl is not None:
            self.ctrl.write(self.sensorOff)



    # Derived class should implement _formatData()

def calcPoly(coeffs, x):
    return coeffs[0] + (coeffs[1]*x) + (coeffs[2]*x*x)

class IRTemperatureSensor(SensorBase):
    svcUUID  = _TI_UUID(0xAA00)
    dataUUID = _TI_UUID(0xAA01)
    ctrlUUID = _TI_UUID(0xAA02)

    zeroC = 273.15 # Kelvin
    tRef  = 298.15
    Apoly = [1.0,      1.75e-3, -1.678e-5]
    Bpoly = [-2.94e-5, -5.7e-7,  4.63e-9]
    Cpoly = [0.0,      1.0,      13.4]

    def __init__(self, periph):
        SensorBase.__init__(self, periph)
        self.S0 = 6.4e-14

    def read(self):
        '''Returns (ambient_temp, target_temp) in degC'''

        # See http://processors.wiki.ti.com/index.php/SensorTag_User_Guide#IR_Temperature_Sensor
        (rawVobj, rawTamb) = struct.unpack('<hh', self.data.read())
        tAmb = rawTamb / 128.0
        Vobj = rawVobj / 128.0
        return (tAmb, Vobj)
          
        # old sensor tag math for Obj temp
        '''Vobj = 1.5625e-7 * rawVobj        
        tDie = tAmb + self.zeroC
        S   = self.S0 * calcPoly(self.Apoly, tDie-self.tRef)
        Vos = calcPoly(self.Bpoly, tDie-self.tRef)
        fObj = calcPoly(self.Cpoly, Vobj-Vos)
        tObj = math.pow( math.pow(tDie,4.0) + (fObj/S), 0.25 )
        return (tAmb, tObj - self.zeroC)'''



class AccelerometerSensor(SensorBase):
    svcUUID  = _TI_UUID(0xAA80)
    dataUUID = _TI_UUID(0xAA81)
    ctrlUUID = _TI_UUID(0xAA82)
    

    def __init__(self, periph):
        SensorBase.__init__(self, periph)

    def read(self):
        '''Returns (x_accel, y_accel, z_accel) in units of g'''
        scale = float(32768 / 2)
        #scale = float(4096)
        (x,y,z,a,b,c,d,e,f) = struct.unpack('<hhhhhhhhh', self.data.read())
        return (a/scale,b/scale,c/scale)
 


class HumiditySensor(SensorBase):
    svcUUID  = _TI_UUID(0xAA20)
    dataUUID = _TI_UUID(0xAA21)
    ctrlUUID = _TI_UUID(0xAA22)

    def __init__(self, periph):
        SensorBase.__init__(self, periph)

    def read(self):
        '''Returns (ambient_temp, rel_humidity)'''
        (rawT, rawH) = struct.unpack('<HH', self.data.read())
        temp = -46.85 + 175.72 * (rawT / 65536.0)
        RH = -6.0 + 125.0 * ((rawH & 0xFFFC)/65536.0)
        return (temp, RH)


class LuxometerSensor(SensorBase):
    svcUUID  = _TI_UUID(0xAA70)
    dataUUID = _TI_UUID(0xAA71)
    ctrlUUID = _TI_UUID(0xAA72)    

    def __init__(self, periph):
        SensorBase.__init__(self, periph)

    def read(self):
        '''Returns (lux)'''
        (rawL) = struct.unpack('<H', self.data.read())
        RL = tup2float(rawL) / 100.0
        return (RL)
        

class MagnetometerSensor(SensorBase):
    svcUUID  = _TI_UUID(0xAA80)
    dataUUID = _TI_UUID(0xAA81)
    ctrlUUID = _TI_UUID(0xAA82)

    def read(self):
        '''Returns (x, y, z) in uT units'''
        scale = float(32760 / 4912)
        (x,y,z,a,b,c,d,e,f) = struct.unpack('<hhhhhhhhh', self.data.read())
        return (d/scale,e/scale,f/scale)


class BarometerSensor(SensorBase):
    svcUUID  = _TI_UUID(0xAA40)
    dataUUID = _TI_UUID(0xAA41)
    ctrlUUID = _TI_UUID(0xAA42)
    calUUID  = _TI_UUID(0xAA42)
    #sensorOn = None

    def __init__(self, periph):
       SensorBase.__init__(self, periph)


    def read(self):
        '''Returns (ambient_temp, pressure_millibars)'''
        (rawT,rawP) = struct.unpack('<hI',self.data.read())
        temp = (rawT) / (100.0)
        pres = (rawP) / (100.0 * float(1<<8))
        return (temp,pres)


class GyroscopeSensor(SensorBase):
    svcUUID  = _TI_UUID(0xAA80)
    dataUUID = _TI_UUID(0xAA81)
    ctrlUUID = _TI_UUID(0xAA82)
    '''sensorOn = struct.pack("B",0x07)'''
    #sensorOn = None
    # sensibilidad = 250 dps
    # error de sensibilidad = 1/131 = 0.0076336
    # DT = loop period 
    def __init__(self, periph):
       SensorBase.__init__(self, periph)

    def read(self):
        '''Returns (x,y,z) rate in deg/sec'''
        scale = float(32768/250)
        gain = float(0.0076336)
        #DT = 0.9
        #scale = float(65536/500)
        #(x,y,z,a,b,c,d,e,f) = struct.unpack('<hhhhhhhhh', self.data.read())
        (x,y,z,a,b,c,d,e,f) = struct.unpack('<hhhhhhhhh', self.data.read())
        return(x,y,z)
      

class KeypressSensor(SensorBase):
    svcUUID = UUID(0xFFE0)
    dataUUID = UUID(0xFFE1)

    def __init__(self, periph):
        SensorBase.__init__(self, periph)
 
    def enable(self):
        self.periph.writeCharacteristic(0x60, struct.pack('<bb', 0x01, 0x00))

    def disable(self):
        self.periph.writeCharacteristic(0x60, struct.pack('<bb', 0x00, 0x00))


class SensorTag(Peripheral):
    def __init__(self,addr):
        Peripheral.__init__(self,addr)
        # self.discoverServices()
        self.IRtemperature = IRTemperatureSensor(self)
        self.accelerometer = AccelerometerSensor(self)
        self.humidity = HumiditySensor(self)
        self.magnetometer = MagnetometerSensor(self)
        self.barometer = BarometerSensor(self)
        self.gyroscope = GyroscopeSensor(self)
        self.keypress = KeypressSensor(self)
        self.luxometer = LuxometerSensor(self)


class KeypressDelegate(DefaultDelegate):
    BUTTON_L = 0x02
    BUTTON_R = 0x01
    ALL_BUTTONS = (BUTTON_L | BUTTON_R)

    _button_desc = { 
        BUTTON_L : "Left button",
        BUTTON_R : "Right button",
        ALL_BUTTONS : "Both buttons"
    } 

    def __init__(self):
        DefaultDelegate.__init__(self)
        self.lastVal = 0

    def handleNotification(self, hnd, data):
        # NB: only one source of notifications at present
        # so we can ignore 'hnd'.
        val = struct.unpack("B", data)[0]
        down = (val & ~self.lastVal) & self.ALL_BUTTONS
        if down != 0:
            self.onButtonDown(down)
        up = (~val & self.lastVal) & self.ALL_BUTTONS
        if up != 0:
            self.onButtonUp(up)
        self.lastVal = val

    def onButtonUp(self, but):
        print ( "** " + self._button_desc[but] + " UP")

    def onButtonDown(self, but):
        print ( "** " + self._button_desc[but] + " DOWN")




if __name__ == "__main__":
    import time
    import sys
    import argparse
    
    #Global variables
    sensorOn  = struct.pack("B", 0x01)
    sensorbarcal =  struct.pack("B", 0x02)
    sensorMagOn = struct.pack("H", 0x0007)
    sensorGyrOn = struct.pack("H", 0x0007)
    sensorAccOn = struct.pack("H", 0x0038)
    Cx = 0
    Cy = 0
    parser = argparse.ArgumentParser()
    parser.add_argument('host', action='store',help='MAC of BT device')
    parser.add_argument('-n', action='store', dest='count', default=0,
            type=int, help="Number of times to loop data")
    parser.add_argument('-t',action='store',type=float, default=5.0, help='time between polling')
    parser.add_argument('-T','--temperature', action="store_true",default=False)
    parser.add_argument('-A','--accelerometer', action='store_true',
            default=False)
    parser.add_argument('-H','--humidity', action='store_true', default=False)
    parser.add_argument('-M','--magnetometer', action='store_true',
            default=False)
    parser.add_argument('-B','--barometer', action='store_true', default=False)
    parser.add_argument('-G','--gyroscope', action='store_true', default=False)
    parser.add_argument('-K','--keypress', action='store_true', default=False)
    parser.add_argument('-L','--luxometer', action='store_true', default=False)
    parser.add_argument('--all', action='store_true', default=False)
    parser.add_argument('--amqp-host', action='store',help='Host or IP of MQTT server. Default to localhost', default='localhost', dest='amqp_host')
    parser.add_argument('--amqp-port', action='store',help='Port of MQTT server. Default to 5672', default=5672, dest='amqp_port')
    parser.add_argument('--amqp-exchange', action='store',help='Queue used to send message. Default to exchange', default='exchange', dest='amqp_exchange')
    parser.add_argument('--amqp-user', action='store',help='User to connect to AMQP Server. Default to guest', default='guest', dest='amqp_user')
    parser.add_argument('--amqp-password', action='store',help='Password to connect to AMQP Server. Default to guest', default='guest', dest='amqp_password')

    arg = parser.parse_args(sys.argv[1:])
    print('Sending Data to AMQP queue on ' + arg.amqp_host + ' on port ' + str(arg.amqp_port) + ' from host ' + arg.host)

    # Source of data
    tag = SensorTag(arg.host)

    # Destination AMQP brocker
    amqpCredentials = pika.PlainCredentials(arg.amqp_user, arg.amqp_password)
    amqpConnection = pika.BlockingConnection(
        pika.ConnectionParameters(
            arg.amqp_host, 
            arg.amqp_port,
            '', 
            amqpCredentials
        )
    )

    amqpHost = arg.host.replace(':', '-')
    amqpChannel = amqpConnection.channel()
    amqpChannel.exchange_declare(exchange=arg.amqp_exchange, type='topic')

    addAndBind(
        channel=amqpChannel, 
        queue=amqpHost,
        exchange=arg.amqp_exchange,
        routing_key=amqpHost + '.#'
    )
    
    # Enabling selected sensors
    if arg.temperature or arg.all:
        tag.IRtemperature.enable(sensorOn)
        addAndBind(
            channel=amqpChannel, 
            queue='temperature',
            exchange=arg.amqp_exchange,
            routing_key='#.temperature'
        )
    if arg.humidity or arg.all:
        tag.humidity.enable(sensorOn)
        addAndBind(
            channel=amqpChannel, 
            queue='humidity',
            exchange=arg.amqp_exchange,
            routing_key='#.humidity'
        )
    # if arg.barometer or arg.all:
    #     tag.barometer.enable(sensorOn)
    #     addAndBind(
    #         channel=amqpChannel, 
    #         queue='barometer',
    #         exchange=arg.amqp_exchange,
    #         routing_key='#.barometer'
    #     )
    if arg.accelerometer or arg.all:
        tag.accelerometer.enable(sensorAccOn)
        addAndBind(
            channel=amqpChannel, 
            queue='accelerometer',
            exchange=arg.amqp_exchange,
            routing_key='#.accelerometer'
        )
    if arg.magnetometer or arg.all:
        tag.magnetometer.enable(sensorMagOn)
        addAndBind(
            channel=amqpChannel, 
            queue='magnetometer',
            exchange=arg.amqp_exchange,
            routing_key='#.magnetometer'
        )
    if arg.gyroscope or arg.all:
        tag.gyroscope.enable(sensorGyrOn)
        addAndBind(
            channel=amqpChannel, 
            queue='gyroscope',
            exchange=arg.amqp_exchange,
            routing_key='#.gyroscope'
        )
    if arg.luxometer or arg.all:
        tag.luxometer.enable(sensorOn)
        addAndBind(
            channel=amqpChannel, 
            queue='luxometer',
            exchange=arg.amqp_exchange,
            routing_key='#.luxometer'
        )
    if arg.keypress or arg.all:
        tag.keypress.enable()
        tag.setDelegate(KeypressDelegate())

    # Some sensors (e.g., temperature, accelerometer) need some time for initialization.
    # Not waiting here after enabling a sensor, the first read value might be empty or incorrect.
    time.sleep(1.0)
    t1 = time.time()
    counter=1
    while True:
        t0=time.time()
        now = datetime.now().isoformat()
        if arg.temperature or arg.all:
            routing_key = amqpHost + '.temperature'
            value = str(tag.IRtemperature.read())
            message = now + ' - ' + amqpHost + ' - ' + routing_key + ' - ' + value
            amqpChannel.basic_publish(
                exchange=arg.amqp_exchange,
                routing_key=routing_key,
                body=message
            )
        if arg.humidity or arg.all:
            routing_key = amqpHost + '.humidity'
            value = str(tag.humidity.read())
            message = now + ' - ' + routing_key + ' - ' + value
            amqpChannel.basic_publish(
                exchange=arg.amqp_exchange,
                routing_key=routing_key,
                body=message
            )
        # if arg.barometer or arg.all:
        #     routing_key = '.barometer'
        #     value = str(tag.barometer.read())
            # message = now + ' - ' + amqpHost + ' - ' + routing_key + ' - ' + value
            # amqpChannel.basic_publish(
            #     exchange=arg.amqp_exchange,
            #     routing_key=routing_key,
            #     body=message
            # )
        if arg.accelerometer or arg.all:
            routing_key = amqpHost + '.accelerometer'
            value = str(tag.accelerometer.read())
            message = now + ' - ' + amqpHost + ' - ' + routing_key + ' - ' + value
            amqpChannel.basic_publish(
                exchange=arg.amqp_exchange,
                routing_key=routing_key,
                body=message
            )
        if arg.magnetometer or arg.all:
            routing_key = amqpHost + '.magnetometer'
            value = str(tag.magnetometer.read())
            message = now + ' - ' + amqpHost + ' - ' + routing_key + ' - ' + value
            amqpChannel.basic_publish(
                exchange=arg.amqp_exchange,
                routing_key=routing_key,
                body=message
            )
        if arg.gyroscope or arg.all:
            routing_key = amqpHost + '.gyroscope'
            value = str(tag.gyroscope.read())
            message = now + ' - ' + amqpHost + ' - ' + routing_key + ' - ' + value
            amqpChannel.basic_publish(
                exchange=arg.amqp_exchange,
                routing_key=routing_key,
                body=message
            )
        if arg.luxometer or arg.all:
            routing_key = amqpHost + '.luxometer'
            value = str(tag.luxometer.read())
            message = now + ' - ' + amqpHost + ' - ' + routing_key + ' - ' + value
            amqpChannel.basic_publish(
                exchange=arg.amqp_exchange,
                routing_key=routing_key,
                body=message
            )
        if counter >= arg.count and arg.count != 0:
            break


        counter += 1
        tag.waitForNotifications(arg.t)

    # Disconnecting from local brocker
    tag.disconnect()
    del tag
    # Disconnecting from AMQP Brocker
    amqpConnection.close()
