import telebot
import requests
import logging
import time as time_lib
import mysql.connector
import matplotlib.pyplot as plt
import os
import configparser
from datetime import datetime, date, timedelta


def main():
    logging.basicConfig(level=logging.DEBUG, filename='full.log', format='%(asctime)s %(levelname)s:%(message)s')
    try:
        bot = telebot.TeleBot('1624616189:AAGwQeVH1otrxeZn8rkLIi7eNH7F_0pMLbw')

        @bot.message_handler(commands=['start'])
        def start_message(message):
            try:
                bot.send_message(message.chat.id, 'Hi')
            except Exception as error:
                logging.error(error, exc_info=True)

        @bot.message_handler(commands=['help'])
        def help_message(message):
            try:
                bot.send_message(message.chat.id, '/list - show list of all currency\n'
                                                  '/exchange - exchange USD (ex.: /exchange $10 to CAD or '
                                                  '/exchange 10 USD to CAD)\n'
                                                  '/history - show chart (ex.: /history USD/CAD for 7 days)')
            except Exception as error:
                logging.error(error, exc_info=True)

        # show list of all currency
        @bot.message_handler(commands=['list'])
        def list_message(message):
            try:
                list_currency = check_local_data(message)
                text_for_message = 'All currency:\n'
                for i in list_currency:
                    text_for_message += str(i[0]) + ':\t' + str(i[1]) + '\n'
                bot.send_message(message.chat.id, text_for_message)
            except Exception as error:
                bot.send_message(message.chat.id, 'Cant show list of currency')
                logging.error(error, exc_info=True)

        # exchange USD (format /exchange $10 to CAD or /exchange 10 USD to CAD)
        @bot.message_handler(commands=['exchange'])
        def exchange_message(message):
            try:
                text_exchange = message.text[10:].split()
                if text_exchange[0][0] == '$':
                    text_for_message = result_of_exchange(message, text_exchange[2], int(text_exchange[0][1:]))
                else:
                    text_for_message = result_of_exchange(message, text_exchange[3], int(text_exchange[0]))

                if text_for_message != "":
                    bot.send_message(message.chat.id, text_for_message)
                else:
                    bot.send_message(message.chat.id, "Don't understand, please try again\n"
                                                      "Ex.: /exchange $10 to CAD or /exchange 10 USD to CAD")
            except Exception as error:
                bot.send_message(message.chat.id, "Cant make exchange, please try again\n"
                                                  "Ex.: /exchange $10 to CAD or /exchange 10 USD to CAD")
                logging.error(error, exc_info=True)

        # show chart   /history USD/CAD for 7 days
        @bot.message_handler(commands=['history'])
        def history_message(message):
            try:
                text_for_chart = message.text[9:].split()
                start_at = date.today() - timedelta(days=int(text_for_chart[2]))
                end_at = date.today()
                format_date = "%Y-%m-%d"

                exchange_currency = text_for_chart[0][4:]
                url_for_chart = "https://api.exchangeratesapi.io/history"
                url_params = {
                    'start_at': start_at.strftime(format_date),
                    'end_at': end_at.strftime(format_date),
                    'base': text_for_chart[0][:3],
                    'symbols': exchange_currency
                }

                list_for_chart = requests.get(url=url_for_chart, params=url_params).json()

                # if at least 2 value for chart, than make it
                if len(list_for_chart['rates']) > 1:
                    sort_list_for_chart = sorted(list_for_chart['rates'].items())
                    date_x = []
                    num_y = []
                    for i in sort_list_for_chart:
                        date_x.append(i[0][5:])
                        num_y.append(round(i[1][exchange_currency], 2))

                    plt.plot(date_x, num_y)
                    plt.xlabel('x - date')
                    plt.ylabel('y - currency')

                    plt.savefig('chart.png')
                    plt.close()
                    bot.send_photo(message.chat.id, photo=open('chart.png', 'rb'))
                    os.remove('chart.png')
                else:
                    bot.send_message(message.chat.id, "No exchange rate data is available for the selected currency")

            except Exception as error:
                bot.send_message(message.chat.id, "Cant make chart, please try again\n"
                                                  "Ex.: /history USD/CAD for 7 days")
                logging.error(error, exc_info=True)

        # if less than 10 minutes take data from database/ else take data from site
        def check_local_data(message):
            try:
                config = configparser.ConfigParser()
                config.read('config.ini', encoding='utf-8-sig')
                cnx = mysql.connector.connect(user=config.get('mysql', 'user'),
                                              password=config.get('mysql', 'password'),
                                              host=config.get('mysql', 'host'),
                                              database='exchange_bot')
                config.close()

                read_date = cnx.cursor()
                read_date.execute("SELECT date FROM last_api_request")
                last_date = read_date.fetchall()
                read_date.close()

                date_format = "%Y-%m-%d %H:%M:%S"
                now = datetime.now()
                date_now = datetime.strptime(now.strftime(date_format), date_format)
                dif_in_time = date_now - last_date[0][0]
                date_now = now.strftime(date_format)

                # if more than 10 minutes
                if len(last_date) == 0 or dif_in_time.seconds / 60 > 10:
                    clear_table = cnx.cursor()
                    clear_table.execute("DELETE FROM last_api_request")
                    cnx.commit()
                    clear_table.close()

                    list_currency = requests.get('https://api.exchangeratesapi.io/latest?base=USD').json()

                    insert_date = cnx.cursor()
                    for i in list_currency['rates']:
                        add_currency = "INSERT INTO last_api_request (name, number, date) VALUES (%s, %s, %s)"
                        data_currency = (i, round(list_currency['rates'][i], 2), date_now)
                        insert_date.execute(add_currency, data_currency)

                    cnx.commit()
                    insert_date.close()

                read_currency = cnx.cursor()
                read_currency.execute("SELECT name, number FROM last_api_request")
                last_currency = read_currency.fetchall()
                read_currency.close()

                cnx.close()
                return last_currency

            except Exception as error:
                bot.send_message(message.chat.id, "Cant load data from database or exchangeratesapi.io")
                logging.error(error, exc_info=True)

        def result_of_exchange(message, cur_for_exchange, num_for_exchange):
            try:
                list_currency = check_local_data(message)
                for i in list_currency:
                    if i[0] == cur_for_exchange:
                        return str(round(num_for_exchange * i[1], 2)) + " " + cur_for_exchange
                return ""
            except Exception as error:
                bot.send_message(message.chat.id, "Cant make exchange with that data")
                logging.error(error, exc_info=True)

        while True:
            try:
                bot.polling(none_stop=True, interval=0, timeout=0)
            except Exception as not_res:
                logging.error(not_res, exc_info=True)
                time_lib.sleep(10)

    except Exception as err:
        logging.error(err, exc_info=True)


if __name__ == '__main__':
    main()
