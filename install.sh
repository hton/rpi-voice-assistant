#!/bin/bash

# Скрипт установки Raspberry Pi Voice Assistant
# Installation script for Raspberry Pi Voice Assistant

set -e

echo "========================================"
echo "Raspberry Pi Voice Assistant - Установка"
echo "========================================"
echo ""

# Проверка ОС
if [ ! -f /etc/os-release ]; then
    echo "Ошибка: Не удалось определить ОС"
    exit 1
fi

source /etc/os-release
echo "ОС: $PRETTY_NAME"
echo ""

# Проверка архитектуры
ARCH=$(uname -m)
echo "Архитектура: $ARCH"
echo ""

# Обновление системы
echo "1. Обновление системы..."
sudo apt-get update

# Установка системных зависимостей
echo ""
echo "2. Установка системных зависимостей..."
sudo apt-get install -y \
    python3-pip python3-venv python3-dev \
    portaudio19-dev python3-pyaudio \
    espeak espeak-ng \
    git wget curl unzip \
    libasound2-dev \
    libportaudio2 libportaudiocpp0 \
    build-essential \
    libffi-dev \
    libssl-dev

# Создание виртуального окружения
echo ""
echo "3. Создание виртуального окружения Python..."
python3 -m venv venv
source venv/bin/activate

# Обновление pip
echo ""
echo "4. Обновление pip..."
pip install --upgrade pip setuptools wheel

# Установка Python зависимостей
echo ""
echo "5. Установка Python зависимостей (это займет 20-30 минут)..."
pip install -r requirements.txt

# Создание директорий
echo ""
echo "6. Создание необходимых директорий..."
mkdir -p models models/piper logs config

# Загрузка Vosk модели
echo ""
echo "7. Загрузка модели Vosk для распознавания речи..."
if [ ! -d "models/vosk-model-small-ru-0.22" ]; then
    cd models
    wget -q --show-progress https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip
    unzip -q vosk-model-small-ru-0.22.zip
    rm vosk-model-small-ru-0.22.zip
    cd ..
    echo "Vosk модель загружена"
else
    echo "Vosk модель уже существует"
fi

# Загрузка Piper модели
echo ""
echo "8. Загрузка модели Piper для синтеза речи..."
if [ ! -f "models/piper/ru_RU-ruslan-medium.onnx" ]; then
    cd models/piper
    wget -q --show-progress https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/ruslan/medium/ru_RU-ruslan-medium.onnx
    wget -q --show-progress https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/ruslan/medium/ru_RU-ruslan-medium.onnx.json
    cd ../..
    echo "Piper модель загружена"
else
    echo "Piper модель уже существует"
fi

# Копирование .env файла
echo ""
echo "9. Настройка конфигурации..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ".env файл создан"
else
    echo ".env файл уже существует"
fi

# Настройка прав
echo ""
echo "10. Настройка прав доступа..."
chmod +x src/assistant.py

# Информация о дальнейших шагах
echo ""
echo "========================================"
echo "Установка завершена!"
echo "========================================"
echo ""
echo "Следующие шаги:"
echo ""
echo "1. Отредактируйте .env файл и добавьте API ключи:"
echo "   nano .env"
echo ""
echo "2. Отредактируйте config/config.yaml под ваши нужды:"
echo "   nano config/config.yaml"
echo ""
echo "3. Проверьте аудио устройства:"
echo "   source venv/bin/activate"
echo "   python3 -c 'import sounddevice as sd; print(sd.query_devices())'"
echo ""
echo "4. Запустите ассистента:"
echo "   source venv/bin/activate"
echo "   python3 src/assistant.py"
echo ""
echo "5. Для автозапуска настройте systemd service:"
echo "   sudo cp voice-assistant.service /etc/systemd/system/"
echo "   sudo nano /etc/systemd/system/voice-assistant.service"
echo "   sudo systemctl enable voice-assistant"
echo "   sudo systemctl start voice-assistant"
echo ""
echo "Документация: README.md"
echo ""
