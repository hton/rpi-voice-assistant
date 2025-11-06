#!/usr/bin/env python3
"""
Скрипт тестирования компонентов голосового ассистента
Test script for voice assistant components
"""

import sys
import yaml
import logging
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)

logger = logging.getLogger(__name__)


def test_config():
    """Тест загрузки конфигурации"""
    logger.info("=" * 60)
    logger.info("Тест 1: Загрузка конфигурации")
    logger.info("=" * 60)

    try:
        with open('config/config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        logger.info("✓ Конфигурация загружена успешно")
        logger.info(f"  - LLM модель: {config['llm']['model_name']}")
        logger.info(f"  - Vosk модель: {config['stt']['model_path']}")
        logger.info(f"  - Piper модель: {config['tts']['model_path']}")
        return True, config

    except Exception as e:
        logger.error(f"✗ Ошибка загрузки конфигурации: {e}")
        return False, None


def test_audio():
    """Тест аудио устройств"""
    logger.info("\n" + "=" * 60)
    logger.info("Тест 2: Аудио устройства")
    logger.info("=" * 60)

    try:
        import sounddevice as sd

        devices = sd.query_devices()

        logger.info("✓ Найдены аудио устройства:")
        for i, device in enumerate(devices):
            logger.info(f"  [{i}] {device['name']}")
            logger.info(f"      Входов: {device['max_input_channels']}, "
                       f"Выходов: {device['max_output_channels']}")

        return True

    except Exception as e:
        logger.error(f"✗ Ошибка проверки аудио: {e}")
        return False


def test_vosk(config):
    """Тест Vosk STT"""
    logger.info("\n" + "=" * 60)
    logger.info("Тест 3: Vosk (распознавание речи)")
    logger.info("=" * 60)

    try:
        from vosk import Model

        model_path = config['stt']['model_path']

        if not Path(model_path).exists():
            logger.error(f"✗ Модель Vosk не найдена: {model_path}")
            logger.info("  Запустите: bash install.sh")
            return False

        logger.info(f"  Загрузка модели из {model_path}...")
        model = Model(model_path)

        logger.info("✓ Модель Vosk загружена успешно")
        return True

    except Exception as e:
        logger.error(f"✗ Ошибка загрузки Vosk: {e}")
        return False


def test_piper(config):
    """Тест Piper TTS"""
    logger.info("\n" + "=" * 60)
    logger.info("Тест 4: Piper (синтез речи)")
    logger.info("=" * 60)

    try:
        import subprocess

        # Проверка установки Piper
        result = subprocess.run(
            ['piper', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )

        logger.info(f"✓ Piper установлен: {result.stdout.strip()}")

        # Проверка модели
        model_path = config['tts']['model_path']

        if Path(model_path).exists():
            logger.info(f"✓ Модель Piper найдена: {model_path}")
            return True
        else:
            logger.error(f"✗ Модель Piper не найдена: {model_path}")
            logger.info("  Запустите: bash install.sh")
            return False

    except FileNotFoundError:
        logger.error("✗ Piper не установлен")
        logger.info("  Установите: pip install piper-tts")
        return False
    except Exception as e:
        logger.error(f"✗ Ошибка проверки Piper: {e}")
        return False


def test_transformers():
    """Тест HuggingFace Transformers"""
    logger.info("\n" + "=" * 60)
    logger.info("Тест 5: HuggingFace Transformers")
    logger.info("=" * 60)

    try:
        import torch
        import transformers

        logger.info(f"✓ PyTorch версия: {torch.__version__}")
        logger.info(f"✓ Transformers версия: {transformers.__version__}")

        # Проверка CUDA (опционально)
        if torch.cuda.is_available():
            logger.info(f"✓ CUDA доступна: {torch.cuda.get_device_name(0)}")
        else:
            logger.info("  CUDA недоступна (будет использован CPU)")

        return True

    except Exception as e:
        logger.error(f"✗ Ошибка проверки Transformers: {e}")
        return False


def test_gpio():
    """Тест GPIO"""
    logger.info("\n" + "=" * 60)
    logger.info("Тест 6: GPIO (опционально)")
    logger.info("=" * 60)

    try:
        import RPi.GPIO as GPIO

        GPIO.setmode(GPIO.BCM)
        logger.info("✓ RPi.GPIO доступен")
        GPIO.cleanup()
        return True

    except ImportError:
        logger.warning("⚠ RPi.GPIO недоступен (нормально для не-RPi систем)")
        return True
    except Exception as e:
        logger.error(f"✗ Ошибка GPIO: {e}")
        return False


def test_mqtt():
    """Тест MQTT"""
    logger.info("\n" + "=" * 60)
    logger.info("Тест 7: MQTT (опционально)")
    logger.info("=" * 60)

    try:
        import paho.mqtt.client as mqtt

        logger.info("✓ paho-mqtt установлен")
        return True

    except ImportError:
        logger.warning("⚠ paho-mqtt не установлен (опционально)")
        return True


def test_google_calendar():
    """Тест Google Calendar"""
    logger.info("\n" + "=" * 60)
    logger.info("Тест 8: Google Calendar API (опционально)")
    logger.info("=" * 60)

    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        logger.info("✓ Google API библиотеки установлены")

        # Проверка credentials файла
        if Path('config/google_credentials.json').exists():
            logger.info("✓ google_credentials.json найден")
        else:
            logger.warning("⚠ google_credentials.json не найден (опционально)")

        return True

    except ImportError:
        logger.warning("⚠ Google API библиотеки не установлены (опционально)")
        return True


def main():
    """Главная функция"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 8 + "ТЕСТИРОВАНИЕ КОМПОНЕНТОВ АССИСТЕНТА" + " " * 15 + "║")
    print("╚" + "=" * 58 + "╝")
    print("\n")

    results = []

    # Тест 1: Конфигурация
    success, config = test_config()
    results.append(("Конфигурация", success))

    if not config:
        logger.error("\nНевозможно продолжить без конфигурации")
        return

    # Тест 2: Аудио
    success = test_audio()
    results.append(("Аудио устройства", success))

    # Тест 3: Vosk
    success = test_vosk(config)
    results.append(("Vosk STT", success))

    # Тест 4: Piper
    success = test_piper(config)
    results.append(("Piper TTS", success))

    # Тест 5: Transformers
    success = test_transformers()
    results.append(("Transformers", success))

    # Тест 6: GPIO
    success = test_gpio()
    results.append(("GPIO", success))

    # Тест 7: MQTT
    success = test_mqtt()
    results.append(("MQTT", success))

    # Тест 8: Google Calendar
    success = test_google_calendar()
    results.append(("Google Calendar", success))

    # Итоговый отчет
    logger.info("\n" + "=" * 60)
    logger.info("ИТОГОВЫЙ ОТЧЕТ")
    logger.info("=" * 60)

    for name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        logger.info(f"{status:10} - {name}")

    passed = sum(1 for _, s in results if s)
    total = len(results)

    logger.info("=" * 60)
    logger.info(f"Пройдено тестов: {passed}/{total}")
    logger.info("=" * 60)

    if passed == total:
        logger.info("\n✓ Все тесты пройдены! Система готова к работе.")
        logger.info("\nЗапуск ассистента:")
        logger.info("  python3 src/assistant.py")
    else:
        logger.warning("\n⚠ Некоторые тесты не пройдены.")
        logger.info("\nСмотрите сообщения выше для решения проблем.")

    print("\n")


if __name__ == "__main__":
    main()
