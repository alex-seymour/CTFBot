import time
import sqlite3
import datetime
import requests
import discord

class CTFBot:
    def __init__(self, url):
        self._error_count = 0
        self._hook = discord.Webhook.from_url(url, adapter=discord.RequestsWebhookAdapter())
        self._ctftime_url = 'https://ctftime.org/api/v1/events/?limit=100&start={}'.format(int(time.time()))
        self._db_conn = sqlite3.connect('ctfs.dat')
        self._db_conn.row_factory = sqlite3.Row

        cursor = self._db_conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS events
                          (ctftime_id INT, name TEXT, start TEXT, finish TEXT, duration TEXT,url TEXT, logo TEXT, 
                          format TEXT, week_alert BOOLEAN, day_alert BOOLEAN, started_alert BOOLEAN, ended BOOLEAN)''')
        self._db_conn.commit()

    def _get_ctfs(self):
        response = requests.get(self._ctftime_url, headers={'User-Agent': 'python'})

        if response.status_code == 200:
            if self._error_count > 0:
                self._error_count = 0

            return self._check_ctfs(response.json())
        elif self._error_count < 3:
            self._error_count += 1
        else:
            self._error_count = 0
            self._send_message('CTF Bot in distress!')

    def _check_ctfs(self, ctf_data):
        valid_ctfs = []

        if ctf_data is not None:
            for ctf in ctf_data:
                if not ctf['onsite']:
                    valid_ctfs.append(ctf)

        return valid_ctfs

    def _send_message(self, message):
        self._hook.send(message)
