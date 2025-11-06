# Быстрый старт

Минимальная инструкция для быстрого запуска голосового ассистента.

## За 5 минут

### 1. Автоматическая установка

```bash
cd ~/rpi-voice-assistant
bash install.sh
```

Скрипт установит все зависимости и загрузит модели (займет 20-30 минут).

### 2. Настройка

```bash
# Скопировать и отредактировать .env
cp .env.example .env
nano .env
```

Минимально необходимо (остальное опционально):
- Оставить пустым для базовой работы
- Или добавить WEATHER_API_KEY для погоды

### 3. Запуск

```bash
source venv/bin/activate
python3 src/assistant.py
```

### 4. Первое использование

После запуска:
1. Скажите **"привет ассистент"** (wake word)
2. Или нажмите кнопку GPIO (если подключена)
3. После звукового сигнала говорите команду
4. Например: "Привет, как дела?"

## Тестирование компонентов

Перед запуском проверьте систему:

```bash
source venv/bin/activate
python3 test_components.py
```

## Основные команды

```bash
# Общение
"Привет, как дела?"
"Расскажи анекдот"

# Погода (требует API ключ)
"Какая погода?"

# Новости (требует API ключ)
"Расскажи новости"

# Умный дом
"Включи свет в комнате"
"Выключи вентилятор"

# Напоминания
"Напомни через 10 минут купить молоко"

# Системные
"Забудь контекст"
"Выключись"
```

## Быстрые настройки

### Изменить LLM модель

Редактировать `config/config.yaml`:

```yaml
llm:
  model_name: "ai-forever/rugpt3large_based_on_gpt2"  # Легкая модель
  # или
  model_name: "IlyaGusev/saiga_mistral_7b"  # Продвинутая (нужно 8GB RAM)
```

### Настроить аудио устройства

```bash
# Посмотреть доступные устройства
python3 -c "import sounddevice as sd; print(sd.query_devices())"

# Обновить в config/config.yaml
nano config/config.yaml
```

### Добавить GPIO устройство

Редактировать `config/config.yaml`:

```yaml
smart_home:
  gpio_devices:
    - name: "свет в комнате"
      pin: 22
      type: "light"
```

## Автозапуск

```bash
# Настроить пути в service файле
sudo nano voice-assistant.service

# Установить сервис
sudo cp voice-assistant.service /etc/systemd/system/
sudo systemctl enable voice-assistant
sudo systemctl start voice-assistant

# Проверить статус
sudo systemctl status voice-assistant

# Смотреть логи
sudo journalctl -u voice-assistant -f
```

## Решение проблем

### Ошибка "No module named 'xxx'"

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Не работает микрофон

```bash
# Тест микрофона
arecord -d 5 test.wav && aplay test.wav

# Проверить индекс устройства
python3 -c "import sounddevice as sd; print(sd.query_devices())"
```

### Модель не загружается (недостаточно памяти)

Используйте более легкую модель:

```yaml
llm:
  model_name: "ai-forever/rugpt3large_based_on_gpt2"
  load_in_4bit: false
  max_new_tokens: 128
```

### Медленная работа

1. Используйте 4-bit квантизацию:
   ```yaml
   llm:
     load_in_4bit: true
   ```

2. Уменьшите `max_new_tokens`:
   ```yaml
   llm:
     max_new_tokens: 128
   ```

3. Добавьте радиатор и вентилятор на RPi

## Что дальше?

- Полная документация: [README.md](README.md)
- Настройка Google Calendar
- Настройка MQTT для умного дома
- Добавление своих команд и устройств

## Полезные ссылки

- **OpenWeatherMap API**: https://openweathermap.org/api
- **NewsAPI**: https://newsapi.org/
- **HuggingFace Models**: https://huggingface.co/models?language=ru
- **Vosk Models**: https://alphacephei.com/vosk/models
- **Piper Voices**: https://github.com/rhasspy/piper

---

**Готово!** Теперь у вас есть работающий голосовой ассистент на русском языке.
