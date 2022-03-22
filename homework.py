import os
import time
import logging
import requests
from requests.exceptions import RequestException
from http import HTTPStatus
from dotenv import load_dotenv

import telegram
from telegram import TelegramError

from exceptions import BotException
load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}
logger = logging.getLogger(__name__)


def send_message(bot, message):
    """Send message to chat."""
    try:
        logging.info('Sending message')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except TelegramError as error:
        logging.error(f'Sending message error: {error}')


def get_api_answer(current_timestamp):
    """Request to API-endpoint."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        logger.info('sending API-request')
        homeworks_status = requests.get(ENDPOINT, headers=HEADERS,
                                        params=params)
    except RequestException as request_error:
        logger.debug('API-request is unreachable')
        raise BotException(request_error)
    if homeworks_status.status_code != HTTPStatus.OK:
        status_code_error = 'Request can not be executed'
        raise BotException(status_code_error)
    return homeworks_status.json()


def check_response(response):
    """Check if homework exists in response."""
    if not isinstance(response, dict):
        error = 'Invalid response data type'
        logger.error(error)
        raise TypeError(error)
    if 'homeworks' not in response:
        error = 'No homeworks key in data'
        logger.error(error)
        raise KeyError(error)
    if not isinstance(response['homeworks'], list):
        error = 'Invalid response[homeworks] data type'
        logger.error(error)
        raise TypeError(error)

    if 'current_date' not in response:
        error = 'No "current_date" key in data'
        logger.error(error)
        raise KeyError(error)
    return response['homeworks']


def parse_status(homework):
    """Extracting homework status."""
    if not isinstance(homework, dict):
        error = 'Invalid homework data type'
        logger.error(error)
        raise TypeError(error)
    if 'homework_name' not in homework:
        logger.error('Invalid homework name key data')
        raise KeyError('Invalid response key data')
    if 'status' not in homework:
        logger.error('Invalid homework name key data')
        raise KeyError('Invalid response key data')
    if homework['status'] not in HOMEWORK_STATUSES:
        logger.error('Homework status not in the list')
        raise KeyError('Homework status not in the list')

    homework_name = homework['homework_name']
    homework_status = homework['status']
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Check if tokens are correct."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """Main logic of the bot."""
    if not check_tokens():
        check_tokens_error = 'Invalid token or tokens in the list'
        raise BotException(check_tokens_error)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    current_status = ''
    current_error = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if len(homeworks) == 0:
                logger.debug('Статус не изменился')
                continue
            if len(homeworks) > 0:
                if 'lesson_name' not in homeworks[0]:
                    logger.error('Unknown lesson name')
                    raise KeyError('Unknown lesson name')
                last_homework = homeworks[0]
                lesson_name = last_homework['lesson_name']
                homework_status = parse_status(last_homework)
                if homework_status != current_status:
                    current_status = homework_status
                    send_message(bot, f'{lesson_name}. {homework_status}')
                current_timestamp = response.get('current_date')
                current_error = current_error
                current_status = current_status
        except Exception as error:
            message = f"Сбой в работе программы: {error}. " \
                      f"Статус работы: {current_status}"
            if str(error) != str(current_error):
                send_message(bot, message)
                current_error = error
                current_status = ''
            logger.error(message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - %(levelname)s - %(message)s',
        level=logging.DEBUG,
        filename='bot_log.log',
        filemode='a'
    )

    main()
