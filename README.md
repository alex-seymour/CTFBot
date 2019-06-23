# CTFBot
## About
A Discord bot designed to post alerts about upcoming CTFs. This bot will check for and post notifications once an hour and updates CTF event data once a day.
Three types of notification are posted for each CTF, one is posted a week before it begins, another a day before it begins and the final notification is posted after the CTF starts.
The bot will also periodically check finished CTFs and post a message containing the team's final score and position if they took part.

## Setup
* Create a webhook for the Discord channel you want the bot to post notifications to
* Clone the repository ``git clone https://github.com/LucidUnicorn/CTFBot``
* Install the necessary requirements ``pip install -r requirements.txt``
* Configure the bot (see below)
* Run the bot ``python bot.py``

## Configuration
The bot has three required configuration values that should appear inside a file called ``config.json`` within the `ctfbot` directory.

```json
{
    "notify_hook": "<your notification channel webhook URL>",
    "result_hook": "<your results channel webhook URL>",
    "team_id": "<your CTFTime team ID>"
}
```

- **notify_hook**: a Discord webhook for the channel you want CTF notifications to be posted to.
- **result_hook**: a Discord webhook for the channel you want your team's results to be posted to. This can be the same as `notify_hook` if you don't want to use a separate channel.
- **team_id**: your team's CTFtime ID, this can be found by navigating to your team's page on [CTFtime](https://ctftime.org) and copying the number at the end of the URL.