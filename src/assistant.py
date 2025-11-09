#!/usr/bin/env python3
"""
Raspberry Pi Voice Assistant
Main application file

Голосовой ассистент для Raspberry Pi
Главный файл приложения
"""

import os
import sys
import yaml
import logging
import logging.handlers
import signal
import threading
import time
import re
from pathlib import Path
from dotenv import load_dotenv

# Добавление путей
sys.path.insert(0, str(Path(__file__).parent))


def sanitize_user_input(text, max_length=500):
    """
    Санитизация пользовательского ввода для безопасности

    Args:
        text: Пользовательский текст
        max_length: Максимальная длина

    Returns:
        str: Очищенный текст
    """
    if not text:
        return ""

    # Ограничение длины
    text = text[:max_length]

    # Удаление управляющих символов (кроме пробела и переноса строки)
    text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', text)

    # Удаление множественных пробелов
    text = re.sub(r'\s+', ' ', text).strip()

    return text

# Импорт модулей
from modules.stt import SpeechRecognizer
from modules.tts import TextToSpeech, SimpleTTS
from modules.llm import LLMEngine, SimpleLLM
from modules.activation import ActivationManager
from services.smart_home import SmartHomeController
from services.information import WeatherService, NewsService
from services.reminders import RemindersManager, GoogleCalendarService


