import logging
import os
import requests
import telegram
import time
import sys
from dotenv import load_dotenv
from http import HTTPStatus
from logging.handlers import RotatingFileHandler
from exceptions import (
    RequestError,
    ConnectionError,
    ResponceError,
    TokenError,
    SendMessageError
)


load_dotenv()
PRACTICUM_TOKEN = os.getenv('TOKEN_YP')
TELEGRAM_TOKEN = os.getenv('TOKEN_BOT_TG')
TELEGRAM_CHAT_ID = int(os.getenv('TG_CHAT_ID'))

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s, %(levelname)s, %(message)s'
)
handler_file = RotatingFileHandler(
    'main.log', maxBytes=50000000, backupCount=5, encoding='utf-8'
)
handler_terminal = logging.StreamHandler(sys.stdout)
handler_file.setFormatter(formatter)
handler_terminal.setFormatter(formatter)
logger.addHandler(handler_file)
logger.addHandler(handler_terminal)


def check_tokens():
    """Проверяем доступность переменных окружения - Токенов."""
    tokens = {
        'practicim_token': PRACTICUM_TOKEN,
        'telegram_token': TELEGRAM_TOKEN,
        'telegram_chat_id': TELEGRAM_CHAT_ID,
    }
    for key, token in tokens.items():
        if token is None:
            logger.critical(f'Токен {key} отсутствует.')
            raise TokenError(f'Токен {key} отсутствует.')
    logger.info('Токены валидны.')
    return True


def send_message(bot, message):
    """Отправляем сообщение в телеграмм."""
    try:
        logger.debug(f'Сообщение успешно отправлено: {message}')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.TelegramError as err:
        logger.error(f'Сбой при отправке сообщения: {message}')
        raise SendMessageError(f'Сбой при отправке сообщения: {err}')


def get_api_answer(timestamp):
    """Отправляем запрос к endpoint API Yandex.Practicum."""
    payload = {'from_date': timestamp}
    try:
        logger.info('Отправлен запрос на endpoint API Yandex.Practicum')
        response = requests.get(
            ENDPOINT, headers=HEADERS, params=payload
        )
    except requests.exceptions.RequestException as err:
        logger.error(
            f'При попытке отправить запрос на эндпоинт возникла ошибка: {err}'
        )
        raise RequestError(
            f'При попытке отправить запрос на эндпоинт возникла ошибка: {err}'
        )

    if response.status_code != HTTPStatus.OK:
        logger.error(
            f'Эндпоинт {ENDPOINT} недоступен.'
            f'Код ответа:{response.status_code}'
        )
        raise ConnectionError(
            f'Эндпоинт {ENDPOINT} недоступен.'
            f'Код ответа:{response.status_code}'
        )
    return response.json()


def check_response(response):
    """Проверяем ответ от эндпоинт API на соответствие документации."""
    keys_response_dict = ['current_date', 'homeworks']
    if response is None:
        logger.error('От API пришел пустой ответ.')
        raise ResponceError('От API пришел пустой ответ.')
    if not isinstance(response, dict):
        logger.error('Ответ не соответствует типу данных.')
        raise TypeError('Ответ не соответствует типу данных.')
    for key in keys_response_dict:
        if key not in response:
            logger.error(f'В ответе API не найден ключ {key}.')
            raise KeyError(f'В ответе API не найден ключ {key}.')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        logger.error('Ответ не соответствует типу данных.')
        raise TypeError('Ответ не соответствует типу данных.')
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
        raise KeyError
    homework_name = homework['homework_name']
    status = homework['status']

    try:
        verdict = HOMEWORK_VERDICTS[status]
        return (
            f'Изменился статус проверки работы "{homework_name}".'
            f'{verdict}'
        )
    except KeyError as err:
        logger.error(
            f'Статус проверки домашней работы не определен. {err}'
        )
        raise ResponceError(
            f'Статус проверки домашней работы не определен. {err}'
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
            homeworks_list = check_response(response)
            try:
                message = parse_status(homeworks_list[0])
                if message != last_message:
                    send_message(bot, message)
                    last_message = message
                else:
                    logger.debug('Статус домашней работы не изменился.')
            except IndexError:
                logger.warning('Домашняя работа на проверку не отправлена.')
            timestamp = int(time.time())
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(f'Уведомление об ошибке отправлено в чат. {message}')
            if str(error) != last_error_message:
                send_message(bot, message)
                last_error_message = str(error)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
