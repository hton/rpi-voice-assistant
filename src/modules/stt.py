"""
Speech-to-Text module using Vosk
Распознавание речи на русском языке
"""

import os
import json
import queue
import logging
import sounddevice as sd
from vosk import Model, KaldiRecognizer

logger = logging.getLogger(__name__)


class SpeechRecognizer:
    """Класс для распознавания речи с использованием Vosk"""

    def __init__(self, config):
        """
        Инициализация распознавателя речи

        Args:
            config: Словарь с конфигурацией из config.yaml
        """
        self.config = config
        self.audio_config = config['audio']
        self.stt_config = config['stt']

        self.model = None
        self.recognizer = None
        self.audio_queue = queue.Queue()

        self._load_model()

    def _load_model(self):
        """Загрузка модели Vosk"""
        model_path = self.stt_config['model_path']

        if not os.path.exists(model_path):
            logger.error(f"Модель Vosk не найдена по пути: {model_path}")
            logger.info(f"Скачайте модель с: {self.stt_config['model_url']}")
            logger.info(f"И распакуйте в: {model_path}")
            raise FileNotFoundError(f"Vosk model not found at {model_path}")

        logger.info(f"Загрузка модели Vosk из {model_path}")
        self.model = Model(model_path)
        logger.info("Модель Vosk загружена успешно")

    def _audio_callback(self, indata, frames, time, status):
        """Callback для записи аудио"""
        if status:
            logger.warning(f"Audio callback status: {status}")
        self.audio_queue.put(bytes(indata))

    def listen(self, timeout=None):
        """
        Прослушивание и распознавание речи

        Args:
            timeout: Максимальное время записи в секундах (None = бесконечно)

        Returns:
            str: Распознанный текст или None в случае ошибки
        """
        sample_rate = self.audio_config['sample_rate']
        device_index = self.audio_config.get('mic_device_index')

        # Создаем новый распознаватель для каждой сессии
        self.recognizer = KaldiRecognizer(self.model, sample_rate)
        self.recognizer.SetWords(True)

        logger.info("Начало прослушивания...")

        try:
            with sd.RawInputStream(
                samplerate=sample_rate,
                blocksize=self.audio_config['chunk_size'],
                device=device_index,
                dtype='int16',
                channels=1,
                callback=self._audio_callback
            ):
                silence_chunks = 0
                max_silence_chunks = int(
                    self.config['performance']['silence_timeout'] * sample_rate /
                    self.audio_config['chunk_size']
                )

                recorded_chunks = 0
                max_chunks = None
                if timeout:
                    max_chunks = int(
                        timeout * sample_rate / self.audio_config['chunk_size']
                    )

                while True:
                    data = self.audio_queue.get()
                    recorded_chunks += 1

                    if self.recognizer.AcceptWaveform(data):
                        result = json.loads(self.recognizer.Result())
                        if result.get('text'):
                            logger.info(f"Распознано: {result['text']}")
                            return result['text']
                        silence_chunks += 1
                    else:
                        # Частичный результат
                        partial = json.loads(self.recognizer.PartialResult())
                        if partial.get('partial'):
                            silence_chunks = 0  # Сброс счетчика тишины
                        else:
                            silence_chunks += 1

                    # Проверка тайм-аута тишины
                    if silence_chunks >= max_silence_chunks:
                        logger.info("Обнаружена тишина, завершение записи")
                        break

                    # Проверка максимального времени записи
                    if max_chunks and recorded_chunks >= max_chunks:
                        logger.info("Достигнут максимальный таймаут записи")
                        break

                # Получение финального результата
                final_result = json.loads(self.recognizer.FinalResult())
                text = final_result.get('text', '')

                if text:
                    logger.info(f"Финальный результат: {text}")
                    return text
                else:
                    logger.warning("Речь не распознана")
                    return None

        except Exception as e:
            logger.error(f"Ошибка при распознавании речи: {e}")
            return None
        finally:
            # Очистка очереди
            while not self.audio_queue.empty():
                self.audio_queue.get()

    def listen_for_wake_word(self, keywords):
        """
        Непрерывное прослушивание в ожидании ключевого слова

        Args:
            keywords: Список ключевых слов для активации

        Returns:
            bool: True если обнаружено ключевое слово
        """
        sample_rate = self.audio_config['sample_rate']
        device_index = self.audio_config.get('mic_device_index')

        self.recognizer = KaldiRecognizer(self.model, sample_rate)

        logger.info(f"Ожидание ключевых слов: {keywords}")

        try:
            with sd.RawInputStream(
                samplerate=sample_rate,
                blocksize=self.audio_config['chunk_size'],
                device=device_index,
                dtype='int16',
                channels=1,
                callback=self._audio_callback
            ):
                while True:
                    data = self.audio_queue.get()

                    if self.recognizer.AcceptWaveform(data):
                        result = json.loads(self.recognizer.Result())
                        text = result.get('text', '').lower()

                        if text:
                            logger.debug(f"Распознано: {text}")

                            # Проверка наличия ключевого слова
                            for keyword in keywords:
                                if keyword.lower() in text:
                                    logger.info(f"Обнаружено ключевое слово: {keyword}")
                                    return True

        except KeyboardInterrupt:
            logger.info("Прослушивание прервано пользователем")
            return False
        except Exception as e:
            logger.error(f"Ошибка при прослушивании ключевого слова: {e}")
            return False

    def get_available_devices(self):
        """Получить список доступных аудио устройств"""
        devices = sd.query_devices()
        logger.info("Доступные аудио устройства:")
        for i, device in enumerate(devices):
            logger.info(f"  [{i}] {device['name']} - In: {device['max_input_channels']}, Out: {device['max_output_channels']}")
        return devices


if __name__ == "__main__":
    # Тестирование модуля
    import yaml

    logging.basicConfig(level=logging.INFO)

    with open("../config/config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    recognizer = SpeechRecognizer(config)
    recognizer.get_available_devices()

    print("\n=== Тест распознавания речи ===")
    print("Скажите что-нибудь...")
    text = recognizer.listen(timeout=10)
    print(f"Результат: {text}")
