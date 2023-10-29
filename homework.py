import logging
import os
import requests
import time

import telegram
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('SECRET_PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('SECRET_TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('SECRET_TG_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logging.basicConfig(
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)
logger.addHandler(
    logging.StreamHandler()
)


def check_tokens():
    """Проверяет доступность токенов."""
    tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    for token in tokens:
        if token is None:
            return False
        return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.error.BadRequest:
        logger.error('Ошибка при отправке сообщения!')


def get_api_answer(timestamp):
    """Делает запрос к API Яндекс.Практикума."""
    params = {'from_date': timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    response.raise_for_status()
    return response.json()


def check_response(response):
    """Проверяет ответ от API."""
    if 'homeworks' not in response or 'current_date' not in response:
        logging.error('Ответ не соответствует документации API')
        return False
    return True


def parse_status(homework):
    homework_name = homework.get('homework_name')
    status = homework.get('status')
    if homework_name is None or status is None:
        logging.error(
            'Информация о домашней работе не соответствует документации')
        return None
    verdict = HOMEWORK_VERDICTS.get(status)
    if verdict is None:
        logging.error(f'Неизвестный статус домашней работы: {status}')
        return None
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.error('Отсутствуют параметры окружения')
        return

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            api_response = get_api_answer(timestamp)
            if not check_response(api_response):
                continue
            homeworks = api_response.get('homeworks', [])
            if homeworks:
                message = parse_status(homeworks[0])
                if message is not None:
                    send_message(bot, message)
            timestamp = api_response.get('current_date', timestamp)
            time.sleep(RETRY_PERIOD)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            send_message(bot, message)
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
