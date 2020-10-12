import requests
import time
import os
import redis
import telebot
from datetime import datetime, timezone


def get_tlgrm_credntials():
    tlgrm_api_credintails = dict()
    if os.getenv('tlgrm_token') is not None and os.getenv('tlgrm_bot_name') is not None and \
        os.getenv('chat_id') is not None:
        tlgrm_api_credintails = {'token': os.getenv('tlgrm_token'),
                                 'bot_name': os.getenv('tlgrm_bot_name'),
                                 'chat_id': os.getenv('chat_id')}
    else:
        print("You must set bot's name and token in ENV")
        exit(-1)
    return tlgrm_api_credintails


def get_api_credentials():
    okdesk_api_credintails = dict()
    if os.getenv('domain') is not None and os.getenv('api_token') is not None:
        okdesk_api_credintails = {'domain': os.getenv('domain'),
                                  'api_token': os.getenv('api_token')}
    else:
        print("You must set domain and api_token in ENV")
        exit(-1)
    return okdesk_api_credintails


def get_issue_info(issue_id: int, okdesk_api_credintails: dict) -> str:
    url = u"https://{}.okdesk.ru/api/v1/issues/{}?api_token={}".format(okdesk_api_credintails.get('domain'),
                                                                       issue_id,
                                                                       okdesk_api_credintails.get('api_token'))
    headers = {'Content-Type': 'application/json'}
    api_request = requests.get(url=url, headers=headers)
    issues = api_request.json()
    return issues


def get_comments_list(issue_id: int, okdesk_api_credintails: dict) -> str:
    url = u"https://{}.okdesk.ru/api/v1/issues/{}/comments?api_token={}".format(okdesk_api_credintails.get('domain'),
                                                                       issue_id,
                                                                       okdesk_api_credintails.get('api_token'))
    headers = {'Content-Type': 'application/json'}
    api_request = requests.get(url=url, headers=headers)
    comments = api_request.json()
    return comments


def get_last_comments(comments):
    for comment in comments:
        if len(comment.get('content', "Комментарий пустой")) > 300:
            return comment.get('content', "Комментарий пустой")[0:300] + '...'
        else:
            return comment.get('content', "Комментарий пустой")
    return "Комментариев к задаче нет."


def send_msg_to_tlgrm(message: str, tlgrm_api_credintails: dict):
    api_key = u"{}:{}".format(tlgrm_api_credintails.get('bot_name'),
                              tlgrm_api_credintails.get('token'))
    bot = telebot.TeleBot(api_key)
    bot.config['api_key'] = api_key
    result_str = bot.send_message(tlgrm_api_credintails.get('chat_id'), message)
    return result_str.get('ok', False)


