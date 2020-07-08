import requests
import time
import os
import redis
from datetime import datetime, timedelta


def get_list_issues(url: str) -> set:
    headers = {'Content-Type': 'application/json'}
    api_request = requests.get(url=url, headers=headers)
    list_issues = set(api_request.json())
    return list_issues


def get_api_credentials():
    okdesk_api_credentials = dict()
    if os.getenv('domain') is not None and os.getenv('api_token') is not None:
        okdesk_api_credentials = {'domain': os.getenv('domain'),
                                  'api_token': os.getenv('api_token')}
    else:
        print("You must set domain and api_token in ENV")
        exit(-1)
    return okdesk_api_credentials


def get_list_overdue_reaction_issues():
    overdue_issues_url = u"http://{}.okdesk.ru/api/v1/issues/count?api_token=\
{}&overdue_reaction=1&status[]=opened".format(okdesk_api_credintails.get('domain'),
                                                  okdesk_api_credintails.get('api_token')
                                                  )
    answered_overdue_issues_url = u"http://{}.okdesk.ru/api/v1/issues/count?api_token=\
{}&overdue_reaction=1&status[]=opened&reacted_until={}".format(okdesk_api_credintails.get('domain'),
                                                                   okdesk_api_credintails.get('api_token'),
                                                                   time.strftime('%d-%m-%Y %H:%M')
                                                                   )
    list_overdue_issues = get_list_issues(overdue_issues_url)
    list_overdue_answered_issues = get_list_issues(answered_overdue_issues_url)
    return list_overdue_issues.difference(list_overdue_answered_issues)


def get_list_long_wait_issues():
    waiting_issues_url = u"http://{}.okdesk.ru/api/v1/issues/count?api_token=\
{}&status[]=waiting".format(okdesk_api_credintails.get('domain'),
                                okdesk_api_credintails.get('api_token'))
    answered_24h_waiting_issues_url = u"http://{}.okdesk.ru/api/v1/issues/count?api_token=\
{}&status[]=waiting&updated_since={}".format(okdesk_api_credintails.get('domain'),
                                             okdesk_api_credintails.get('api_token'),
                                             datetime.strftime(datetime.now() - timedelta(1), '%d-%m-%Y'))
    list_waiting_issues = get_list_issues(waiting_issues_url)
    list_answered_24h_issues = get_list_issues(answered_24h_waiting_issues_url)
    return list_waiting_issues.difference(list_answered_24h_issues)


def get_list_overdue_execution_issues():
    overdue_issues_url = u"http://{}.okdesk.ru/api/v1/issues/count?api_token=\
{}&status[]=waiting&status[]=opened&overdue=1".format(okdesk_api_credintails.get('domain'),
                                okdesk_api_credintails.get('api_token'))
    return get_list_issues(overdue_issues_url)


def main():
    try:
        redis_okdesk = redis.Redis(host='redis_okdesk', port=6379, db=0)
        while True:
            overdue_reaction_issue_notices = get_list_overdue_reaction_issues()
            for notice in overdue_reaction_issue_notices:
                if redis_okdesk.get(u"{}_tlgrm".format(str(notice))) is None:
                    if redis_okdesk.publish('overdue_reaction_noticed_tlgrm', u"{}_tlgrm".format(str(notice))) > 0:
                        redis_okdesk.set(u"{}_tlgrm".format(str(notice)), 'issue', ex=60 * 60 * 12)
                if redis_okdesk.get(u"{}_email".format(str(notice))) is None:
                    if redis_okdesk.publish('overdue_reaction_noticed_email', u"{}_email".format(str(notice))) > 0:
                        redis_okdesk.set(u"{}_email".format(str(notice)), 'issue', ex=60 * 60 * 12)
            long_waiting_issues_notices = get_list_long_wait_issues()
            for notice in long_waiting_issues_notices:
                if redis_okdesk.get(u"{}_tlgrm".format(str(notice))) is None:
                    if redis_okdesk.publish('long_wait_noticed_tlgrm', u"{}_tlgrm".format(str(notice))) > 0:
                        redis_okdesk.set(u"{}_tlgrm".format(str(notice)), 'issue', ex=60 * 60 * 12)
                if redis_okdesk.get(u"{}_email".format(str(notice))) is None:
                    if redis_okdesk.publish('long_wait_noticed_email', u"{}_email".format(str(notice))) > 0:
                        redis_okdesk.set(u"{}_email".format(str(notice)), 'issue', ex=60 * 60 * 12)
            overdue_issue_notices = get_list_overdue_execution_issues()
            for notice in overdue_issue_notices:
                if redis_okdesk.get(u"{}_tlgrm".format(str(notice))) is None:
                    if redis_okdesk.publish('overdue_noticed_tlgrm', u"{}_tlgrm".format(str(notice))) > 0:
                        redis_okdesk.set(u"{}_tlgrm".format(str(notice)), 'issue', ex=60 * 60 * 12)
                if redis_okdesk.get(u"{}_email".format(str(notice))) is None:
                    if redis_okdesk.publish('overdue_noticed_email', u"{}_email".format(str(notice))) > 0:
                        redis_okdesk.set(u"{}_email".format(str(notice)), 'issue', ex=60 * 60 * 12)
            time.sleep(360)
    except (KeyboardInterrupt, SystemExit):
        print("Process is terminated")
        exit(0)


if __name__ == '__main__':
    okdesk_api_credintails = get_api_credentials()
    main()
