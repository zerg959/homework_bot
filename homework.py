import os
import telegram
import time
import requests
from requests.exceptions import RequestException
import logging
from http import HTTPStatus
from dotenv import load_dotenv
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
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.DEBUG,
    filename='bot_log.log',
    filemode='a'
)
logger = logging.getLogger(__name__)


def send_message(bot, message):
    """Send message to chat."""
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)


def get_api_answer(current_timestamp):
    """Request to API-endpoint."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homeworks_status = requests.get(ENDPOINT, headers=HEADERS,
                                        params=params)
    except RequestException as request_error:
        request_error = 'Invalid request data'
        raise request_error
    if homeworks_status.status_code != HTTPStatus.OK:
        status_error = 'Request can not be executed'
        raise status_error
    return homeworks_status.json()


def check_response(response):
    """Check if homework exists in response."""
    if 'homeworks' not in response:
        key_value_error = 'Invalid response key data'
        raise key_value_error
    elif not isinstance(response, dict):
        data_type_error = 'Invalid response data type'
        raise data_type_error
    elif not isinstance(response['homeworks'], list):
        data_type_error = 'Invalid key response data type'
        raise data_type_error
    return response.get('homeworks')


def parse_status(homework):
    """Extracting homework status."""
    homework_name = homework['homework_name']
    homework_status = homework['status']
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Check if tokens are correct."""
    if (
            PRACTICUM_TOKEN
            and TELEGRAM_TOKEN
            and TELEGRAM_CHAT_ID
    ):
        return True
    return False


def main():
    """Main logic of the bot."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    current_error = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if len(homeworks) > 0:
                last_homework = homeworks[0]
                lesson_name = last_homework['lesson_name']
                homework_status = parse_status(last_homework)
                send_message(bot, f'{lesson_name}. {homework_status}')
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
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