class VoiceAssistant:
    """Главный класс голосового ассистента"""

    def __init__(self, config_path='config/config.yaml'):
        """
        Инициализация ассистента

        Args:
            config_path: Путь к файлу конфигурации
        """
        # Загрузка конфигурации
        self.config = self._load_config(config_path)

        # Настройка логирования
        self._setup_logging()

        self.logger = logging.getLogger(__name__)
        self.logger.info("=" * 60)
        self.logger.info("Raspberry Pi Voice Assistant")
        self.logger.info("=" * 60)

        # Состояние
        self.running = False
        self.reminder_thread = None

        # Инициализация компонентов
        self._init_components()

    def _load_config(self, config_path):
        """Загрузка конфигурации"""
        # Загрузка .env
        load_dotenv()

        # Загрузка YAML конфигурации
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        return config

    def _setup_logging(self):
        """Настройка системы логирования"""
        log_config = self.config.get('logging', {})

        log_level = getattr(logging, log_config.get('level', 'INFO'))
        log_file = log_config.get('file', './logs/assistant.log')
        console_output = log_config.get('console_output', True)

        # Создание директории для логов
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)

        # Настройка форматирования
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Обработчик файла
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=log_config.get('max_bytes', 10485760),
            backupCount=log_config.get('backup_count', 5),
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)

        # Корневой logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        root_logger.addHandler(file_handler)

        # Консольный вывод
        if console_output:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)

    def _init_components(self):
        """Инициализация всех компонентов"""
        self.logger.info("Инициализация компонентов...")

        try:
            # STT
            self.logger.info("Загрузка модуля распознавания речи...")
            self.stt = SpeechRecognizer(self.config)

            # TTS
            self.logger.info("Загрузка модуля синтеза речи...")
            try:
                self.tts = TextToSpeech(self.config)
            except Exception as e:
                self.logger.warning(f"Piper недоступен ({e}), использую SimpleTTS")
                self.tts = SimpleTTS(self.config)

            # LLM
            # Проверяем, хочет ли пользователь использовать простую модель
            use_simple_llm = self.config.get('llm', {}).get('use_simple_llm', False)

            if use_simple_llm:
                self.logger.info("Использую SimpleLLM (на основе правил)")
                self.llm = SimpleLLM(self.config)
            else:
                self.logger.info("Загрузка языковой модели (это может занять время)...")
                try:
                    self.llm = LLMEngine(self.config)
                except Exception as e:
                    self.logger.error(f"Не удалось загрузить LLM: {e}")
                    self.logger.warning("Использую SimpleLLM")
                    self.llm = SimpleLLM(self.config)

            # Активация
            self.logger.info("Настройка системы активации...")
            self.activation = ActivationManager(self.config)

            # Умный дом
            self.logger.info("Инициализация контроллера умного дома...")
            self.smart_home = SmartHomeController(self.config)

            # Погода и новости
            self.logger.info("Инициализация информационных сервисов...")
            self.weather = WeatherService(self.config)
            self.news = NewsService(self.config)

            # Напоминания и календарь
            self.logger.info("Инициализация системы напоминаний...")
            self.reminders = RemindersManager(self.config)
            self.calendar = GoogleCalendarService(self.config)

            self.logger.info("Все компоненты успешно инициализированы!")

        except Exception as e:
            self.logger.error(f"Ошибка при инициализации компонентов: {e}")
            raise

    def start(self):
        """Запуск ассистента"""
        self.logger.info("Запуск голосового ассистента...")
        self.running = True

        # Запуск фонового потока для проверки напоминаний
        self.reminder_thread = threading.Thread(target=self._reminder_checker, daemon=True)
        self.reminder_thread.start()

        # Приветствие
        self.tts.speak("Голосовой ассистент запущен и готов к работе.")

        # Основной цикл
        try:
            while self.running:
                self._main_loop()

        except KeyboardInterrupt:
            self.logger.info("Получен сигнал остановки")
        finally:
            self.stop()

    def _main_loop(self):
        """Основной цикл работы ассистента"""
        # Ожидание активации
        self.logger.info("Ожидание активации...")
        activation_type = self.activation.wait_for_activation(
            stt_engine=self.stt,
            timeout=None
        )

        if activation_type == 'timeout' or activation_type == 'interrupted':
            return

        # Индикация прослушивания
        self.activation.set_led_state('listening')
        self.tts.speak("Слушаю")

        # Распознавание речи
        self.logger.info("Прослушивание команды...")
        max_recording_duration = self.config['performance']['max_recording_duration']
        user_text = self.stt.listen(timeout=max_recording_duration)

        if not user_text:
            self.tts.speak("Я не расслышал команду")
            self.activation.set_led_state('off')
            return

        # Санитизация пользовательского ввода
        user_text = sanitize_user_input(user_text)

        if not user_text:
            self.tts.speak("Получена некорректная команда")
            self.activation.set_led_state('off')
            return

        # Обработка команды
        self.activation.set_led_state('processing')
        self._process_command(user_text)

        # Возврат в режим ожидания
        self.activation.set_led_state('off')

    def _process_command(self, text):
        """
        Обработка голосовой команды

        Args:
            text: Распознанный текст
        """
        self.logger.info(f"Обработка команды: {text}")

        text_lower = text.lower()

        # Проверка специальных команд
        # 1. Погода
        if any(word in text_lower for word in ['погода', 'температура', 'градус']):
            success, message = self.weather.get_weather()
            self.tts.speak(message)
            return

        # 2. Новости
        if 'новост' in text_lower:
            success, message = self.news.get_news()
            self.tts.speak(message)
            return

        # 3. Управление умным домом
        if any(word in text_lower for word in ['включи', 'выключи', 'запусти', 'останови']):
            success, message = self.smart_home.process_command(text)
            if success:
                self.tts.speak(message)
                return

        # 4. Напоминания
        if 'напомни' in text_lower or 'напоминание' in text_lower:
            self._handle_reminder(text)
            return

        # 5. Создание события в календаре
        if any(word in text_lower for word in ['создай встречу', 'добавь событие', 'запланируй']):
            self._handle_calendar_event(text)
            return

        # 6. Сброс контекста
        if 'забудь' in text_lower or 'сбрось' in text_lower or 'новый разговор' in text_lower:
            self.llm.reset_conversation()
            self.tts.speak("Контекст разговора сброшен")
            return

        # 7. Завершение работы
        if any(word in text_lower for word in ['выключись', 'завершить работу', 'стоп программа']):
            self.tts.speak("Завершаю работу. До свидания!")
            self.running = False
            return

        # Обычный разговор с LLM
        response = self.llm.generate_response(text, use_history=True)
        self.tts.speak(response)

    def _handle_reminder(self, text):
        """Обработка создания напоминания"""
        # Парсинг времени и текста
        remind_time, reminder_text = self.reminders.parse_reminder_from_text(text)

        if remind_time and reminder_text:
            success, message = self.reminders.add_reminder(reminder_text, remind_time)
            self.tts.speak(message)
        else:
            self.tts.speak("Не удалось понять время напоминания. Попробуйте сказать, например: напомни через 10 минут купить молоко")

    def _handle_calendar_event(self, text):
        """Обработка создания события в календаре"""
        # Упрощенная обработка - можно расширить
        # Пока просто создаем событие с текущим текстом
        from datetime import datetime, timedelta

        # Попытка извлечь время
        remind_time, event_text = self.reminders.parse_reminder_from_text(text)

        if not remind_time:
            # По умолчанию через час
            remind_time = datetime.now() + timedelta(hours=1)

        if not event_text:
            event_text = text

        success, message = self.calendar.create_event(
            summary=event_text,
            start_datetime=remind_time,
            duration_minutes=60
        )

        self.tts.speak(message)

    def _reminder_checker(self):
        """Фоновый поток для проверки напоминаний"""
        check_interval = self.config.get('reminders', {}).get('check_interval', 60)

        while self.running:
            try:
                # Проверка напоминаний
                due_reminders = self.reminders.check_reminders()

                for reminder in due_reminders:
                    message = f"Напоминание: {reminder['text']}"
                    self.logger.info(message)
                    self.tts.speak(message)

                time.sleep(check_interval)

            except Exception as e:
                self.logger.error(f"Ошибка в reminder_checker: {e}")
                time.sleep(check_interval)

    def stop(self):
        """Остановка ассистента"""
        self.logger.info("Остановка голосового ассистента...")
        self.running = False

        # Очистка ресурсов
        try:
            self.activation.cleanup()
            self.smart_home.cleanup()
        except Exception as e:
            self.logger.error(f"Ошибка при очистке ресурсов: {e}")

        self.logger.info("Голосовой ассистент остановлен")


def main():
    """Точка входа"""
    import argparse

    parser = argparse.ArgumentParser(description='Raspberry Pi Voice Assistant')
    parser.add_argument(
        '--config',
        type=str,
        default='config/config.yaml',
        help='Путь к файлу конфигурации'
    )
    args = parser.parse_args()

    # Создание и запуск ассистента
    assistant = VoiceAssistant(config_path=args.config)

    # Обработка сигналов
    def signal_handler(sig, frame):
        print("\nПолучен сигнал завершения...")
        assistant.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Запуск
    assistant.start()


if __name__ == "__main__":
    main()
