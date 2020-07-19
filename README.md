# **OKDESK NOTICE SENDER**

People try to get rid of their duty, but a Manager has to influence to staff. "You gotta do what you gotta do". So the service sends him info about the not enough paid attention issues.

**How to run docker-compose**

For running the docker-compose you must set all environment variable, due to it use in the scripts to connect to API Okdesk and API Telegram
**Example:**
api_token=000fcccc domain=mysite tlgrm_token=AKDKDKD tlgrm_bot_name=333333 chat_id=-4544545454 docker-compose up -d --build

# **Conceptual scheme of the project**
The Service has 4 parts, all of them are docker containers:
* overdue_chk - seek the "bad" issues
* telegrm_snd - send a notice via Telegram chat
* email_snd - send a notice via an email server to email
* redis - Redis database.

![Image of Concept](https://github.com/AlexShander/okdesk_notices/blob/master/img/concept.png)

# Diagram of overdue_chk's algorithm
![Image of overdue_chk](https://github.com/AlexShander/okdesk_notices/blob/master/img/overdue_chk.png)

# Diagram of telegrm_snd's algorithm
![Image of telegrm_snd](https://github.com/AlexShander/okdesk_notices/blob/master/img/telegrm_snd.png)
