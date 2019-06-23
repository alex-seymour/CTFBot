import json
import time
import sqlite3
from datetime import datetime
from pathlib import Path

import requests
import discord
import schedule
import pytz


class CTFBot:
    def __init__(self, config):
        self._error_count = 0
        self._error_limit = 2
        self._timezone = pytz.timezone('Europe/London')
        self._event_hook = discord.Webhook.from_url(config.get('notify_hook'), adapter=discord.RequestsWebhookAdapter())
        self._result_hook = discord.Webhook.from_url(config.get('result_hook'), adapter=discord.RequestsWebhookAdapter())
        self._ctftime_url = 'https://ctftime.org/api/v1'
        self.team_id = int(config.get('team_id'))
        self._db_conn = sqlite3.connect(Path(__file__).parent / 'ctfs.dat')
        self._db_conn.row_factory = sqlite3.Row

        cursor = self._db_conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS events
                          (ctftime_id INT, name TEXT, start TEXT, finish TEXT, duration TEXT, url TEXT, logo TEXT, 
                          format TEXT, week_alert BOOLEAN, day_alert BOOLEAN, started_alert BOOLEAN, ended BOOLEAN)''')
        self._db_conn.commit()

        self.update()
        self.notify()

    def _get_ctfs(self):
        response = requests.get(f'{self._ctftime_url}/events/?limit=100&start={int(time.time())}',
                                headers={'User-Agent': 'python'})

        if response.status_code == 200:
            if self._error_count > 0:
                self._error_count = 0

            return self._check_ctfs(response.json())
        elif self._error_count < self._error_limit:
            self._error_count += 1
        else:
            self._error_count = 0
            self._send_message('Unable to retrieve CTF data', 14099749, error=True)

    @staticmethod
    def _check_ctfs(ctf_data):
        valid_ctfs = []

        if ctf_data is not None:
            for ctf in ctf_data:
                if not ctf['onsite']:
                    valid_ctfs.append(ctf)

        return valid_ctfs

    def _save_ctfs(self, ctfs):
        if len(ctfs) == 0:
            return

        cursor = self._db_conn.cursor()

        for ctf in ctfs:
            db_entry = cursor.execute('''SELECT *
                                      FROM events
                                      WHERE ctftime_id = :id''', ctf).fetchone()

            if db_entry is None:
                duration = '{}:{}'.format(ctf['duration']['days'], ctf['duration']['hours'])
                cursor.execute('''INSERT INTO events
                                  VALUES(:id, :title, :start, :finish, "{}",:ctftime_url,
                                    :logo,:format, 0, 0, 0, 0)'''.format(duration), ctf)
            else:
                if db_entry['start'] != ctf['start']:
                    cursor.execute('''UPDATE events
                                      SET start = :start
                                      WHERE ctftime_id = :id''', ctf)

                if db_entry['finish'] != ctf['finish']:
                    cursor.execute('''UPDATE events
                                      SET finish = :finish
                                      WHERE ctftime_id = :id''', ctf)

                if db_entry['logo'] != ctf['logo']:
                    cursor.execute('''UPDATE events
                                      SET logo = :logo
                                      WHERE ctftime_id = :id''', ctf)

        self._db_conn.commit()

    def _get_team_participation(self, ctf):
        response = requests.get(f'{self._ctftime_url}/results/', headers={'User-Agent': 'python'})

        if response.status_code == 200:
            if self._error_count > 0:
                self._error_count = 0

            self._check_team_participation(response.json(), ctf)
        elif self._error_count < self._error_limit:
            self._error_count += 1
        else:
            self._error_count = 0
            self._send_message('Unable to retrieve team participation data', 14099749, error=True)

    def _check_team_participation(self, results_data, ctf):
        for event in results_data.keys():
            if event == ctf['id']:
                for score in results_data[event]['scores']:
                    if score['team_id'] == self.team_id:
                        self._send_message('Your team competed in this CTF', 14681067, ctf,
                                           result=True, ctf_result=score)
                        return
                return

    def notify(self):
        date_format = '%Y-%m-%dT%H:%M:%S%z'
        now = datetime.utcnow().replace(tzinfo=pytz.utc)
        cursor = self._db_conn.cursor()
        ctfs = cursor.execute('SELECT * FROM events WHERE ended = 0').fetchall()

        for ctf in ctfs:
            parameters = dict(id=ctf['ctftime_id'])
            start = datetime.strptime(ctf['start'], date_format)
            finish = datetime.strptime(ctf['finish'], date_format)

            if start > now:
                diff = start - now

                if diff.days < 1 and not ctf['day_alert']:
                    cursor.execute('UPDATE events SET day_alert = 1 WHERE ctftime_id = :id', parameters)
                    self._send_message('This CTF is starting in 24 hours', 1992651, ctf, start=start, finish=finish)
                elif 7 >= diff.days > 0 and not ctf['week_alert']:
                    cursor.execute('UPDATE events SET week_alert = 1 WHERE ctftime_id = :id', parameters)
                    self._send_message('This CTF is starting in {} days'.format(diff.days), 16777215, ctf, start=start, finish=finish)
            elif start < now < finish and not ctf['started_alert']:
                cursor.execute('UPDATE events SET started_alert = 1 WHERE ctftime_id = :id', parameters)
                self._send_message('This CTF has started', 65317, ctf, start=start, finish=finish)
            elif finish < now:
                cursor.execute('UPDATE events SET ended = 1 WHERE ctftime_id = :id', parameters)
                self._get_team_participation(ctf)

        self._db_conn.commit()

    def update(self):
        ctf_data = self._get_ctfs()

        if ctf_data is not None:
            self._save_ctfs(ctf_data)

    def clear_db(self):
        now = datetime.now()

        if now.day == 1:
            cursor = self._db_conn.cursor()
            ctfs = cursor.execute('SELECT ctftime_id FROM events WHERE ended = 1').fetchall()

            if len(ctfs) > 0:
                for ctf in ctfs:
                    cursor.execute('DELETE FROM events WHERE ctftime_id = :ctftime_id', ctf)

                self._db_conn.commit()

    def _send_message(self, message, colour, ctf=None, error=False, result=False, ctf_result=None, **kwargs):
        embed = discord.Embed()
        embed.colour = colour
        embed.type = 'rich'

        if not error and not result and ctf is not None:
            duration = ctf['duration'].split(':')

            if duration[0] == '0':
                duration = '{} hours'.format(duration[1])
            else:
                duration = '{0[0]} days {0[1]} hours'.format(duration)

            embed.description = message
            embed.set_author(name=ctf['name'], url=ctf['url'], icon_url=ctf['logo'])
            embed.set_thumbnail(url=ctf['logo'])
            embed.add_field(name='Duration', value=duration)

            if 'start' in kwargs.keys():
                local = kwargs['start'].astimezone(self._timezone).strftime('%H:%M, %d-%m-%Y')
                embed.add_field(name='Start', value=local)

            if 'finish' in kwargs.keys():
                local = kwargs['finish'].astimezone(self._timezone).strftime('%H:%M, %d-%m-%Y')
                embed.add_field(name='Finish', value=local)

            embed.add_field(name='Format', value=ctf['format'])
            embed.add_field(name='Details', value='[CTFtime]({})'.format(ctf['url']))
        elif result:
            embed.description = message
            embed.set_author(name=ctf['name'], url=ctf['url'], icon_url=ctf['logo'])
            embed.set_thumbnail(url=ctf['logo'])
            embed.add_field(name='Score', value=ctf_result['points'][:ctf_result['points'].rfind('.')])
            embed.add_field(name='Position', value=ctf_result['place'])
        elif error:
            embed.title = 'The beacons are lit! CTFBot calls for aid!'
            embed.set_image(url='https://i.ytimg.com/vi/P6CBcE6PCwA/maxresdefault.jpg')
            embed.set_footer(text=message)

        self._event_hook.send(embed=embed)


if __name__ == '__main__':
    last_update = None
    config_file = Path(__file__).parent / 'config.json'

    if not config_file.is_file:
        print('No config file found')
        exit()
    else:
        with config_file.open('r') as file:
            configuration = json.load(file)

    bot = CTFBot(configuration)
    schedule.every().day.at('00:00').do(bot.update)
    schedule.every().day.at('00:00').do(bot.clear_db)
    schedule.every().hour.at(':01').do(bot.notify)

    while True:
        schedule.run_pending()
        time.sleep(1)
