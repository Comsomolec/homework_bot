class TokenError(Exception):
    """Класс исключения при отсуствии переменной окружения."""

    pass


class ResponceError(Exception):
    """Класс исключения при неверном содержании ответа от эндпоинт API."""

    pass


class SendMessageError(Exception):
    """Класс исключения при отправке сообщения через Телеграм."""

    pass
