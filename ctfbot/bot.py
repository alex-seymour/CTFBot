import time
import sqlite3
import datetime
import logging
import requests
import discord
import pytz

class CTFBot:
    def __init__(self, url, logger):
        self._logger = logger
        self._error_count = 0
        self._timezone = pytz.timezone('Europe/London')
        self._hook = discord.Webhook.from_url(url, adapter=discord.RequestsWebhookAdapter())
        self._ctftime_url = 'https://ctftime.org/api/v1/events/?limit=100&start={}'.format(int(time.time()))
        self._db_conn = sqlite3.connect('ctfs.dat')
        self._db_conn.row_factory = sqlite3.Row

        cursor = self._db_conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS events
                          (ctftime_id INT, name TEXT, start TEXT, finish TEXT, duration TEXT, url TEXT, logo TEXT, 
                          format TEXT, week_alert BOOLEAN, day_alert BOOLEAN, started_alert BOOLEAN, ended BOOLEAN)''')
        self._db_conn.commit()

    def _get_ctfs(self):
        response = requests.get(self._ctftime_url, headers={'User-Agent': 'python'})

        if response.status_code == 200:
            if self._error_count > 0:
                self._error_count = 0

            return self._check_ctfs(response.json())
        elif self._error_count < 2:
            self._error_count += 1
        else:
            self._error_count = 0
            self._send_message('Unable to retrieve CTF data', 14099749, error=True)

    def _check_ctfs(self, ctf_data):
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
            db_entry = cursor.execute('SELECT ctftime_id FROM events WHERE ctftime_id = {}'.format(ctf['id'])).fetchone()

            if db_entry is None:
                duration = '{}:{}'.format(ctf['duration']['days'], ctf['duration']['hours'])
                cursor.execute('''INSERT INTO events
                                  VALUES(:id, :title, :start, :finish, "{}",:ctftime_url,
                                    :logo,:format, 0, 0, 0, 0)'''.format(duration), ctf)

        self._db_conn.commit()

    def notify(self):
        date_format = '%Y-%m-%dT%H:%M:%S%z'
        now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        cursor = self._db_conn.cursor()
        ctfs = cursor.execute('SELECT * FROM events WHERE ended = 0').fetchall()

        for ctf in ctfs:
            parameters = dict(id=ctf['ctftime_id'])
            start = datetime.datetime.strptime(ctf['start'], date_format)
            finish = datetime.datetime.strptime(ctf['finish'], date_format)

            if start > now:
                diff = start - now

                if diff.days <= 1 and not ctf['day_alert']:
                    self._logger.info('Sending 24 hour notification for {}'.format(ctf['name']))
                    cursor.execute('UPDATE events SET day_alert = 1 WHERE ctftime_id = :id', parameters)
                    self._send_message('This CTF is starting in 24 hours', 1992651, ctf, start=start, finish=finish)
                elif diff.days <= 7 and not ctf['week_alert']:
                    self._logger.info('Sending 1 week notification for {}'.format(ctf['name']))
                    cursor.execute('UPDATE events SET week_alert = 1 WHERE ctftime_id = :id', parameters)
                    self._send_message('This CTF is starting in 1 week', 16777215, ctf, start=start, finish=finish)
            elif start < now < finish:
                self._logger.info('Sending started notification for {}'.format(ctf['name']))
                cursor.execute('UPDATE events SET started_alert = 1 WHERE ctftime_id = :id', parameters)
                self._send_message('This CTF has started', 65317, ctf, start=start, finish=finish)
            elif finish < now:
                self._logger.info('Setting {} to finished'.format(ctf['name']))
                cursor.execute('UPDATE events SET ended = 1 WHERE ctftime_id = :id', parameters)

        self._db_conn.commit()

    def update(self):
        ctf_data = self._get_ctfs()

        if ctf_data is not None:
            self._save_ctfs(ctf_data)

    def _send_message(self, message, colour, ctf=None, error=False, **kwargs):
        embed = discord.Embed()
        embed.colour = colour
        embed.type = 'rich'

        if not error and ctf is not None:
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
        elif error:
            embed.title = 'The beacons are lit! CTFBot calls for aid!'
            embed.set_image(url='https://i.ytimg.com/vi/P6CBcE6PCwA/maxresdefault.jpg')
            embed.set_footer(text=message)

        self._hook.send(embed=embed)


if __name__ == '__main__':
    logger = logging.getLogger('ctfbot')
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(filename='/tmp/ctfbot.log', encoding='utf-8', mode='w')
    handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
    logger.addHandler(handler)

    last_update = None
    bot = CTFBot('', logger)

    while True:
        try:
            diff = (datetime.datetime.utcnow() - last_update)
        except TypeError:
            diff = None

        if last_update is None or diff.days >= 1:
            logging.info('Updating sources')
            bot.update()
            last_update = datetime.datetime.utcnow()

        bot.notify()
        logger.info('Sleeping')
        time.sleep(3600)
