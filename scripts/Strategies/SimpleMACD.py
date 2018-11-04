import logging
import numpy as np
import pandas as pd
import requests
import json

from AVInterface import AVInterface, AVIntervals, AVPriceType, AVTimeSeries
from .Strategy import Strategy
from Utils import *

class SimpleMACD(Strategy):
    def __init__(self, config):
        super().__init__(config)
        logging.info('Simple MACD strategy initialised.')


    def read_configuration(self, config):
        self.interval = config['strategies']['simple_macd']['interval']
        self.controlledRisk = config['ig_interface']['controlled_risk']
        self.use_av_api = config['strategies']['simple_macd']['use_av_api']
        self.timeout = 1 # Delay between each find_trade_signal() call
        if self.use_av_api:
            try:
                with open('../config/.credentials', 'r') as file:
                    credentials = json.load(file)
                    self.av = AVInterface(config, credentials['av_api_key'])
                    self.timeout = 10
            except IOError:
                logging.error("Credentials file not found!")
                return


    # TODO  possibly split in more smaller ones
    def find_trade_signal(self, broker, epic_id):
        # Fetch current market data
        market = broker.get_market_info(epic_id)
        # Safety checks before processing the epic
        if (market is None
            or 'markets' in market
            or market['snapshot']['bid'] is None):
            logging.warn('Strategy can`t process {}'.format(epic_id))
            return TradeDirection.NONE, None, None

        # Extract market data to calculate stop and limit values
        limit_perc = 10
        stop_perc = max([market['dealingRules']['minNormalStopOrLimitDistance']['value'], 5])
        if self.controlledRisk:
            stop_perc = market['dealingRules']['minControlledRiskStopDistance']['value'] + 1 # +1 to avoid rejection
        current_bid = market['snapshot']['bid']
        current_offer = market['snapshot']['offer']

        # Extract market Id
        marketId = market['instrument']['marketId']

        # Fetch historic prices and build a list with them ordered cronologically
        hist_data = []
        if self.use_av_api:
            # Convert the string for alpha vantage
            marketIdAV = '{}:{}'.format('LON', marketId.split('-')[0])
            # ****************** OLD WAY *******************
            # hist_data = self.av.get_price_series_close(marketIdAV, AVTimeSeries.TIME_SERIES_DAILY, AVIntervals.DAILY)
            # # Safety check
            # if hist_data is None:
            #     logging.warn('Strategy can`t process {}'.format(marketId))
            #     return TradeDirection.NONE, None, None
            # **********************************************
            px = pd.DataFrame()
            macdJson = self.av.get_macd_series_raw(marketIdAV, AVIntervals.DAILY)
            for ts, values in macdJson['Technical Analysis: MACD'].items():
               px.append(values, ignore_index=True)
            print(px)
        else:
            prices = broker.get_prices(epic_id, self.interval, 26)
            prevBid = 0
            for p in prices['prices']:
                if p['closePrice']['bid'] is None:
                    hist_data.append(prevBid)
                else:
                    hist_data.append(p['closePrice']['bid'])
                    prevBid = p['closePrice']['bid']
            if prices is None or 'prices' not in prices:
                logging.warn('Strategy can`t process {}'.format(marketId))
                return TradeDirection.NONE, None, None
            # Calculate the MACD indicator
            px = pd.DataFrame({'close': hist_data})
            px['26_ema'] = pd.DataFrame.ewm(px['close'], span=26).mean()
            px['12_ema'] = pd.DataFrame.ewm(px['close'], span=12).mean()
            px['MACD'] = (px['12_ema'] - px['26_ema'])
            px['MACD_Signal'] = px['MACD'].rolling(9).mean()

        # Find where macd and signal cross each other
        px['positions'] = 0
        px.loc[9:, 'positions'] = np.where(px.loc[9:, 'MACD'] >= px.loc[9:, 'MACD_Signal'] , 1, 0)
        # Highlight the direction of the crossing
        px['signals'] = px['positions'].diff()

        # Identify the trade direction looking at the last signal
        tradeDirection = TradeDirection.NONE
        if len(px['signals']) > 0 and px['signals'].iloc[-1] > 0:
            tradeDirection = TradeDirection.BUY
        elif len(px['signals']) > 0 and px['signals'].iloc[-1] < 0:
            tradeDirection = TradeDirection.SELL
        # Log only tradable epics
        if tradeDirection is not TradeDirection.NONE:
            logging.info("SimpleMACD says: {} {}".format(tradeDirection.name, marketId))

        # Calculate stop and limit distances
        limit, stop = self.calculate_stop_limit(tradeDirection, current_offer, current_bid, limit_perc, stop_perc)

        return tradeDirection, limit, stop

    def calculate_stop_limit(self, tradeDirection, current_offer, current_bid, limit_perc, stop_perc):
        limit = None
        stop = None
        if tradeDirection == TradeDirection.BUY:
            limit = current_offer + percentage_of(limit_perc, current_offer)
            stop = current_bid - percentage_of(stop_perc, current_bid)
        elif tradeDirection == TradeDirection.SELL:
            limit = current_bid - percentage_of(limit_perc, current_bid)
            stop = current_offer + percentage_of(stop_perc, current_offer)

        return limit, stop

    def get_av_historic_price(self, marketId, function, interval, apiKey):
        intParam = '&interval={}'.format(interval)
        if interval == '1day':
            intParam = ''
        url = 'https://www.alphavantage.co/query?function={}&symbol={}{}&outputsize=full&apikey={}'.format(function, marketId, intParam, apiKey)
        data = requests.get(url)
        return json.loads(data.text)
