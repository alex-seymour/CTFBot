# CTFBot
## About
A Discord bot designed to post alerts about upcoming CTFs. This bot will check for and post notifications once an hour and updates CTF event data once a day.
Three types of notification are posted for each CTF, one is posted a week before it begins, another a day before it begins and the final notification is posted after the CTF starts.

## Setup
* Create a webhook for the Discord channel you want the bot to post notifications to
* Clone the repository ``git clone https://github.com/LucidUnicorn/CTFBot``
* Modify bot.py and add the hook URL ``bot = CTFBot('https://your.discord.hook.url.here')``