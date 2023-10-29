import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import ResponseCodeError

load_dotenv()


PRACTICUM_TOKEN = os.getenv('SECRET_PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('SECRET_TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('SECRET_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logger = logging.getLogger(__name__)
logger.addHandler(
    logging.StreamHandler()
)


def check_tokens():
    """Проверяет доступность токенов."""
    tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    return all(tokens)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение успешно отправлено в Telegram')
    except Exception as e:
        logger.error(f'Ошибка при отправке сообщения: {e}')


def get_api_answer(timestamp):
    """Делает запрос к API Яндекс.Практикума."""
    params = {'from_date': timestamp}
    params_dict = dict(url=ENDPOINT, headers=HEADERS, params=params)
    try:
        response = requests.get(**params_dict)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f'Ошибка при запросе к API: {e}')
    else:
        if response.status_code != HTTPStatus.OK:
            raise ResponseCodeError(f'Запрос к API '
                                    f'вернул код {response.status_code}')
        return response.json()


def check_response(response: dict):
    """Проверяет ответ от API."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является dict')
    if not isinstance(response.get('homeworks'),
                      list) or 'current_date' not in response:
        raise TypeError('Ответ не соответствует документации API')
    return True


def parse_status(homework):
    """Извлекает статус домашней работы."""
    homework_name = homework.get('homework_name')
    if homework_name is None:
        raise KeyError('Ответ API не содержит ключ "homework_name"')
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Недокументированный статус домашней работы: '
                         f'{status}')
    verdict = HOMEWORK_VERDICTS.get(status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствует токен.')
        sys.exit('Отсутствует токен.')
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
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s, %(levelname)s, %(message)s, %(name)s',
        level=logging.DEBUG)
    main()
