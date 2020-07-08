import requests
import time
import os
import redis
from datetime import datetime, timezone
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import re


def get_email_list():
    email_list = set()
    try:
        email_list_file = open("email_list.conf", "r+")
        while True:
            line = email_list_file.readline()
            if not line:
                break
            if re.match(r"[^@]+@[^@]+\.[^@]+", line):
                email_list.add(line)
    except OSError:
        print("I can't read a file, check file email_list.conf")
    return email_list


def get_email_credentials():
    email_credentials = dict()
    if os.getenv('email_server') is not None and os.getenv('email_login') is not None and \
       os.getenv('email_passwd') is not None:
        email_credentials = {'server': os.getenv('email_server'),
                             'port': os.getenv('email_port', 465),
                             'email_login': os.getenv('email_login'),
                             'email_passwd': os.getenv('email_passwd')}
    else:
        print("You must set the email credentials: email_server, email_login, email_passwd")
        exit(-1)
    return email_credentials


def get_api_credentials():
    okdesk_api_credentials = dict()
    if os.getenv('domain') is not None and os.getenv('api_token') is not None:
        okdesk_api_credentials = {'domain': os.getenv('domain'),
                                  'api_token': os.getenv('api_token')}
    else:
        print("You must set domain and api_token in ENV")
        exit(-1)
    return okdesk_api_credentials


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
        return comment.get('content', "Комментарий пустой")
    return "Комментариев к задаче нет."


def send_msg_to_tlgrm(message: str, tlgrm_api_credintails: dict):
    api_key = u"{}:{}".format(tlgrm_api_credintails.get('bot_name'),
                              tlgrm_api_credintails.get('token'))
    bot = telebot.TeleBot(api_key)
    bot.config['api_key'] = api_key
    result_str = bot.send_message(tlgrm_api_credintails.get('chat_id'), message)
    return result_str.get('ok', False)


def send_email(email_credentials: dict, to_email: str, subject: str, message: str):
    smtp_server = smtplib.SMTP_SSL(email_credentials.get('server'), email_credentials.get('port'))
    smtp_server.ehlo()
    smtp_server.login(email_credentials.get('email_login'), email_credentials.get('email_passwd'))
    msg = MIMEMultipart()
    msg['To'] = to_email
    msg['From'] = email_credentials.get('email_login')
    msg['Subject'] = subject
    body = MIMEText(message, 'plain')
    msg.attach(body)
    try:
        smtp_server.send_message(msg)
    except smtplib.SMTPHeloError:
        print("The server didn't reply properly to the helo greeting.")
        return False
    except smtplib.SMTPRecipientsRefused:
        print("The server rejected ALL recipients (no mail was sent).")
        return False
    except smtplib.SMTPSenderRefused:
        print("The server didn't accept the from_addr.")
        return False
    except smtplib.SMTPDataError:
        print("The server replied with an unexpected error code (other than a refusal of a recipient).")
        return False
    except smtplib.SMTPNotSupportedError:
        print("The mail_options parameter includes 'SMTPUTF8' but the SMTPUTF8 extension is not supported by the server.")
        return False
    smtp_server.quit()
    return True


def main():
    email_credentials = get_email_credentials()
    okdesk_api_credintails = get_api_credentials()
    email_list = get_email_list()
    redis_okdesk = redis.Redis(host='redis_okdesk', port=6379, db=0)
    overdue_reaction_channel = redis_okdesk.pubsub(ignore_subscribe_messages=True)
    overdue_reaction_channel.subscribe('overdue_reaction_noticed_email')
    long_waiting_channel = redis_okdesk.pubsub(ignore_subscribe_messages=True)
    long_waiting_channel.subscribe('long_wait_noticed_email')
    overdue_channel = redis_okdesk.pubsub(ignore_subscribe_messages=True)
    overdue_channel.subscribe('overdue_noticed_email')
    while True:
        overdue_reaction_message = overdue_reaction_channel.get_message()
        if overdue_reaction_message:
            issue_id = str(overdue_reaction_message['data'].decode('utf-8')).split('_')[0]
            issue_info = get_issue_info(issue_id, okdesk_api_credintails)
            issue_url = u"https://help.korkemtech.kz/issues/{}".format(issue_info['id'])
            str_planned_reaction_at = datetime.fromisoformat(issue_info['planned_reaction_at']).astimezone(
                tz=None).strftime('%Y-%m-%d %H:%M')
            email_msg = u"Просроченно время реакции \n\
Плановое время реакции: {}\n{}\nНаименование: {}\n\
Описание заявки: {}\n".format(str_planned_reaction_at,
                              issue_url,
                              issue_info.get('title', "Не указали наименование"),
                              issue_info.get('description', "Нет описания задачи"))
            one_shoot_ok = False
            for email in email_list:
                if not send_email(email_credentials,
                                  email,
                                  u"Просроченно время реакции задачи: {}".format(issue_info['id']),
                                  email_msg):
                    one_shoot_ok = True
            if not one_shoot_ok:
                redis_okdesk.delete(u"{}_email".format(issue_id))
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
            email_msg = u"Время последнего комментария больше 1 суток \n\
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
            one_shoot_ok = False
            for email in email_list:
                if not send_email(email_credentials,
                                  email,
                                  u"Время последнего комментария больше 1 суток: {}".format(
                                                                                     issue_info['id']),
                                  email_msg):
                    one_shoot_ok = True
            if not one_shoot_ok:
                redis_okdesk.delete(u"{}_email".format(issue_id))
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
            email_msg = u"Время решения заявки истекло \n\
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
            one_shoot_ok = False
            for email in email_list:
                if not send_email(email_credentials,
                                  email,
                                  u"Время решения заявки истекло: {}".format(issue_info['id']),
                                  email_msg):
                    one_shoot_ok = True
            if not one_shoot_ok:
                redis_okdesk.delete(u"{}_email".format(issue_id))
        time.sleep(0.001)


if __name__ == '__main__':
    main()
