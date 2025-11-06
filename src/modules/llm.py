"""
LLM Integration module using HuggingFace Transformers
Интеграция с языковой моделью для генерации ответов
"""

import logging
import torch
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    BitsAndBytesConfig,
    pipeline
)

logger = logging.getLogger(__name__)


class LLMEngine:
    """Класс для работы с языковой моделью"""

    def __init__(self, config):
        """
        Инициализация LLM движка

        Args:
            config: Словарь с конфигурацией из config.yaml
        """
        self.config = config
        self.llm_config = config['llm']

        self.model = None
        self.tokenizer = None
        self.pipeline = None
        self.conversation_history = []

        self._load_model()

    def _load_model(self):
        """Загрузка модели и токенизатора"""
        model_name = self.llm_config['model_name']
        logger.info(f"Загрузка модели: {model_name}")

        try:
            # Настройка квантизации для экономии памяти
            quantization_config = None

            if self.llm_config.get('load_in_4bit', False):
                logger.info("Использование 4-bit квантизации")
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4"
                )
            elif self.llm_config.get('load_in_8bit', False):
                logger.info("Использование 8-bit квантизации")
                quantization_config = BitsAndBytesConfig(
                    load_in_8bit=True
                )

            # Загрузка токенизатора
            logger.info("Загрузка токенизатора...")
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                trust_remote_code=True
            )

            # Загрузка модели
            logger.info("Загрузка модели (это может занять несколько минут)...")
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                quantization_config=quantization_config,
                device_map=self.llm_config.get('device_map', 'auto'),
                trust_remote_code=True,
                torch_dtype=torch.float16 if quantization_config else torch.float32,
                low_cpu_mem_usage=True
            )

            # Создание pipeline для удобной генерации
            self.pipeline = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
                device_map=self.llm_config.get('device_map', 'auto')
            )

            logger.info("Модель успешно загружена")

            # Вывод информации о памяти
            if torch.cuda.is_available():
                memory_allocated = torch.cuda.memory_allocated() / 1024**3
                logger.info(f"GPU память использовано: {memory_allocated:.2f} GB")

        except Exception as e:
            logger.error(f"Ошибка при загрузке модели: {e}")
            logger.info("Попробуйте использовать более легкую модель или включить квантизацию")
            raise

    def generate_response(self, user_input, use_history=True):
        """
        Генерация ответа на запрос пользователя

        Args:
            user_input: Текст запроса пользователя
            use_history: Использовать историю разговора

        Returns:
            str: Ответ модели
        """
        if not user_input or not user_input.strip():
            return "Извините, я не расслышал вопрос."

        logger.info(f"Запрос пользователя: {user_input}")

        try:
            # Формирование промпта
            prompt = self._build_prompt(user_input, use_history)

            # Генерация ответа
            response = self._generate(prompt)

            # Сохранение в историю
            if use_history:
                self.conversation_history.append({
                    "role": "user",
                    "content": user_input
                })
                self.conversation_history.append({
                    "role": "assistant",
                    "content": response
                })

                # Ограничение длины истории
                max_history = 10
                if len(self.conversation_history) > max_history:
                    self.conversation_history = self.conversation_history[-max_history:]

            logger.info(f"Ответ модели: {response}")
            return response

        except Exception as e:
            logger.error(f"Ошибка при генерации ответа: {e}")
            return "Извините, произошла ошибка при обработке вашего запроса."

    def _build_prompt(self, user_input, use_history):
        """
        Построение промпта для модели

        Args:
            user_input: Текст запроса
            use_history: Использовать историю

        Returns:
            str: Сформированный промпт
        """
        system_prompt = self.llm_config.get('system_prompt', '')

        # Формат промпта зависит от модели
        # Для русских моделей типа Saiga используется формат:
        # <s>system\nПромпт</s><s>user\nВопрос</s><s>assistant\n

        prompt_parts = []

        # Системный промпт
        if system_prompt:
            prompt_parts.append(f"<s>system\n{system_prompt}</s>")

        # История разговора
        if use_history and self.conversation_history:
            for msg in self.conversation_history[-6:]:  # Последние 3 обмена
                role = msg['role']
                content = msg['content']
                prompt_parts.append(f"<s>{role}\n{content}</s>")

        # Текущий запрос
        prompt_parts.append(f"<s>user\n{user_input}</s>")
        prompt_parts.append("<s>assistant\n")

        prompt = "".join(prompt_parts)

        logger.debug(f"Промпт: {prompt[:200]}...")
        return prompt

    def _generate(self, prompt):
        """
        Генерация текста моделью

        Args:
            prompt: Промпт для модели

        Returns:
            str: Сгенерированный текст
        """
        # Параметры генерации
        generation_params = {
            'max_new_tokens': self.llm_config.get('max_new_tokens', 256),
            'temperature': self.llm_config.get('temperature', 0.7),
            'top_p': self.llm_config.get('top_p', 0.9),
            'top_k': self.llm_config.get('top_k', 50),
            'repetition_penalty': self.llm_config.get('repetition_penalty', 1.1),
            'do_sample': self.llm_config.get('do_sample', True),
            'pad_token_id': self.tokenizer.eos_token_id,
        }

        # Генерация
        outputs = self.pipeline(
            prompt,
            **generation_params,
            return_full_text=False
        )

        # Извлечение ответа
        generated_text = outputs[0]['generated_text']

        # Очистка ответа (удаление служебных токенов)
        response = self._clean_response(generated_text)

        return response

    def _clean_response(self, text):
        """
        Очистка ответа от служебных токенов и форматирования

        Args:
            text: Сырой текст от модели

        Returns:
            str: Очищенный текст
        """
        # Удаление служебных токенов
        text = text.replace("<s>", "").replace("</s>", "")
        text = text.replace("<|im_start|>", "").replace("<|im_end|>", "")

        # Удаление префиксов ролей
        for role in ["assistant\n", "user\n", "system\n"]:
            if text.startswith(role):
                text = text[len(role):]

        # Обрезка по первой новой строке если ответ многострочный
        # (для коротких голосовых ответов)
        lines = text.strip().split('\n')
        if len(lines) > 1 and len(lines[0]) > 20:
            text = lines[0]

        return text.strip()

    def reset_conversation(self):
        """Сбросить историю разговора"""
        self.conversation_history = []
        logger.info("История разговора сброшена")

    def get_model_info(self):
        """Получить информацию о модели"""
        if self.model is None:
            return "Модель не загружена"

        info = {
            "model_name": self.llm_config['model_name'],
            "parameters": sum(p.numel() for p in self.model.parameters()) / 1e9,
            "device": str(self.model.device),
        }

        if torch.cuda.is_available():
            info["gpu_memory_gb"] = torch.cuda.memory_allocated() / 1024**3

        return info


