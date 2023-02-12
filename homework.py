from http import HTTPStatus
import logging
from logging.handlers import RotatingFileHandler
import os
import sys
import time

from dotenv import load_dotenv
import requests
import telegram

from exceptions import (
    ResponceError,
    SendMessageError,
    TokenError
)

load_dotenv()
PRACTICUM_TOKEN = os.getenv('TOKEN_YP')
TELEGRAM_TOKEN = os.getenv('TOKEN_BOT_TG')
TELEGRAM_CHAT_ID = os.getenv('TG_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}
TOKENS = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']
VERDICT_PHRASE = (
    'Изменился статус проверки работы "{homework_name}": "{status}". {verdict}'
)
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format=('%(asctime)s, %(levelname)s, %(message)s, '
            'Функция: %(funcName)s, Строка: %(lineno)d'),
    handlers=[
        RotatingFileHandler(
            __file__ + '.log',
            maxBytes=50000000,
            backupCount=5,
            encoding='utf-8'
        ),
        logging.StreamHandler(sys.stdout)
    ]
)


def check_tokens():
    """Проверяем доступность переменных окружения - Токенов."""
    names = []
    for name in TOKENS:
        if globals()[name] is None:
            names.append(name)
            logger.critical(f'Токен {name} отсутствует.')
    if names:
        raise TokenError(f'Токены {",".join(names)} отсутствует.')
    logger.info('Токены валидны.')


def send_message(bot, message):
    """Отправляем сообщение в телеграмм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Сообщение успешно отправлено: {message}')
    except telegram.TelegramError as error:
        logger.exception(
            f'Сбой при отправке сообщения в телеграм: {message}.{error}'
        )
        raise SendMessageError(
            f'Сбой при отправке сообщения в телеграм: {message}.{error}'
        )


def get_api_answer(timestamp):
    """Отправляем запрос к endpoint API Yandex.Practicum."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params=payload
        )
    except requests.exceptions.RequestException as error:
        raise Exception(
            f'Ошибка при отправке запрос на эндпоинт: {error}. '
            f'Параметры запроса: '
            f'{ENDPOINT}, headers={HEADERS}, params={payload}'
        )
    if response.status_code != HTTPStatus.OK:
        raise ResponceError(
            f'Эндпоинт {ENDPOINT} недоступен. '
            f'Код ответа:{response.status_code}. '
            f'Параметры запроса: '
            f'{ENDPOINT}, headers={HEADERS}, params={payload}.'
        )
    return response.json()


def check_response(response):
    """Проверяем ответ от эндпоинт API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError(
            f'Ответ не соответствует типу данных. '
            f'Вместо dict -> {type(response)}.'
        )
    if 'homeworks' not in response:
        raise KeyError('В ответе API не найден ключ "homeworks".')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(
            f'Ответ не соответствует типу данных. '
            f'Вместо list -> {type(response)}.'
        )
    return homeworks


def parse_status(homework):
    """Проверка статуса проверки домашней работы."""
    # keys_homework_dict = [
    #     'id',
    #     'status',
    #     'homework_name',
    #     'reviewer_comment',
    #     'date_updated',
    #     'lesson_name'
    # ]
    # for key in keys_homework_dict:
    #     if key not in homework:
    #         logger.error(f'В ответе API не найден ключ {key}.')
    #         raise KeyError(f'В ответе API не найден ключ {key}.')
    # Данная конструкция не проходит тесты ЯП. (?)
    if 'homework_name' not in homework:
        raise KeyError('Ключ "homework_name" отсутствует в dict(homework)')
    if 'status' not in homework:
        raise KeyError('Ключ "status" отсутствует в dict(homework)')
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise KeyError(
            f'Статус проверки домашней работы не определен -> {status}'
        )
    verdict = HOMEWORK_VERDICTS[status]
    return VERDICT_PHRASE.format(
        homework_name=homework['homework_name'], status=status, verdict=verdict
    )


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = ''
    last_error_message = ''
    while True:
        try:
            response = get_api_answer(timestamp - RETRY_PERIOD)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                if message != last_message:
                    send_message(bot, message)
                    last_message = message
                else:
                    logger.debug('Статус домашней работы не изменился.')
            else:
                logger.warning('Домашняя работа на проверку не отправлена.')
            timestamp = response['current_date']
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != last_error_message:
                try:
                    send_message(bot, message)
                    last_error_message = message
                except Exception as error_message:
                    logger.critical(
                        f'Сообщение в телеграм чат не отправлено. '
                        f'{error_message}'
                    )
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
