class BotException(Exception):
    """Основной класс исключений работы бота."""

    def __init__(self, *args):
        self.message = args[0] if args else None

    def __str__(self):
        return f'Сбой в работе программы: {self.message}'


class TokenError(BotException):
    """Класс исключения при отсуствии переменной окружения."""

    pass


class RequestError(BotException):
    """Класс исключения при отправке запроса на эндпоинт."""

    pass


class ConnectionError(BotException):
    """Класс исключения при получения кода ответа от эндпоинт API."""

    pass


class ResponceError(BotException):
    """Класс исключения при неверном содержании ответа от эндпоинт API."""

    pass


class SendMessageError(BotException):
    """Класс исключения при отправке сообщения через Телеграм."""

    pass
