from http import HTTPStatus
from logging.handlers import RotatingFileHandler
import logging
import os
import sys
import time

from dotenv import load_dotenv
import requests
import telegram

from exceptions import (
    ResponceError,
    SendMessageError,
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
VERDICT = (
    'Изменился статус проверки работы "{homework_name}": "{status}". {verdict}'
)
TOKEN_ERROR = 'Токены {tokens} отсутствуют'
TOKEN_VALID = 'Токены валидны'
DEBUG_SEND_MESSAGE = 'Сообщение успешно отправлено: {message}'
ERROR_SEND_MESSAGE = (
    'Сбой при отправке сообщения в телеграм: {message}.{error}'
)
ENDPOINT_RESPONSE_ERROR = (
    'Ошибка при отправке запрос на эндпоинт {url}: {error}. '
    'Параметры запроса: headers={headers}, params={params}'
)
ENDPOINT_REQUEST_CODE_ERROR = (
    'Эндпоинт {url} недоступен. Код ответа:{code}. '
    'Параметры запроса: headers={headers}, params={params}'
)
ENDPOINT_REQUEST_ERROR = (
    'Эндпоинт {url} недоступен. '
    'Код ответа:{code}. '
    'Ошибка: {error}. '
    'Параметры запроса: headers={headers}, params={params}'
)
RESPONSE_TYPE_ERROR = (
    'Ответ не соответствует типу данных. Вместо dict -> {type}'
)
KEY_HOMEWORKS_NOT_FOUND = 'В ответе API не найден ключ "homeworks"'
KEY_IN_DICT_HOMEWORK_NOT_FOUND = (
    'Ключ {key} отсутствует в dict(homework)'
)
CHECK_STATUS_UNDEFINED = (
    'Статус проверки домашней работы не определен -> {status}'
)
STATUS_DEBUG = 'Статус домашней работы не изменился.'
HOMEWORK_NOT_SUBMITTED = 'Домашняя работа на проверку не отправлена.'
EXCEPTION_MESSAGE = 'Сбой в работе программы: {error}'
EXCEPTION_MESSAGE_NOT_SUBMITTED = (
    'Сообщение в телеграм чат не отправлено. {error}'
)
logger = logging.getLogger(__name__)


def check_tokens():
    """Проверяем доступность переменных окружения - Токенов."""
    tokens = [name for name in TOKENS if globals()[name] is None]
    if tokens:
        logger.critical(TOKEN_ERROR.format(tokens=tokens))
        raise ValueError(TOKEN_ERROR.format(tokens=tokens))
    logger.info(TOKEN_VALID)


def send_message(bot, message):
    """Отправляем сообщение в телеграмм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(DEBUG_SEND_MESSAGE.format(message=message))
    except telegram.TelegramError as error:
        logger.exception(
            ERROR_SEND_MESSAGE.format(message=message, error=error)
        )
        raise SendMessageError(
            ERROR_SEND_MESSAGE.format(message=message, error=error)
        )


def get_api_answer(timestamp):
    """Отправляем запрос к endpoint API Yandex.Practicum."""
    payload = {'from_date': timestamp}
    response_check = {'code': None, 'error': None}
    request_parameters = dict(url=ENDPOINT, headers=HEADERS, params=payload)
    try:
        response = requests.get(**request_parameters)
    except requests.exceptions.RequestException as error:
        raise ConnectionError(
            ENDPOINT_RESPONSE_ERROR.format(error=error, **request_parameters)
        )
    if response.status_code != HTTPStatus.OK:
        raise ResponceError(
            ENDPOINT_REQUEST_CODE_ERROR.format(
                code=response.status_code, **request_parameters
            )
        )
    response = response.json()
    for key in response_check:
        if key in response:
            response_check[key] = response[key]
    if (response_check['code'] is not None) and (
            response_check['error'] is not None):
        raise ResponceError(
            ENDPOINT_REQUEST_ERROR.format(
                code=response_check['code'], error=response_check['error'],
                **request_parameters
            )
        )
    return response


def check_response(response):
    """Проверяем ответ от эндпоинт API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError(RESPONSE_TYPE_ERROR.format(type=type(response)))
    if 'homeworks' not in response:
        raise KeyError(KEY_HOMEWORKS_NOT_FOUND)
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(RESPONSE_TYPE_ERROR.format(type=type(homeworks)))
    return homeworks


def parse_status(homework):
    """Проверка статуса проверки домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError(
            KEY_IN_DICT_HOMEWORK_NOT_FOUND.format(key="homework_name")
        )
    if 'status' not in homework:
        raise KeyError(
            KEY_IN_DICT_HOMEWORK_NOT_FOUND.format(key="status")
        )
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(CHECK_STATUS_UNDEFINED.format(status=status))
    return VERDICT.format(
        homework_name=homework['homework_name'],
        status=status,
        verdict=HOMEWORK_VERDICTS[status]
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
                    logger.debug(STATUS_DEBUG)
            else:
                logger.debug(HOMEWORK_NOT_SUBMITTED)
            timestamp = response['current_date']
        except Exception as error:
            message = EXCEPTION_MESSAGE.format(error=error)
            logger.error(message)
            if message != last_error_message:
                try:
                    send_message(bot, message)
                    last_error_message = message
                except Exception as error_message:
                    logger.critical(EXCEPTION_MESSAGE_NOT_SUBMITTED.format(
                        error=error_message
                    ))
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format=('%(asctime)s, %(levelname)s, Функция: %(funcName)s, '
                'Строка: %(lineno)d, %(message)s.'),
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

    main()
