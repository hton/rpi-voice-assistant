"""
Information Services - Weather and News
Сервисы получения информации: погода и новости
"""

import logging
import requests
from datetime import datetime
import os

logger = logging.getLogger(__name__)


class WeatherService:
    """Сервис получения погоды"""

    def __init__(self, config):
        self.config = config.get('weather', {})
        self.enabled = self.config.get('enabled', False)
        self.api_key = os.getenv('WEATHER_API_KEY') or self.config.get('api_key', '')
        self.city = os.getenv('WEATHER_CITY') or self.config.get('city', 'Moscow')
        self.provider = self.config.get('api_provider', 'openweathermap')

    def get_weather(self):
        """
        Получить текущую погоду

        Returns:
            tuple: (success: bool, message: str)
        """
        if not self.enabled:
            return False, "Сервис погоды отключен"

        if not self.api_key:
            return False, "API ключ для погоды не настроен"

        try:
            if self.provider == 'openweathermap':
                return self._get_openweathermap()
            else:
                return False, f"Неподдерживаемый провайдер: {self.provider}"

        except Exception as e:
            logger.error(f"Ошибка получения погоды: {e}")
            return False, "Не удалось получить данные о погоде"

    def _get_openweathermap(self):
        """Получить погоду от OpenWeatherMap"""
        url = "http://api.openweathermap.org/data/2.5/weather"
        params = {
            'q': self.city,
            'appid': self.api_key,
            'units': 'metric',
            'lang': 'ru'
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        # Формирование ответа
        temp = data['main']['temp']
        feels_like = data['main']['feels_like']
        description = data['weather'][0]['description']
        humidity = data['main']['humidity']
        wind_speed = data['wind']['speed']

        message = (
            f"Погода в городе {self.city}: {description}. "
            f"Температура {temp:.0f} градусов, ощущается как {feels_like:.0f}. "
            f"Влажность {humidity}%, ветер {wind_speed} метров в секунду."
        )

        logger.info(f"Погода: {message}")
        return True, message


class NewsService:
    """Сервис получения новостей"""

    def __init__(self, config):
        self.config = config.get('news', {})
        self.enabled = self.config.get('enabled', False)
        self.api_key = os.getenv('NEWS_API_KEY') or self.config.get('api_key', '')
        self.country = self.config.get('country', 'ru')
        self.max_articles = self.config.get('max_articles', 5)

    def get_news(self, category=None):
        """
        Получить последние новости

        Args:
            category: Категория новостей (business, technology, sports, etc.)

        Returns:
            tuple: (success: bool, message: str)
        """
        if not self.enabled:
            return False, "Сервис новостей отключен"

        if not self.api_key:
            return False, "API ключ для новостей не настроен"

        try:
            url = "https://newsapi.org/v2/top-headlines"
            params = {
                'apiKey': self.api_key,
                'country': self.country,
                'pageSize': self.max_articles
            }

            if category:
                params['category'] = category

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if data.get('status') != 'ok':
                return False, "Ошибка получения новостей"

            articles = data.get('articles', [])

            if not articles:
                return True, "Новостей не найдено"

            # Формирование ответа
            news_list = []
            for i, article in enumerate(articles[:self.max_articles], 1):
                title = article.get('title', 'Без названия')
                news_list.append(f"{i}. {title}")

            message = "Последние новости: " + ". ".join(news_list)

            logger.info(f"Новости получены: {len(articles)} статей")
            return True, message

        except Exception as e:
            logger.error(f"Ошибка получения новостей: {e}")
            return False, "Не удалось получить новости"


if __name__ == "__main__":
    # Тестирование
    import yaml
    from dotenv import load_dotenv

    logging.basicConfig(level=logging.INFO)
    load_dotenv()

    with open("../config/config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    print("\n=== Тест сервиса погоды ===")
    weather = WeatherService(config)
    success, message = weather.get_weather()
    print(f"Успех: {success}")
    print(f"Сообщение: {message}")

    print("\n=== Тест сервиса новостей ===")
    news = NewsService(config)
    success, message = news.get_news()
    print(f"Успех: {success}")
    print(f"Сообщение: {message}")