def main():
    tlgrm_api_credintails = get_tlgrm_credntials()
    okdesk_api_credintails = get_api_credentials()
    redis_okdesk = redis.Redis(host='redis_okdesk', port=6379, db=0)
    overdue_reaction_channel = redis_okdesk.pubsub(ignore_subscribe_messages=True)
    overdue_reaction_channel.subscribe('overdue_reaction_noticed_tlgrm')
    long_waiting_channel = redis_okdesk.pubsub(ignore_subscribe_messages=True)
    long_waiting_channel.subscribe('long_wait_noticed_tlgrm')
    overdue_channel = redis_okdesk.pubsub(ignore_subscribe_messages=True)
    overdue_channel.subscribe('overdue_noticed_tlgrm')
    while True:
        overdue_reaction_message = overdue_reaction_channel.get_message()
        if overdue_reaction_message:
            issue_id = str(overdue_reaction_message['data'].decode('utf-8')).split('_')[0]
            issue_info = get_issue_info(issue_id, okdesk_api_credintails)
            issue_url = u"https://help.korkemtech.kz/issues/{}".format(issue_info['id'])
            str_planned_reaction_at = datetime.fromisoformat(issue_info['planned_reaction_at']).astimezone(
                tz=None).strftime('%Y-%m-%d %H:%M')
            tlgrm_msg = u"Просроченно время реакции \n\
Плановое время реакции: {}\n{}\nНаименование: {}\n\
Описание заявки: {}\n".format(str_planned_reaction_at,
                              issue_url,
                              issue_info.get('title', "Не указали наименование"),
                              issue_info.get('description', "Нет описания задачи")                              )
            if not send_msg_to_tlgrm(tlgrm_msg, tlgrm_api_credintails=tlgrm_api_credintails):
                redis_okdesk.delete(u"{}_tlgrm".format(issue_id))
        long_waiting_message = long_waiting_channel.get_message()
        if long_waiting_message:
            issue_id = str(long_waiting_message['data'].decode('utf-8')).split('_')[0]
            issue_info = get_issue_info(issue_id, okdesk_api_credintails)
            issue_url = u"https://help.korkemtech.kz/issues/{}".format(issue_info['id'])
            if issue_info.get('comments', None):
                str_last_at = datetime.fromisoformat(issue_info.get('comments', None).get('last_at',
                                                                                          '9999-12-31T00:00:00.000+03:00')).astimezone(
                    tz=None).strftime('%Y-%m-%d %H:%M')
            else:
                str_last_at = 'Нет комментариев к задаче.'
            if issue_info.get('assignee', None):
                assigned_user = issue_info.get('assignee').get('name', None)
                if not assigned_user:
                    assigned_user = 'Ни кто не взял заявку.'
            comment = get_last_comments(get_comments_list(issue_id, okdesk_api_credintails))
            tlgrm_msg = u"Время последнего комментария больше 1 суток \n\
Статус заявки: {}\nДата последнего комментария: {}\n\
Наименование: {}\nОписание заявки: {}\n\
Ответственный по заявке: {}\n\
Последний комментарий к задаче: {}\n{}".format("Ожидание",
                                               str_last_at,
                                               issue_info.get('title', "Не указали наименование"),
                                               issue_info.get('description', "Нет описания задачи"),
                                               assigned_user,
                                               comment,
                                               issue_url)
            if not send_msg_to_tlgrm(tlgrm_msg, tlgrm_api_credintails=tlgrm_api_credintails):
                redis_okdesk.delete(u"{}_tlgrm".format(issue_id))
        overdue_message = overdue_channel.get_message()
        if overdue_message:
            issue_id = str(overdue_message['data'].decode('utf-8')).split('_')[0]
            issue_info = get_issue_info(issue_id, okdesk_api_credintails)
            issue_url = u"https://help.korkemtech.kz/issues/{}".format(issue_info['id'])
            if issue_info.get('comments', None):
                str_last_at = datetime.fromisoformat(issue_info.get('comments', None).get('last_at',
                                                                                          '9999-12-31T00:00:00.000+03:00')).astimezone(
                    tz=None).strftime('%Y-%m-%d %H:%M')
            else:
                str_last_at = 'Нет комментариев к задаче.'
            if issue_info.get('deadline_at', None):
                str_deadline_at = datetime.fromisoformat(issue_info.get('deadline_at',
                                                                        '9999-12-31T00:00:00.000+03:00')).astimezone(tz=None).strftime('%Y-%m-%d %H:%M')
            else:
                str_deadline_at = 'Нет даты deadline к задаче.'
            if issue_info.get('assignee', None):
                assigned_user = issue_info.get('assignee').get('name', None)
                if not assigned_user:
                    assigned_user = 'Ни кто не взял заявку.'
            comment = get_last_comments(get_comments_list(issue_id, okdesk_api_credintails))
            tlgrm_msg = u"Время решения заявки истекло \n\
Дата окончания решения задачи: {}\n\
Дата последнего комментария: {}\n\
Наименование: {}\nОписание заявки: {}\n\
Ответственный по заявке: {}\n\
Последний комментарий к задаче: {}\n{}".format(str_deadline_at,
                                               str_last_at,
                                               issue_info.get('title', "Не указали наименование"),
                                               issue_info.get('description', "Нет описания задачи"),
                                               assigned_user,
                                               comment,
                                               issue_url)
            if not send_msg_to_tlgrm(tlgrm_msg, tlgrm_api_credintails=tlgrm_api_credintails):
                redis_okdesk.delete(u"{}_tlgrm".format(issue_id))
        time.sleep(0.001)


if __name__ == '__main__':
    main()
