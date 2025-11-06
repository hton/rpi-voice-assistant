"""
Smart Home Integration - GPIO and MQTT control
Интеграция с умным домом через GPIO и MQTT
"""

import logging
import json
import re

logger = logging.getLogger(__name__)

# GPIO
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    logger.warning("RPi.GPIO недоступен")

# MQTT
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    logger.warning("paho-mqtt недоступен")


class SmartHomeController:
    """Контроллер умного дома"""

    def __init__(self, config):
        self.config = config
        self.smart_home_config = config.get('smart_home', {})

        self.devices = {}
        self.mqtt_client = None

        if self.smart_home_config.get('enabled', False):
            self._setup_gpio_devices()
            self._setup_mqtt()

    def _setup_gpio_devices(self):
        """Настройка GPIO устройств"""
        if not GPIO_AVAILABLE:
            return

        gpio_devices = self.smart_home_config.get('gpio_devices', [])

        if not gpio_devices:
            return

        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            for device in gpio_devices:
                name = device['name']
                pin = device['pin']
                device_type = device.get('type', 'generic')

                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)

                self.devices[name.lower()] = {
                    'pin': pin,
                    'type': device_type,
                    'state': False
                }

                logger.info(f"GPIO устройство настроено: {name} на pin {pin}")

        except Exception as e:
            logger.error(f"Ошибка настройки GPIO устройств: {e}")

    def _setup_mqtt(self):
        """Настройка MQTT клиента"""
        if not MQTT_AVAILABLE:
            return

        mqtt_config = self.smart_home_config.get('mqtt', {})

        if not mqtt_config.get('enabled', False):
            return

        try:
            self.mqtt_client = mqtt.Client(
                client_id=mqtt_config.get('client_id', 'rpi_assistant')
            )

            # Аутентификация
            username = mqtt_config.get('username')
            password = mqtt_config.get('password')
            if username and password:
                self.mqtt_client.username_pw_set(username, password)

            # Callback'и
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_message = self._on_mqtt_message

            # Подключение
            broker = mqtt_config.get('broker', 'localhost')
            port = mqtt_config.get('port', 1883)

            self.mqtt_client.connect(broker, port, 60)
            self.mqtt_client.loop_start()

            logger.info(f"MQTT подключен к {broker}:{port}")

        except Exception as e:
            logger.error(f"Ошибка подключения к MQTT: {e}")
            self.mqtt_client = None

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback при подключении к MQTT"""
        if rc == 0:
            logger.info("MQTT подключение установлено")
            # Подписка на топики
            topics = self.smart_home_config.get('mqtt', {}).get('topics', {})
            for topic_name, topic_path in topics.items():
                client.subscribe(f"{topic_path}/#")
                logger.info(f"Подписка на топик: {topic_path}/#")
        else:
            logger.error(f"MQTT подключение не удалось: {rc}")

    def _on_mqtt_message(self, client, userdata, msg):
        """Callback при получении MQTT сообщения"""
        logger.debug(f"MQTT сообщение: {msg.topic} = {msg.payload.decode()}")

    def process_command(self, text):
        """
        Обработка голосовой команды управления

        Args:
            text: Текст команды

        Returns:
            tuple: (success: bool, response: str)
        """
        text = text.lower()

        # Паттерны команд
        patterns = {
            'turn_on': r'(включи|включить|запусти|запустить)\s+(.+)',
            'turn_off': r'(выключи|выключить|останови|остановить)\s+(.+)',
            'status': r'(статус|состояние)\s+(.+)',
        }

        for command, pattern in patterns.items():
            match = re.search(pattern, text)
            if match:
                device_name = match.group(2).strip()

                if command == 'turn_on':
                    return self.turn_on(device_name)
                elif command == 'turn_off':
                    return self.turn_off(device_name)
                elif command == 'status':
                    return self.get_status(device_name)

        # Команда не распознана
        return False, "Не удалось распознать команду управления устройством"

    def turn_on(self, device_name):
        """Включить устройство"""
        device_name = device_name.lower()

        # GPIO устройство
        if device_name in self.devices:
            try:
                pin = self.devices[device_name]['pin']
                GPIO.output(pin, GPIO.HIGH)
                self.devices[device_name]['state'] = True
                logger.info(f"Включено: {device_name}")
                return True, f"{device_name} включен"
            except Exception as e:
                logger.error(f"Ошибка включения {device_name}: {e}")
                return False, f"Ошибка при включении {device_name}"

        # MQTT устройство
        if self.mqtt_client:
            try:
                topic = f"home/devices/{device_name}/set"
                self.mqtt_client.publish(topic, "ON")
                logger.info(f"MQTT команда: {topic} = ON")
                return True, f"{device_name} включен"
            except Exception as e:
                logger.error(f"Ошибка MQTT команды: {e}")

        return False, f"Устройство {device_name} не найдено"

    def turn_off(self, device_name):
        """Выключить устройство"""
        device_name = device_name.lower()

        # GPIO устройство
        if device_name in self.devices:
            try:
                pin = self.devices[device_name]['pin']
                GPIO.output(pin, GPIO.LOW)
                self.devices[device_name]['state'] = False
                logger.info(f"Выключено: {device_name}")
                return True, f"{device_name} выключен"
            except Exception as e:
                logger.error(f"Ошибка выключения {device_name}: {e}")
                return False, f"Ошибка при выключении {device_name}"

        # MQTT устройство
        if self.mqtt_client:
            try:
                topic = f"home/devices/{device_name}/set"
                self.mqtt_client.publish(topic, "OFF")
                logger.info(f"MQTT команда: {topic} = OFF")
                return True, f"{device_name} выключен"
            except Exception as e:
                logger.error(f"Ошибка MQTT команды: {e}")

        return False, f"Устройство {device_name} не найдено"

    def get_status(self, device_name):
        """Получить статус устройства"""
        device_name = device_name.lower()

        if device_name in self.devices:
            state = "включен" if self.devices[device_name]['state'] else "выключен"
            return True, f"{device_name} {state}"

        return False, f"Устройство {device_name} не найдено"

    def cleanup(self):
        """Очистка ресурсов"""
        if GPIO_AVAILABLE:
            try:
                GPIO.cleanup()
            except:
                pass

        if self.mqtt_client:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except:
                pass
