"""
Reminders and Google Calendar Integration
Напоминания и интеграция с Google Календарем
"""

import logging
import sqlite3
import pickle
import os
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# Google Calendar
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    logger.warning("Google API библиотеки недоступны")

SCOPES = ['https://www.googleapis.com/auth/calendar']


class RemindersManager:
    """Менеджер напоминаний"""

    def __init__(self, config):
        self.config = config.get('reminders', {})
        self.enabled = self.config.get('enabled', False)
        self.db_file = self.config.get('database_file', './config/reminders.db')

        self.conn = None
        self.cursor = None

        if self.enabled:
            self._init_database()

    def _init_database(self):
        """Инициализация базы данных напоминаний"""
        try:
            # Создание директории если нужно
            Path(self.db_file).parent.mkdir(parents=True, exist_ok=True)

            self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
            self.cursor = self.conn.cursor()

            # Создание таблицы
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    datetime TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    notified INTEGER DEFAULT 0
                )
            ''')
            self.conn.commit()

            logger.info(f"База данных напоминаний инициализирована: {self.db_file}")

        except Exception as e:
            logger.error(f"Ошибка инициализации БД: {e}")
            self.enabled = False

    def add_reminder(self, text, remind_datetime):
        """
        Добавить напоминание

        Args:
            text: Текст напоминания
            remind_datetime: datetime объект времени напоминания

        Returns:
            tuple: (success: bool, message: str)
        """
        if not self.enabled:
            return False, "Сервис напоминаний отключен"

        try:
            created_at = datetime.now().isoformat()
            datetime_str = remind_datetime.isoformat()

            self.cursor.execute('''
                INSERT INTO reminders (text, datetime, created_at)
                VALUES (?, ?, ?)
            ''', (text, datetime_str, created_at))

            self.conn.commit()

            reminder_id = self.cursor.lastrowid

            time_str = remind_datetime.strftime('%d.%m.%Y в %H:%M')
            message = f"Напоминание создано на {time_str}: {text}"

            logger.info(f"Напоминание #{reminder_id}: {message}")
            return True, message

        except Exception as e:
            logger.error(f"Ошибка добавления напоминания: {e}")
            return False, "Не удалось создать напоминание"

    def check_reminders(self):
        """
        Проверить активные напоминания

        Returns:
            list: Список напоминаний, которые нужно показать
        """
        if not self.enabled:
            return []

        try:
            now = datetime.now().isoformat()

            self.cursor.execute('''
                SELECT id, text, datetime
                FROM reminders
                WHERE datetime <= ? AND notified = 0
                ORDER BY datetime
            ''', (now,))

            reminders = []
            for row in self.cursor.fetchall():
                reminder_id, text, datetime_str = row
                reminders.append({
                    'id': reminder_id,
                    'text': text,
                    'datetime': datetime_str
                })

                # Отметить как уведомленное
                self.cursor.execute('''
                    UPDATE reminders SET notified = 1 WHERE id = ?
                ''', (reminder_id,))

            self.conn.commit()

            return reminders

        except Exception as e:
            logger.error(f"Ошибка проверки напоминаний: {e}")
            return []

    def parse_reminder_from_text(self, text):
        """
        Извлечь время и текст напоминания из голосовой команды

        Args:
            text: Голосовая команда

        Returns:
            tuple: (datetime|None, reminder_text)
        """
        import re
        from dateutil import parser as date_parser

        text_lower = text.lower()

        # Паттерны времени
        patterns = {
            'через_минут': r'через\s+(\d+)\s+минут',
            'через_часов': r'через\s+(\d+)\s+час',
            'в_время': r'в\s+(\d+):(\d+)',
            'завтра_в': r'завтра\s+в\s+(\d+):(\d+)',
        }

        for pattern_name, pattern in patterns.items():
            match = re.search(pattern, text_lower)
            if match:
                now = datetime.now()

                if pattern_name == 'через_минут':
                    minutes = int(match.group(1))
                    remind_time = now + timedelta(minutes=minutes)
                    reminder_text = re.sub(pattern, '', text_lower, count=1).strip()
                    return remind_time, reminder_text

                elif pattern_name == 'через_часов':
                    hours = int(match.group(1))
                    remind_time = now + timedelta(hours=hours)
                    reminder_text = re.sub(pattern, '', text_lower, count=1).strip()
                    return remind_time, reminder_text

                elif pattern_name == 'в_время':
                    hour = int(match.group(1))
                    minute = int(match.group(2))
                    remind_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if remind_time < now:
                        remind_time += timedelta(days=1)
                    reminder_text = re.sub(pattern, '', text_lower, count=1).strip()
                    return remind_time, reminder_text

                elif pattern_name == 'завтра_в':
                    hour = int(match.group(1))
                    minute = int(match.group(2))
                    remind_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    remind_time += timedelta(days=1)
                    reminder_text = re.sub(pattern, '', text_lower, count=1).strip()
                    return remind_time, reminder_text

        return None, text

    def get_upcoming_reminders(self, count=5):
        """Получить ближайшие напоминания"""
        if not self.enabled:
            return []

        try:
            now = datetime.now().isoformat()

            self.cursor.execute('''
                SELECT id, text, datetime
                FROM reminders
                WHERE datetime > ? AND notified = 0
                ORDER BY datetime
                LIMIT ?
            ''', (now, count))

            return [
                {'id': row[0], 'text': row[1], 'datetime': row[2]}
                for row in self.cursor.fetchall()
            ]

        except Exception as e:
            logger.error(f"Ошибка получения напоминаний: {e}")
            return []


class GoogleCalendarService:
    """Сервис Google Calendar"""

    def __init__(self, config):
        self.config = config.get('google_calendar', {})
        self.enabled = GOOGLE_AVAILABLE and self.config.get('enabled', False)

        self.credentials_file = self.config.get('credentials_file')
        self.token_file = self.config.get('token_file')
        self.calendar_id = self.config.get('calendar_id', 'primary')

        self.service = None

        if self.enabled:
            self._authenticate()

    def _authenticate(self):
        """Аутентификация в Google Calendar"""
        try:
            creds = None

            # Загрузка токена если есть
            if os.path.exists(self.token_file):
                with open(self.token_file, 'rb') as token:
                    creds = pickle.load(token)

            # Если нет валидных credentials, запросить аутентификацию
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not os.path.exists(self.credentials_file):
                        logger.error(f"Файл credentials не найден: {self.credentials_file}")
                        logger.info("Скачайте credentials.json из Google Cloud Console")
                        self.enabled = False
                        return

                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, SCOPES
                    )
                    creds = flow.run_local_server(port=0)

                # Сохранение токена
                with open(self.token_file, 'wb') as token:
                    pickle.dump(creds, token)

            self.service = build('calendar', 'v3', credentials=creds)
            logger.info("Google Calendar аутентификация успешна")

        except Exception as e:
            logger.error(f"Ошибка аутентификации Google Calendar: {e}")
            self.enabled = False

    def create_event(self, summary, start_datetime, duration_minutes=60, description=''):
        """
        Создать событие в календаре

        Args:
            summary: Название события
            start_datetime: Время начала
            duration_minutes: Длительность в минутах
            description: Описание

        Returns:
            tuple: (success: bool, message: str)
        """
        if not self.enabled:
            return False, "Google Calendar отключен"

        try:
            end_datetime = start_datetime + timedelta(minutes=duration_minutes)

            event = {
                'summary': summary,
                'description': description,
                'start': {
                    'dateTime': start_datetime.isoformat(),
                    'timeZone': 'Europe/Moscow',
                },
                'end': {
                    'dateTime': end_datetime.isoformat(),
                    'timeZone': 'Europe/Moscow',
                },
            }

            event = self.service.events().insert(
                calendarId=self.calendar_id,
                body=event
            ).execute()

            time_str = start_datetime.strftime('%d.%m.%Y в %H:%M')
            message = f"Событие создано: {summary} на {time_str}"

            logger.info(message)
            return True, message

        except Exception as e:
            logger.error(f"Ошибка создания события: {e}")
            return False, "Не удалось создать событие в календаре"

    def get_upcoming_events(self, count=10):
        """Получить ближайшие события"""
        if not self.enabled:
            return []

        try:
            now = datetime.utcnow().isoformat() + 'Z'

            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=now,
                maxResults=count,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            return events

        except Exception as e:
            logger.error(f"Ошибка получения событий: {e}")
            return []
