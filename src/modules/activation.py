"""
Activation module - GPIO button and wake word detection
Модуль активации ассистента через кнопку и ключевое слово
"""

import logging
import threading
import time

logger = logging.getLogger(__name__)

# Попытка импорта GPIO
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    logger.warning("RPi.GPIO недоступен. GPIO функции будут отключены.")
    GPIO_AVAILABLE = False


class ActivationManager:
    """Управление активацией ассистента"""

    def __init__(self, config):
        """
        Инициализация менеджера активации

        Args:
            config: Словарь с конфигурацией
        """
        self.config = config
        self.gpio_config = config.get('gpio', {})
        self.wake_word_config = config.get('wake_word', {})

        self.gpio_enabled = GPIO_AVAILABLE and self.gpio_config.get('enabled', False)
        self.wake_word_enabled = self.wake_word_config.get('enabled', False)

        self.button_pressed = False
        self.wake_word_detected = False

        self._setup_gpio()

    def _setup_gpio(self):
        """Настройка GPIO для кнопки и LED"""
        if not self.gpio_enabled:
            logger.info("GPIO активация отключена")
            return

        try:
            button_pin = self.gpio_config['button_pin']
            led_pin = self.gpio_config.get('led_pin')
            bounce_time = self.gpio_config.get('bounce_time', 200)

            # Настройка GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            # Кнопка (с подтяжкой к питанию)
            GPIO.setup(button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

            # LED индикатор
            if led_pin:
                GPIO.setup(led_pin, GPIO.OUT)
                GPIO.output(led_pin, GPIO.LOW)

            # Обработчик нажатия кнопки
            GPIO.add_event_detect(
                button_pin,
                GPIO.FALLING,  # Нажатие (замыкание на землю)
                callback=self._button_callback,
                bouncetime=bounce_time
            )

            logger.info(f"GPIO настроен: кнопка на pin {button_pin}, LED на pin {led_pin}")

        except Exception as e:
            logger.error(f"Ошибка настройки GPIO: {e}")
            self.gpio_enabled = False

    def _button_callback(self, channel):
        """Callback при нажатии кнопки"""
        logger.info("Кнопка нажата!")
        self.button_pressed = True

    def wait_for_activation(self, stt_engine=None, timeout=None):
        """
        Ожидание активации (кнопка или ключевое слово)

        Args:
            stt_engine: Движок распознавания речи для wake word
            timeout: Таймаут ожидания в секундах

        Returns:
            str: Тип активации ('button', 'wake_word', 'timeout')
        """
        start_time = time.time()

        # Если оба метода отключены, сразу активируем
        if not self.gpio_enabled and not self.wake_word_enabled:
            logger.warning("Все методы активации отключены, автоматическая активация")
            return 'auto'

        # Индикация ожидания
        self.set_led_state('waiting')

        logger.info("Ожидание активации...")

        # Запуск прослушивания wake word в отдельном потоке
        wake_word_thread = None
        if self.wake_word_enabled and stt_engine:
            wake_word_thread = threading.Thread(
                target=self._wake_word_listener,
                args=(stt_engine,),
                daemon=True
            )
            wake_word_thread.start()

        # Ожидание активации
        try:
            while True:
                # Проверка кнопки
                if self.button_pressed:
                    self.button_pressed = False
                    logger.info("Активация через кнопку")
                    return 'button'

                # Проверка wake word
                if self.wake_word_detected:
                    self.wake_word_detected = False
                    logger.info("Активация через ключевое слово")
                    return 'wake_word'

                # Проверка таймаута
                if timeout and (time.time() - start_time) > timeout:
                    logger.info("Таймаут ожидания активации")
                    return 'timeout'

                time.sleep(0.1)

        except KeyboardInterrupt:
            logger.info("Ожидание прервано")
            return 'interrupted'

    def _wake_word_listener(self, stt_engine):
        """
        Прослушивание ключевого слова в фоновом режиме

        Args:
            stt_engine: Движок распознавания речи
        """
        keywords = self.wake_word_config.get('keywords', [])

        if not keywords:
            logger.warning("Ключевые слова не заданы")
            return

        try:
            # Используем метод STT для прослушивания
            detected = stt_engine.listen_for_wake_word(keywords)
            if detected:
                self.wake_word_detected = True
        except Exception as e:
            logger.error(f"Ошибка при прослушивании wake word: {e}")

    def set_led_state(self, state):
        """
        Управление LED индикатором

        Args:
            state: Состояние ('off', 'on', 'waiting', 'listening', 'processing')
        """
        if not self.gpio_enabled:
            return

        led_pin = self.gpio_config.get('led_pin')
        if not led_pin:
            return

        try:
            if state == 'off':
                GPIO.output(led_pin, GPIO.LOW)

            elif state == 'on':
                GPIO.output(led_pin, GPIO.HIGH)

            elif state == 'waiting':
                # Медленное мигание
                threading.Thread(
                    target=self._blink_led,
                    args=(led_pin, 0.5, 1),
                    daemon=True
                ).start()

            elif state == 'listening':
                # Быстрое мигание
                threading.Thread(
                    target=self._blink_led,
                    args=(led_pin, 0.1, 3),
                    daemon=True
                ).start()

            elif state == 'processing':
                # Постоянно включен
                GPIO.output(led_pin, GPIO.HIGH)

        except Exception as e:
            logger.error(f"Ошибка управления LED: {e}")

    def _blink_led(self, pin, interval, count):
        """Мигание LED"""
        try:
            for _ in range(count):
                GPIO.output(pin, GPIO.HIGH)
                time.sleep(interval)
                GPIO.output(pin, GPIO.LOW)
                time.sleep(interval)
        except Exception as e:
            logger.debug(f"Ошибка при мигании LED: {e}")

    def cleanup(self):
        """Очистка ресурсов GPIO"""
        if self.gpio_enabled:
            try:
                GPIO.cleanup()
                logger.info("GPIO очищен")
            except Exception as e:
                logger.error(f"Ошибка при очистке GPIO: {e}")


class MockGPIO:
    """Mock GPIO для тестирования на не-RPi системах"""

    BCM = 'BCM'
    IN = 'IN'
    OUT = 'OUT'
    HIGH = 1
    LOW = 0
    PUD_UP = 'PUD_UP'
    FALLING = 'FALLING'

    @staticmethod
    def setmode(mode):
        logger.debug(f"Mock GPIO: setmode({mode})")

    @staticmethod
    def setwarnings(flag):
        logger.debug(f"Mock GPIO: setwarnings({flag})")

    @staticmethod
    def setup(pin, mode, **kwargs):
        logger.debug(f"Mock GPIO: setup(pin={pin}, mode={mode})")

    @staticmethod
    def output(pin, value):
        logger.debug(f"Mock GPIO: output(pin={pin}, value={value})")

    @staticmethod
    def input(pin):
        logger.debug(f"Mock GPIO: input(pin={pin})")
        return 1

    @staticmethod
    def add_event_detect(pin, edge, callback=None, bouncetime=None):
        logger.debug(f"Mock GPIO: add_event_detect(pin={pin}, edge={edge})")

    @staticmethod
    def cleanup():
        logger.debug("Mock GPIO: cleanup()")


if __name__ == "__main__":
    # Тестирование модуля
    import yaml

    logging.basicConfig(level=logging.INFO)

    # Если не на RPi, используем Mock GPIO
    if not GPIO_AVAILABLE:
        import sys
        sys.modules['RPi.GPIO'] = type('MockGPIO', (), MockGPIO.__dict__)()
        GPIO_AVAILABLE = True

    with open("../config/config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    activation = ActivationManager(config)

    print("\n=== Тест активации ===")
    print("Нажмите Ctrl+C для выхода")

    try:
        while True:
            activation_type = activation.wait_for_activation(timeout=5)
            print(f"Активирован через: {activation_type}")

            if activation_type == 'timeout':
                print("Таймаут, повторное ожидание...")
            else:
                print("Обработка запроса...")
                activation.set_led_state('processing')
                time.sleep(2)
                activation.set_led_state('off')

    except KeyboardInterrupt:
        print("\nВыход...")
    finally:
        activation.cleanup()
