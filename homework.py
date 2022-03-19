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
        logger.info('Sending API-request')
        homeworks_status = requests.get(ENDPOINT, headers=HEADERS,
                                        params=params)
    except RequestException as request_error:
        raise BotException(request_error)
    if homeworks_status.status_code != HTTPStatus.OK:
        status_code_error = 'Request can not be executed'
        raise BotException(status_code_error)
    return homeworks_status.json()


def check_response(response):
    """Check if homework exists in response."""
    try:
        homeworks_list = response['homeworks']
        homework = homeworks_list[0]
    except BotException:
        if type(response['homeworks']) is not list:
            logger.error('Invalid response data type')
            raise TypeError('Invalid data type')
        if 'homeworks' not in response:
            logger.error('No "homeworks" key in data')
            raise KeyError('Invalid response key data')
        if 'current_date' not in response:
            logger.error('No "current_date" key in data')
            raise KeyError('No "current_date" key in data')
        if type(homework) is not dict:
            logger.error('Invalid homework data type')
            raise TypeError('Invalid homework data type')
    return homeworks_list


def parse_status(homework):
    """Extracting homework status."""
    try:
        homework_name = homework['homework_name']
        homework_status = homework['status']
        verdict = HOMEWORK_STATUSES[homework_status]
    except KeyError:
        if 'homework_name' not in homework:
            logger.error('Invalid homework name key data')
            raise KeyError('Invalid response key data')
        if homework['status'] not in HOMEWORK_STATUSES:
            logger.error('Homework status not in the list')
            raise KeyError('Homework status not in the list')
        if verdict not in HOMEWORK_STATUSES.values():
            logger.error('Unknown homework status')
            raise KeyError('Unknown homework status')
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
    current_error = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if len(homeworks) > 0:
                try:
                    last_homework = homeworks[0]
                    lesson_name = last_homework['lesson_name']
                    homework_status = parse_status(last_homework)
                    send_message(bot, f'{lesson_name}. {homework_status}')
                    timestamp = response.get('current_date', timestamp)
                except KeyError:
                    if 'lesson_name' not in last_homework:
                        logger.error('Unknown lesson name')
                        raise KeyError('Unknown lesson name')
            else:
                logger.debug('Статус не изменился')
            current_timestamp = response.get('current_date')
            current_error = ''
        except Exception as error:
            message = f"Сбой в работе программы: {error}"
            if str(error) != str(current_error):
                send_message(bot, message)
                current_error = error
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
