"""
Text-to-Speech module using Piper
Синтез речи на русском языке
"""

import os
import logging
import subprocess
import tempfile
import sounddevice as sd
import numpy as np
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def sanitize_text_for_tts(text, max_length=1000):
    """
    Санитизация текста для безопасного использования в TTS

    Args:
        text: Текст для санитизации
        max_length: Максимальная длина текста

    Returns:
        str: Безопасный текст
    """
    if not text:
        return ""

    # Ограничение длины
    text = text[:max_length]

    # Удаление потенциально опасных символов и команд
    # Разрешаем только буквы, цифры, пробелы и базовую пунктуацию
    text = re.sub(r'[^\w\s\.,!?;:\-—\'"()а-яА-ЯёЁ]', '', text)

    # Удаление последовательных пробелов
    text = re.sub(r'\s+', ' ', text).strip()

    return text


class TextToSpeech:
    """Класс для синтеза речи с использованием Piper"""

    def __init__(self, config):
        """
        Инициализация TTS

        Args:
            config: Словарь с конфигурацией из config.yaml
        """
        self.config = config
        self.audio_config = config['audio']
        self.tts_config = config['tts']

        self._check_piper()

    def _check_piper(self):
        """Проверка наличия Piper"""
        try:
            result = subprocess.run(
                ['piper', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            logger.info(f"Piper version: {result.stdout.strip()}")
        except FileNotFoundError:
            logger.error("Piper не установлен!")
            logger.info("Установите Piper: pip install piper-tts")
            logger.info("Или скачайте бинарник: https://github.com/rhasspy/piper/releases")
            raise
        except Exception as e:
            logger.warning(f"Не удалось проверить версию Piper: {e}")

    def speak(self, text, blocking=True):
        """
        Произнести текст

        Args:
            text: Текст для произнесения
            blocking: Ждать завершения воспроизведения

        Returns:
            bool: True если успешно
        """
        if not text or not text.strip():
            logger.warning("Пустой текст для произнесения")
            return False

        # Санитизация текста для безопасности
        text = sanitize_text_for_tts(text)

        if not text:
            logger.warning("Текст стал пустым после санитизации")
            return False

        logger.info(f"TTS: {text}")

        try:
            # Генерация аудио через Piper
            audio_data = self._generate_audio(text)

            if audio_data is not None:
                # Воспроизведение
                self._play_audio(audio_data, blocking=blocking)
                return True
            else:
                logger.error("Не удалось сгенерировать аудио")
                return False

        except Exception as e:
            logger.error(f"Ошибка при синтезе речи: {e}")
            return False

    def _generate_audio(self, text):
        """
        Генерация аудио из текста с помощью Piper

        Args:
            text: Текст для синтеза

        Returns:
            numpy.ndarray: Аудио данные или None в случае ошибки
        """
        model_path = self.tts_config.get('model_path')

        if not model_path or not os.path.exists(model_path):
            logger.error(f"Модель Piper не найдена: {model_path}")
            logger.info("Скачайте русскую модель с: https://huggingface.co/rhasspy/piper-voices/tree/main/ru")
            logger.info("Например: ru_RU-ruslan-medium")
            return None

        # Создаем временный файл для вывода
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            output_path = temp_file.name

        try:
            # Параметры Piper
            cmd = [
                'piper',
                '--model', model_path,
                '--output_file', output_path,
            ]

            # Добавляем опциональные параметры
            if 'length_scale' in self.tts_config:
                cmd.extend(['--length_scale', str(self.tts_config['length_scale'])])

            if 'noise_scale' in self.tts_config:
                cmd.extend(['--noise_scale', str(self.tts_config['noise_scale'])])

            if 'noise_w' in self.tts_config:
                cmd.extend(['--noise_w', str(self.tts_config['noise_w'])])

            if 'speaker_id' in self.tts_config:
                cmd.extend(['--speaker', str(self.tts_config['speaker_id'])])

            # Запуск Piper
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Отправляем текст в stdin
            stdout, stderr = process.communicate(input=text, timeout=30)

            if process.returncode != 0:
                logger.error(f"Ошибка Piper: {stderr}")
                return None

            # Читаем сгенерированный WAV файл
            audio_data = self._load_wav(output_path)
            return audio_data

        except subprocess.TimeoutExpired:
            logger.error("Таймаут при генерации речи")
            process.kill()
            return None
        except subprocess.SubprocessError as e:
            logger.error(f"Ошибка subprocess при генерации аудио: {e}")
            return None
        except Exception as e:
            logger.error(f"Ошибка при генерации аудио: {e}")
            return None
        finally:
            # Удаляем временный файл
            if 'output_path' in locals() and os.path.exists(output_path):
                try:
                    os.unlink(output_path)
                except OSError as e:
                    logger.debug(f"Не удалось удалить временный файл {output_path}: {e}")
                except Exception as e:
                    logger.warning(f"Неожиданная ошибка при удалении временного файла: {e}")

    def _load_wav(self, filepath):
        """
        Загрузка WAV файла

        Args:
            filepath: Путь к WAV файлу

        Returns:
            numpy.ndarray: Аудио данные
        """
        try:
            import wave

            with wave.open(filepath, 'rb') as wav_file:
                channels = wav_file.getnchannels()
                sample_rate = wav_file.getframerate()
                frames = wav_file.readframes(wav_file.getnframes())

                # Конвертация в numpy array
                audio_data = np.frombuffer(frames, dtype=np.int16)

                # Конвертация в float32 для sounddevice
                audio_data = audio_data.astype(np.float32) / 32768.0

                if channels == 2:
                    audio_data = audio_data.reshape(-1, 2)

                logger.debug(f"Загружен WAV: {sample_rate}Hz, {channels}ch, {len(audio_data)} samples")
                return audio_data

        except Exception as e:
            logger.error(f"Ошибка при загрузке WAV файла: {e}")
            return None

    def _play_audio(self, audio_data, blocking=True):
        """
        Воспроизведение аудио

        Args:
            audio_data: Аудио данные (numpy array)
            blocking: Ждать завершения воспроизведения
        """
        device_index = self.audio_config.get('speaker_device_index')

        try:
            # Определяем sample rate из конфига TTS или используем стандартный
            sample_rate = 22050  # Стандартный для Piper

            sd.play(audio_data, samplerate=sample_rate, device=device_index)

            if blocking:
                sd.wait()

            logger.debug("Воспроизведение завершено")

        except Exception as e:
            logger.error(f"Ошибка при воспроизведении аудио: {e}")

    def stop(self):
        """Остановить текущее воспроизведение"""
        try:
            sd.stop()
            logger.info("Воспроизведение остановлено")
        except Exception as e:
            logger.error(f"Ошибка при остановке воспроизведения: {e}")


class SimpleTTS:
    """
    Упрощенный TTS на основе espeak (резервный вариант)
    Используется если Piper недоступен
    """

    def __init__(self, config):
        self.config = config
        logger.warning("Используется резервный TTS (espeak)")

    def speak(self, text, blocking=True):
        """Произнести текст через espeak"""
        if not text or not text.strip():
            return False

        # Санитизация текста для безопасности
        text = sanitize_text_for_tts(text)

        if not text:
            logger.warning("Текст стал пустым после санитизации")
            return False

        logger.info(f"TTS (espeak): {text}")

        try:
            cmd = [
                'espeak',
                '-v', 'ru',
                '-s', '150',  # Скорость
                text
            ]

            if blocking:
                subprocess.run(cmd, check=True, timeout=30)
            else:
                subprocess.Popen(cmd)

            return True

        except FileNotFoundError:
            logger.error("espeak не установлен! Установите: sudo apt-get install espeak")
            return False
        except subprocess.SubprocessError as e:
            logger.error(f"Ошибка subprocess espeak: {e}")
            return False
        except Exception as e:
            logger.error(f"Ошибка espeak: {e}")
            return False

    def stop(self):
        """Остановить воспроизведение"""
        try:
            subprocess.run(['killall', 'espeak'], stderr=subprocess.DEVNULL, timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning("Таймаут при попытке остановить espeak")
        except subprocess.SubprocessError as e:
            logger.debug(f"Ошибка при остановке espeak: {e}")
        except Exception as e:
            logger.debug(f"Неожиданная ошибка при остановке espeak: {e}")


if __name__ == "__main__":
    # Тестирование модуля
    import yaml

    logging.basicConfig(level=logging.INFO)

    with open("../config/config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    try:
        tts = TextToSpeech(config)
    except Exception as e:
        logger.info(f"Переключение на SimpleTTS: {e}")
        tts = SimpleTTS(config)

    print("\n=== Тест синтеза речи ===")
    tts.speak("Привет! Я голосовой ассистент для умного дома.")
    tts.speak("Проверка синтеза русской речи.")
