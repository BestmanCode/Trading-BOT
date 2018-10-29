import logging
import time
import sys
import traceback
from random import shuffle

from Utils import *

class Strategy:
    def __init__(self, config):
        self.positions = {}
        # Define common settings in strategies
        self.order_size = config['ig_interface']['order_size']
        self.max_account_usable = config['general']['max_account_usable']
        self.read_configuration(config)

    def read_configuration(self, config):
        raise NotImplementedError('Not implemented: read_configuration')

    def find_trade_signal(self, broker, epic_id):
        raise NotImplementedError('Not implemented: find_trade_signal')

    def spin(self, broker, epic_list):
        logging.info("Strategy started to spin.")
        try:
            # Fetch open positions and process them first
            logging.info("Processing open positions.")
            self.positions = broker.get_open_positions()
            if self.positions is not None:
                for item in self.positions['positions']:
                    self.process_epic(broker, item['market']['epic'])
            else:
                logging.warn("Unable to retrieve open positions!")

            # Check if the account has enough cash available to open new positions
            percent_used = self.get_account_used_perc(broker)
            if percent_used < self.max_account_usable:
                logging.info("Ok to trade, {}% of account is used".format(str(percent_used)))
                if len(epic_list) < 1:
                    logging.warn("Epic list is empty!")
                else:
                    logging.info("Started processing epic list of length: {}".format(len(epic_list)))
                    shuffle(epic_list)
                    for epic in epic_list:
                        try:
                            if self.process_epic(broker, epic):
                                # If there has been a trade check again account usage
                                percent_used = self.get_account_used_perc(broker)
                                if percent_used > self.max_account_usable:
                                    logging.warn("Stop trading because {}% of account is used".format(str(percent_used)))
                                    break
                            time.sleep(self.timeout)
                        except Exception as e:
                            logging.warn(e)
                            logging.warn(traceback.format_exc())
                            logging.warn(sys.exc_info()[0])
                            time.sleep(self.timeout)
                            continue
            else:
                logging.warn("Will not trade, {}% of account balance is used."
                                .format(str(percent_used)))

            # Define timeout until next iteration of strategy
            strategyInteval = 3600 # 1 hour in seconds
            if self.interval == 'HOUR_4':
                strategyInterval = 60 * 60 * 4
            logging.info("Epics analysis complete. Wait for {} seconds".format(strategyInterval))
            time.sleep(strategyInterval)
        except Exception as e:
                logging.warn(e)
                logging.warn(traceback.format_exc())
                logging.warn(sys.exc_info()[0])
                logging.warn("Something fucked up.")
                time.sleep(self.timeout)


    def process_epic(self, broker, epic):
        logging.info("Processing {}".format(epic))
        # Process the epic and find if we want to trade
        trade, limit, stop = self.find_trade_signal(broker, epic)
        # In case of no trade don't do anything
        if trade is not TradeDirection.NONE:
            if self.positions is not None:
                for item in self.positions['positions']:
                    # If a same direction trade already exist, don't trade
                    if item['market']['epic'] == epic and trade.name == item['position']['direction']:
                        logging.warn("There is already an open position for this epic, skip trade")
                        return False
                    # If a trade in opposite direction exist, close the position
                    elif item['market']['epic'] == epic and trade.name != item['position']['direction']:
                        return broker.close_position(item)
                    else:
                        return broker.trade(epic, trade.name, limit, stop)
            else:
                logging.error("Unable to retrieve open positions! Avoid trading this epic")
        return False


    def get_account_used_perc(self, broker):
        balance, deposit = broker.get_account_balances()
        if balance is None or deposit is None:
            return 9999999 # This will block the trading
        return percentage(deposit, balance)