class SimpleLLM:
    """
    Простой резервный LLM на основе правил
    Используется если основная модель недоступна
    """

    def __init__(self, config):
        self.config = config
        self.conversation_history = []
        logger.warning("Используется упрощенный LLM на основе правил")

    def generate_response(self, user_input, use_history=True):
        """Генерация простого ответа на основе правил"""
        user_input = user_input.lower()

        # Простые правила ответов
        if "привет" in user_input or "здравствуй" in user_input:
            return "Привет! Чем могу помочь?"

        elif "как дела" in user_input or "как ты" in user_input:
            return "У меня все хорошо, спасибо! Чем могу быть полезен?"

        elif "спасибо" in user_input:
            return "Пожалуйста, рад помочь!"

        elif "пока" in user_input or "до свидания" in user_input:
            return "До свидания! Обращайтесь если что-то понадобится."

        elif "время" in user_input or "который час" in user_input:
            from datetime import datetime
            now = datetime.now()
            return f"Сейчас {now.strftime('%H:%M')}"

        elif "дата" in user_input or "какое число" in user_input:
            from datetime import datetime
            now = datetime.now()
            return f"Сегодня {now.strftime('%d.%m.%Y')}"

        else:
            return "Извините, я пока не могу ответить на этот вопрос. Попробуйте переформулировать."

    def reset_conversation(self):
        """Сбросить историю"""
        self.conversation_history = []


if __name__ == "__main__":
    # Тестирование модуля
    import yaml

    logging.basicConfig(level=logging.INFO)

    with open("../config/config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    try:
        llm = LLMEngine(config)
        print(f"\n=== Информация о модели ===")
        print(llm.get_model_info())
    except Exception as e:
        print(f"Не удалось загрузить основную модель: {e}")
        print("Использую SimpleLLM")
        llm = SimpleLLM(config)

    print("\n=== Тест генерации ответов ===")
    test_queries = [
        "Привет! Как дела?",
        "Который час?",
        "Расскажи о погоде",
    ]

    for query in test_queries:
        print(f"\nПользователь: {query}")
        response = llm.generate_response(query)
        print(f"Ассистент: {response}")
