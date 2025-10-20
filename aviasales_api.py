# aviasales_api.py
# Модуль для работы с API Aviasales

import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

class AviasalesAPI:
    """Класс для работы с API Aviasales"""

    def __init__(self, api_token: str, base_url: str):
        self.api_token = api_token
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'X-Access-Token': api_token,
            'Accept-Encoding': 'gzip, deflate',
            'Content-Type': 'application/json'
        })

    def get_prices_for_dates(self, origin: str, destination: str, 
                           departure_date: str, return_date: str = None,
                           currency: str = "RUB", limit: int = 30) -> Dict:
        """
        Получить цены на билеты для определенных дат

        Args:
            origin: IATA код города отправления (например, MOW)
            destination: IATA код города назначения (например, LED)
            departure_date: Дата отправления в формате YYYY-MM-DD
            return_date: Дата возвращения в формате YYYY-MM-DD (опционально)
            currency: Валюта цен (RUB, USD, EUR)
            limit: Количество результатов

        Returns:
            Dict с данными о ценах или None при ошибке
        """

        params = {
            'origin': origin.upper(),
            'destination': destination.upper(),
            'departure_at': departure_date,
            'currency': currency,
            'limit': limit,
            'one_way': return_date is None,
            'sorting': 'price',
            'direct': False,
            'token': self.api_token
        }

        if return_date:
            params['return_at'] = return_date
            params['one_way'] = False

        try:
            response = self.session.get(self.base_url, params=params)
            response.raise_for_status()

            data = response.json()

            if data.get('success', False):
                return data
            else:
                logging.error(f"API error: {data.get('error', 'Unknown error')}")
                return None

        except requests.exceptions.RequestException as e:
            logging.error(f"Request error: {e}")
            return None
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error: {e}")
            return None

    def get_cheapest_flights(self, origin: str, destination: str, 
                           days_ahead: int = 30, currency: str = "RUB",
                           max_price: float = None) -> List[Dict]:
        """
        Получить самые дешевые рейсы на указанное количество дней вперед

        Args:
            origin: IATA код города отправления
            destination: IATA код города назначения  
            days_ahead: Количество дней для поиска
            currency: Валюта
            max_price: Максимальная цена для фильтрации

        Returns:
            Список рейсов, отсортированных по цене
        """

        flights = []
        start_date = datetime.now() + timedelta(days=1)  # Начинаем с завтрашнего дня

        for i in range(days_ahead):
            search_date = start_date + timedelta(days=i)
            date_str = search_date.strftime('%Y-%m-%d')

            data = self.get_prices_for_dates(origin, destination, date_str, currency=currency)

            if data and data.get('data'):
                for flight in data['data']:
                    # Фильтруем по максимальной цене, если задана
                    if max_price is None or flight.get('price', float('inf')) <= max_price:
                        flight['search_date'] = date_str
                        flights.append(flight)

        # Сортируем по цене
        flights.sort(key=lambda x: x.get('price', float('inf')))

        return flights

    def format_flight_info(self, flight: Dict) -> str:
        """
        Форматировать информацию о рейсе для отображения

        Args:
            flight: Словарь с данными о рейсе

        Returns:
            Отформатированная строка с информацией о рейсе
        """

        price = flight.get('price', 'N/A')
        origin = flight.get('origin', 'N/A')
        destination = flight.get('destination', 'N/A')
        airline = flight.get('airline', 'N/A')
        departure_at = flight.get('departure_at', 'N/A')
        return_at = flight.get('return_at', '')
        transfers = flight.get('transfers', 0)

        # Форматируем дату
        try:
            if departure_at != 'N/A':
                dep_date = datetime.fromisoformat(departure_at.replace('Z', '+00:00'))
                dep_formatted = dep_date.strftime('%d.%m.%Y %H:%M')
            else:
                dep_formatted = 'N/A'
        except:
            dep_formatted = departure_at

        # Форматируем обратную дату
        ret_formatted = ''
        if return_at:
            try:
                ret_date = datetime.fromisoformat(return_at.replace('Z', '+00:00'))
                ret_formatted = f"\nВозвращение: {ret_date.strftime('%d.%m.%Y %H:%M')}"
            except:
                ret_formatted = f"\nВозвращение: {return_at}"

        transfers_text = "Прямой" if transfers == 0 else f"{transfers} пересадка(и)"

        return f"""✈️ {origin} → {destination}
💰 Цена: {price:,} руб.
🛫 Отправление: {dep_formatted}{ret_formatted}
🏢 Авиакомпания: {airline}
🔄 {transfers_text}"""

def validate_iata_code(code: str) -> bool:
    """
    Проверить валидность IATA кода

    Args:
        code: IATA код для проверки

    Returns:
        True если код валидный, False иначе
    """
    return isinstance(code, str) and len(code) == 3 and code.isalpha()

def get_popular_routes() -> Dict[str, str]:
    """
    Получить список популярных маршрутов с IATA кодами

    Returns:
        Словарь с популярными маршрутами
    """
    return {
        'MOW': 'Москва',
        'LED': 'Санкт-Петербург', 
        'KZN': 'Казань',
        'SVX': 'Екатеринбург',
        'NSK': 'Новосибирск',
        'ROV': 'Ростов-на-Дону',
        'KRR': 'Краснодар',
        'UFA': 'Уфа',
        'VOG': 'Волгоград',
        'SIP': 'Симферополь',
        'AER': 'Сочи',
        'MRV': 'Минеральные Воды',
        'NYC': 'Нью-Йорк',
        'LON': 'Лондон',
        'PAR': 'Париж',
        'ROM': 'Рим',
        'BCN': 'Барселона',
        'BER': 'Берлин',
        'IST': 'Стамбул',
        'DXB': 'Дубай',
        'BKK': 'Бангкок',
        'HKT': 'Пхукет'
    }
