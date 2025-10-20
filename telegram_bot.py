# telegram_bot.py
# Основной файл телеграм-бота для мониторинга цен Aviasales

import telebot
from telebot import types
import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Set
import json
import os

from config import *
from aviasales_api import AviasalesAPI, validate_iata_code, get_popular_routes

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class FlightMonitorBot:
    """Класс телеграм-бота для мониторинга цен на авиабилеты"""

    def __init__(self, telegram_token: str, aviasales_token: str):
        self.bot = telebot.TeleBot(telegram_token)
        self.aviasales_api = AviasalesAPI(aviasales_token, AVIASALES_API_BASE_URL)

        # Хранилище пользовательских настроек
        self.user_settings: Dict[int, Dict] = {}
        self.active_monitors: Set[int] = set()

        # Блокировка для потокобезопасности
        self.lock = threading.Lock()

        # Загружаем настройки пользователей
        self.load_user_settings()

        # Регистрируем обработчики
        self.register_handlers()

        # Запускаем мониторинг
        self.start_monitoring_thread()

        logger.info("Бот инициализирован")

    def register_handlers(self):
        """Регистрация обработчиков команд и сообщений"""

        @self.bot.message_handler(commands=['start'])
        def handle_start(message):
            self.handle_start_command(message)

        @self.bot.message_handler(commands=['help'])
        def handle_help(message):
            self.handle_help_command(message)

        @self.bot.message_handler(commands=['set_route'])
        def handle_set_route(message):
            self.handle_set_route_command(message)

        @self.bot.message_handler(commands=['set_price'])
        def handle_set_price(message):
            self.handle_set_price_command(message)

        @self.bot.message_handler(commands=['set_days'])
        def handle_set_days(message):
            self.handle_set_days_command(message)

        @self.bot.message_handler(commands=['start_monitor'])
        def handle_start_monitor(message):
            self.handle_start_monitor_command(message)

        @self.bot.message_handler(commands=['stop_monitor'])
        def handle_stop_monitor(message):
            self.handle_stop_monitor_command(message)

        @self.bot.message_handler(commands=['status'])
        def handle_status(message):
            self.handle_status_command(message)

        @self.bot.message_handler(commands=['search'])
        def handle_search(message):
            self.handle_search_command(message)

        @self.bot.message_handler(commands=['routes'])
        def handle_routes(message):
            self.handle_routes_command(message)

        @self.bot.callback_query_handler(func=lambda call: True)
        def handle_callback(call):
            self.handle_callback_query(call)

    def handle_start_command(self, message):
        """Обработка команды /start"""
        user_id = message.from_user.id

        # Инициализируем настройки пользователя
        if user_id not in self.user_settings:
            self.user_settings[user_id] = {
                'origin': '',
                'destination': '',
                'max_price': DEFAULT_PRICE_THRESHOLD,
                'days_ahead': DEFAULT_DAYS_AHEAD,
                'currency': DEFAULT_CURRENCY,
                'last_check': None
            }

        welcome_text = f"""
🛫 Добро пожаловать в бот мониторинга цен Aviasales!

Я помогу вам отслеживать цены на авиабилеты и уведомлю, когда найдутся билеты дешевле установленного порога.

📋 Доступные команды:
/help - показать все команды
/set_route - установить маршрут (например: MOW LED)
/set_price - установить пороговую цену
/set_days - установить количество дней для поиска
/start_monitor - начать мониторинг цен
/stop_monitor - остановить мониторинг
/status - показать текущие настройки
/search - найти билеты прямо сейчас
/routes - показать популярные маршруты

🚀 Начните с команды /set_route чтобы установить маршрут!
        """

        self.bot.send_message(message.chat.id, welcome_text)

    def handle_help_command(self, message):
        """Обработка команды /help"""
        help_text = """
📖 Подробная справка по командам:

🛣️ /set_route <ОТКУДА> <КУДА>
Установить маршрут, используя IATA коды городов
Пример: /set_route MOW LED (Москва → Санкт-Петербург)

💰 /set_price <ЦЕНА>
Установить максимальную цену билета в рублях
Пример: /set_price 5000

📅 /set_days <КОЛИЧЕСТВО>
Установить на сколько дней вперед искать билеты
Пример: /set_days 30

▶️ /start_monitor
Начать автоматический мониторинг цен
Бот будет проверять цены каждый час

⏹️ /stop_monitor  
Остановить мониторинг цен

📊 /status
Показать текущие настройки мониторинга

🔍 /search
Найти билеты прямо сейчас по текущим настройкам

🗺️ /routes
Показать список популярных маршрутов с IATA кодами

💡 Совет: Используйте трёхбуквенные IATA коды городов (MOW, LED, NYC, LON и т.д.)
        """

        self.bot.send_message(message.chat.id, help_text)

    def handle_set_route_command(self, message):
        """Обработка команды /set_route"""
        user_id = message.from_user.id

        try:
            parts = message.text.split()
            if len(parts) != 3:
                self.bot.send_message(
                    message.chat.id,
                    "❌ Неверный формат команды.\n"
                    "Используйте: /set_route <ОТКУДА> <КУДА>\n"
                    "Пример: /set_route MOW LED"
                )
                return

            origin = parts[1].upper()
            destination = parts[2].upper()

            if not validate_iata_code(origin) or not validate_iata_code(destination):
                self.bot.send_message(
                    message.chat.id,
                    "❌ Неверные IATA коды. Используйте трёхбуквенные коды городов.\n"
                    "Пример: MOW (Москва), LED (Санкт-Петербург)\n\n"
                    "Посмотрите популярные маршруты: /routes"
                )
                return

            if origin == destination:
                self.bot.send_message(
                    message.chat.id,
                    "❌ Город отправления и назначения не могут быть одинаковыми"
                )
                return

            # Сохраняем настройки
            with self.lock:
                if user_id not in self.user_settings:
                    self.user_settings[user_id] = {}

                self.user_settings[user_id]['origin'] = origin
                self.user_settings[user_id]['destination'] = destination

            self.save_user_settings()

            routes = get_popular_routes()
            origin_name = routes.get(origin, origin)
            destination_name = routes.get(destination, destination)

            self.bot.send_message(
                message.chat.id,
                f"✅ Маршрут установлен: {origin_name} ({origin}) → {destination_name} ({destination})\n\n"
                f"Теперь установите пороговую цену: /set_price <цена>"
            )

        except Exception as e:
            logger.error(f"Error in set_route: {e}")
            self.bot.send_message(
                message.chat.id,
                "❌ Произошла ошибка при установке маршрута"
            )

    def handle_set_price_command(self, message):
        """Обработка команды /set_price"""
        user_id = message.from_user.id

        try:
            parts = message.text.split()
            if len(parts) != 2:
                self.bot.send_message(
                    message.chat.id,
                    "❌ Неверный формат команды.\n"
                    "Используйте: /set_price <цена>\n"
                    "Пример: /set_price 10000"
                )
                return

            try:
                price = float(parts[1])
                if price <= 0:
                    raise ValueError("Price must be positive")
            except ValueError:
                self.bot.send_message(
                    message.chat.id,
                    "❌ Неверная цена. Введите положительное число.\n"
                    "Пример: /set_price 10000"
                )
                return

            # Сохраняем настройки
            with self.lock:
                if user_id not in self.user_settings:
                    self.user_settings[user_id] = {}

                self.user_settings[user_id]['max_price'] = price

            self.save_user_settings()

            self.bot.send_message(
                message.chat.id,
                f"✅ Пороговая цена установлена: {price:,.0f} руб.\n\n"
                f"Теперь можете начать мониторинг: /start_monitor"
            )

        except Exception as e:
            logger.error(f"Error in set_price: {e}")
            self.bot.send_message(
                message.chat.id,
                "❌ Произошла ошибка при установке цены"
            )

    def handle_set_days_command(self, message):
        """Обработка команды /set_days"""
        user_id = message.from_user.id

        try:
            parts = message.text.split()
            if len(parts) != 2:
                self.bot.send_message(
                    message.chat.id,
                    "❌ Неверный формат команды.\n"
                    "Используйте: /set_days <количество>\n"
                    "Пример: /set_days 30"
                )
                return

            try:
                days = int(parts[1])
                if days <= 0 or days > 365:
                    raise ValueError("Days must be between 1 and 365")
            except ValueError:
                self.bot.send_message(
                    message.chat.id,
                    "❌ Неверное количество дней. Введите число от 1 до 365.\n"
                    "Пример: /set_days 30"
                )
                return

            # Сохраняем настройки
            with self.lock:
                if user_id not in self.user_settings:
                    self.user_settings[user_id] = {}

                self.user_settings[user_id]['days_ahead'] = days

            self.save_user_settings()

            self.bot.send_message(
                message.chat.id,
                f"✅ Период поиска установлен: {days} дней вперед"
            )

        except Exception as e:
            logger.error(f"Error in set_days: {e}")
            self.bot.send_message(
                message.chat.id,
                "❌ Произошла ошибка при установке периода"
            )

    def handle_start_monitor_command(self, message):
        """Обработка команды /start_monitor"""
        user_id = message.from_user.id

        # Проверяем настройки пользователя
        settings = self.user_settings.get(user_id, {})

        if not settings.get('origin') or not settings.get('destination'):
            self.bot.send_message(
                message.chat.id,
                "❌ Сначала установите маршрут: /set_route <ОТКУДА> <КУДА>\n"
                "Пример: /set_route MOW LED"
            )
            return

        if not settings.get('max_price'):
            self.bot.send_message(
                message.chat.id,
                "❌ Сначала установите пороговую цену: /set_price <цена>\n"
                "Пример: /set_price 10000"
            )
            return

        with self.lock:
            self.active_monitors.add(user_id)

        routes = get_popular_routes()
        origin_name = routes.get(settings['origin'], settings['origin'])
        destination_name = routes.get(settings['destination'], settings['destination'])

        self.bot.send_message(
            message.chat.id,
            f"✅ Мониторинг запущен!\n\n"
            f"🛣️ Маршрут: {origin_name} → {destination_name}\n"
            f"💰 Максимальная цена: {settings['max_price']:,.0f} руб.\n"
            f"📅 Период поиска: {settings.get('days_ahead', DEFAULT_DAYS_AHEAD)} дней\n\n"
            f"Я буду проверять цены каждый час и уведомлю вас о дешевых билетах!"
        )

        logger.info(f"Started monitoring for user {user_id}")

    def handle_stop_monitor_command(self, message):
        """Обработка команды /stop_monitor"""
        user_id = message.from_user.id

        with self.lock:
            if user_id in self.active_monitors:
                self.active_monitors.remove(user_id)
                self.bot.send_message(
                    message.chat.id,
                    "⏹️ Мониторинг остановлен"
                )
                logger.info(f"Stopped monitoring for user {user_id}")
            else:
                self.bot.send_message(
                    message.chat.id,
                    "ℹ️ Мониторинг не был активен"
                )

    def handle_status_command(self, message):
        """Обработка команды /status"""
        user_id = message.from_user.id
        settings = self.user_settings.get(user_id, {})

        if not settings:
            self.bot.send_message(
                message.chat.id,
                "ℹ️ Настройки не установлены. Начните с команды /start"
            )
            return

        routes = get_popular_routes()
        origin_name = routes.get(settings.get('origin', ''), settings.get('origin', 'Не установлен'))
        destination_name = routes.get(settings.get('destination', ''), settings.get('destination', 'Не установлен'))

        monitoring_status = "🟢 Активен" if user_id in self.active_monitors else "🔴 Остановлен"

        last_check = settings.get('last_check')
        last_check_text = "Никогда"
        if last_check:
            try:
                check_time = datetime.fromisoformat(last_check)
                last_check_text = check_time.strftime('%d.%m.%Y %H:%M')
            except:
                last_check_text = "Ошибка формата"

        status_text = f"""
📊 Текущие настройки:

🛣️ Маршрут: {origin_name} → {destination_name}
💰 Максимальная цена: {settings.get('max_price', 'Не установлена')} руб.
📅 Период поиска: {settings.get('days_ahead', DEFAULT_DAYS_AHEAD)} дней
💱 Валюта: {settings.get('currency', DEFAULT_CURRENCY)}

🔄 Статус мониторинга: {monitoring_status}
🕐 Последняя проверка: {last_check_text}
        """

        self.bot.send_message(message.chat.id, status_text)

    def handle_search_command(self, message):
        """Обработка команды /search"""
        user_id = message.from_user.id
        settings = self.user_settings.get(user_id, {})

        if not settings.get('origin') or not settings.get('destination'):
            self.bot.send_message(
                message.chat.id,
                "❌ Сначала установите маршрут: /set_route <ОТКУДА> <КУДА>"
            )
            return

        self.bot.send_message(message.chat.id, "🔍 Ищу билеты, подождите...")

        # Выполняем поиск
        flights = self.search_flights_for_user(user_id)

        if not flights:
            self.bot.send_message(
                message.chat.id,
                "😔 К сожалению, подходящих билетов не найдено"
            )
            return

        # Отправляем результаты (максимум 5 билетов)
        routes = get_popular_routes()
        origin_name = routes.get(settings['origin'], settings['origin'])
        destination_name = routes.get(settings['destination'], settings['destination'])

        response = f"✈️ Найдено билетов {origin_name} → {destination_name}:\n\n"

        for i, flight in enumerate(flights[:5], 1):
            flight_info = self.aviasales_api.format_flight_info(flight)
            response += f"{i}. {flight_info}\n\n"

        if len(flights) > 5:
            response += f"... и еще {len(flights) - 5} билетов"

        self.bot.send_message(message.chat.id, response)

    def handle_routes_command(self, message):
        """Обработка команды /routes"""
        routes = get_popular_routes()

        response = "🗺️ Популярные маршруты (IATA коды):\n\n"

        # Группируем по странам/регионам
        russian_cities = {}
        international_cities = {}

        for code, name in routes.items():
            if code in ['MOW', 'LED', 'KZN', 'SVX', 'NSK', 'ROV', 'KRR', 'UFA', 'VOG', 'SIP', 'AER', 'MRV']:
                russian_cities[code] = name
            else:
                international_cities[code] = name

        response += "🇷🇺 Россия:\n"
        for code, name in russian_cities.items():
            response += f"• {code} - {name}\n"

        response += "\n🌍 Международные:\n"
        for code, name in international_cities.items():
            response += f"• {code} - {name}\n"

        response += "\n💡 Используйте: /set_route <КОД_ОТКУДА> <КОД_КУДА>"

        self.bot.send_message(message.chat.id, response)

    def handle_callback_query(self, call):
        """Обработка callback запросов от inline кнопок"""
        # Здесь можно добавить обработку callback кнопок
        pass

    def search_flights_for_user(self, user_id: int) -> List[Dict]:
        """Поиск рейсов для конкретного пользователя"""
        settings = self.user_settings.get(user_id, {})

        if not settings.get('origin') or not settings.get('destination'):
            return []

        try:
            flights = self.aviasales_api.get_cheapest_flights(
                origin=settings['origin'],
                destination=settings['destination'],
                days_ahead=settings.get('days_ahead', DEFAULT_DAYS_AHEAD),
                currency=settings.get('currency', DEFAULT_CURRENCY),
                max_price=settings.get('max_price')
            )

            # Обновляем время последней проверки
            with self.lock:
                self.user_settings[user_id]['last_check'] = datetime.now().isoformat()

            return flights

        except Exception as e:
            logger.error(f"Error searching flights for user {user_id}: {e}")
            return []

    def start_monitoring_thread(self):
        """Запуск потока мониторинга"""
        def monitor_prices():
            logger.info("Price monitoring thread started")

            while True:
                try:
                    # Копируем список активных мониторов для безопасности
                    with self.lock:
                        active_users = self.active_monitors.copy()

                    for user_id in active_users:
                        try:
                            flights = self.search_flights_for_user(user_id)

                            if flights:
                                settings = self.user_settings.get(user_id, {})
                                routes = get_popular_routes()
                                origin_name = routes.get(settings['origin'], settings['origin'])
                                destination_name = routes.get(settings['destination'], settings['destination'])

                                # Отправляем уведомление о найденных билетах
                                message = f"🎉 Найдены дешевые билеты {origin_name} → {destination_name}!\n\n"

                                # Показываем топ-3 самых дешевых
                                for i, flight in enumerate(flights[:3], 1):
                                    flight_info = self.aviasales_api.format_flight_info(flight)
                                    message += f"{i}. {flight_info}\n\n"

                                if len(flights) > 3:
                                    message += f"Всего найдено: {len(flights)} билетов\n"
                                    message += "Используйте /search для просмотра всех результатов"

                                self.bot.send_message(user_id, message)
                                logger.info(f"Sent notification to user {user_id}")

                            # Небольшая пауза между пользователями
                            time.sleep(2)

                        except Exception as e:
                            logger.error(f"Error monitoring user {user_id}: {e}")

                    # Сохраняем настройки после проверок
                    self.save_user_settings()

                    # Ждем до следующей проверки
                    time.sleep(CHECK_INTERVAL)

                except Exception as e:
                    logger.error(f"Error in monitoring thread: {e}")
                    time.sleep(60)  # При ошибке ждем минуту

        # Запускаем поток мониторинга
        monitor_thread = threading.Thread(target=monitor_prices, daemon=True)
        monitor_thread.start()

    def save_user_settings(self):
        """Сохранение настроек пользователей в файл"""
        try:
            with open('user_settings.json', 'w', encoding='utf-8') as f:
                # Преобразуем set в list для JSON
                data = {
                    'user_settings': self.user_settings,
                    'active_monitors': list(self.active_monitors)
                }
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving user settings: {e}")

    def load_user_settings(self):
        """Загрузка настроек пользователей из файла"""
        try:
            if os.path.exists('user_settings.json'):
                with open('user_settings.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)

                    self.user_settings = data.get('user_settings', {})
                    # Преобразуем user_id из строк в int
                    self.user_settings = {int(k): v for k, v in self.user_settings.items()}

                    self.active_monitors = set(data.get('active_monitors', []))

                logger.info(f"Loaded settings for {len(self.user_settings)} users")
        except Exception as e:
            logger.error(f"Error loading user settings: {e}")

    def run(self):
        """Запуск бота"""
        logger.info("Starting bot...")
        try:
            self.bot.infinity_polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            logger.error(f"Bot polling error: {e}")
            time.sleep(10)
            self.run()  # Перезапускаем при ошибке

def main():
    """Главная функция"""

    # Проверяем наличие токенов
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("❌ Ошибка: Не установлен TELEGRAM_BOT_TOKEN в config.py")
        return

    if not AVIASALES_API_TOKEN or AVIASALES_API_TOKEN == "YOUR_AVIASALES_API_TOKEN_HERE":
        print("❌ Ошибка: Не установлен AVIASALES_API_TOKEN в config.py")
        return

    # Создаем и запускаем бота
    bot = FlightMonitorBot(TELEGRAM_BOT_TOKEN, AVIASALES_API_TOKEN)
    bot.run()

if __name__ == "__main__":
    main()
