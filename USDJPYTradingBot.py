import oandapyV20
from oandapyV20 import API
import oandapyV20.endpoints.pricing 
from oandapyV20.endpoints.pricing import PricingStream
import oandapyV20.endpoints.instruments
import pandas as pd
import numpy as np
import talib
import time
import requests
import json


# Initialize OANDA API (kindly fill up before executing)
"""
api = API(access_token='your_api')
url = "https://api-fxpractice.oanda.com/v3/accounts/your_account_number/candles/latest"
orderURL = "https://api-fxpractice.oanda.com/v3/accounts/your_account_number/orders"
positions_url = f"https://api-fxpractice.oanda.com/v3/accounts/your_account_number/positions/USD_JPY"

headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer your_api"
}
"""

# Define query parameters used to get candlestick data for closing price
params = {
    #forex pair we are trading
    "instrument": "USD_JPY",
    #candlestick timeframe
    "granularity":"H4",
    #number of candle sticks
    "count":1
}

#json object for buying instrument
buy = {
    "order": {
        #number of units we want to buy
        "units": 10000,
        #what we are buying
        "instrument": "USD_JPY",
        #type of market order
        "timeInForce": "FOK",
        "type": "MARKET",
        "positionFill": "DEFAULT",
        #stop loss to be defined based on closing price
        "stopLossOnFill": {
            "price": ""
        },
        #take profit to be defined based on closing price
        "takeProfitOnFill":{
            "price": ""
        }
    }
}


#json object for exiting a buy position
buyExit = {
    "order": {
        #units should be opposite of buy order to sell off all units we are holding
        "units": -10000,
        #type of instrument we are trading
        "instrument": "USD_JPY",
        #type of market order
        "timeInForce": "FOK",
        "type": "MARKET",
        "positionFill": "DEFAULT" 
    }
}

#json object for entering a sell position
sell = {
    "order": {
        #number of units we are selling to be set in negative numbers
        "units": -10000,
        #type of instrument we are selling
        "instrument": "USD_JPY",
        #type of market order
        "timeInForce": "FOK",
        "type": "MARKET",
        "positionFill": "DEFAULT",
        #stop loss to be defined based on closing price
        "stopLossOnFill": {
            "price": ""
        },
        #take profit to be defined based on closing price
        "takeProfitOnFill":{
            "price": ""
        }   
    }
}

#json object for exiting a sell position
sellExit = {
    "order": {
        #units is based on sell position, we are buying back the units we sold previously
        "units": 10000,
        #type of instrument we are trading
        "instrument": "USD_JPY",
        #type of market order
        "timeInForce": "FOK",
        "type": "MARKET",
        "positionFill": "DEFAULT"
    }
}

#method to calculate MACD
def calculate_macd(instrument):

    MACDparams ={
        #candlestick timeframe we are looking at
        "granularity":"H4"
    }
    #API request to get recent candlestick data
    request = oandapyV20.endpoints.instruments.InstrumentsCandles(instrument=instrument, params=MACDparams)
    response = api.request(request)

    #Array to hold recent price data
    prices = [float(candle['mid']['c']) for candle in response['candles']]

    #use talib to calculate macd based on price data, this would produce 3 arrays macd line values, macd signal line values and macd histograms
    #fast period, slowperiod, signalperiod determines how many candlesticks we are looking at for macd, lesser value would react faster to changes while higher value produce lesser false signals
    macd, signal, histogram = talib.MACD(np.array(prices), fastperiod=12, slowperiod=26, signalperiod=9)
    
    #return most recent macd value
    return macd[-1], signal[-1]

#method to calculate bollinger bands
def calculate_bollinger_bands(instrument):
    bbparams ={
        #candlestick time frame
        "granularity":"H4"
    }

    #API request to get recent candlestick data
    request = oandapyV20.endpoints.instruments.InstrumentsCandles(instrument=instrument, params=bbparams)
    response = api.request(request)

    #Array to hold recent prices
    prices = [float(candle['mid']['c']) for candle in response['candles']]

    # Calculate Bollinger Bands using talib which would return 3 array fo values, the upper, middle and lower bands values
    #params are timeperiod which determine the number of candlesticks we look at and nbdevup and nbdevdn are standard deviations between the upper and lower bands from the middle band
    #matype 0 stands for simple moving average
    upper_band, middle_band, lower_band = talib.BBANDS(np.array(prices), timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
    
    #return latest bollinger band data
    return upper_band[-1], middle_band[-1], lower_band[-1]


instrument = "USD_JPY"
buy_trade = False
sell_trade = False
pmacd = 0
cmacd = 0
psignal = 0
csignal = 0
closing_price = 0
squeeze_threshold = 0.9
retry_count = 0
current_time = time.localtime()


while True:
    params = {
    #forex pair we are trading
    "instrument": "USD_JPY",
    #candlestick timeframe
    "granularity":"H4",
    #number of candle sticks
    "count":1
    }
    #API request to get candlestick data 
    response = requests.get(url, headers=headers, params=params)
    candle_data = response.json()

    #using candlestick data from above to determine opening, closing price, candle_data is structured 
    closing_price = float(candle_data['candles'][0]['mid']['c'])

    #API request to get positions data
    position = requests.get(positions_url, headers=headers)
    position_data = position.json()

    if response.status_code >= 300 or position.status_code >= 300:

        retry_count += 1
        if retry_count >= 5:
            break

        time.sleep(60)
        continue

    else:
        retry_count = 0

    #calculating macd and bollinger band
    upper_band, middle_band, lower_band = calculate_bollinger_bands(instrument)
    cmacd, csignal = calculate_macd(instrument)

    macd_zero_cross_above = pmacd < 0 and cmacd > 0
    macd_zero_cross_below = pmacd > 0 and cmacd < 0
    price_at_lower_band = closing_price <= lower_band
    price_at_higher_band = closing_price >= upper_band
    macd_bullish_cross =  pmacd <= psignal and cmacd > csignal
    macd_bearish_cross =  pmacd >= psignal and cmacd < csignal
    bollinger_band_squeeze = (upper_band - lower_band) < squeeze_threshold

    #determine if there are open buy positions
    buy_trade = int(position_data['position']['long']['units']) > 0
    #determine if there are any open sell positions
    sell_trade = int(position_data['position']['short']['units']) < 0
    
    
    #if there are no positions opened, we are looking to enter into a position
    if(buy_trade == False and sell_trade == False):
        #buy entry strategy
        if macd_zero_cross_above and bollinger_band_squeeze:
            #define stop loss 100 pips below the buying price, note USD JPY pip is on 2 decimal place instead of 4
            buy["order"]["stopLossOnFill"]["price"]= str(round(closing_price - 1,3))
            #define take profit 150 pips above the buying price, note USD JPY pip is on 2 decimal place instead of 4
            buy["order"]["takeProfitOnFill"]["price"]= str(round(closing_price + 1.5,3))
            #API request to buy order
            buy_entry = requests.post(orderURL, headers=headers, json=buy)
            
        #sell entry strategy
        elif macd_zero_cross_below and bollinger_band_squeeze:
            #define stop loss 100 pips above the selling price
            sell["order"]["stopLossOnFill"]["price"]= str(round(closing_price + 1,3))
            #define take profit 150 pips below selling price
            sell["order"]["takeProfitOnFill"]["price"]= str(round(closing_price - 1.5,3))
            #API request to sell order
            sell_entry = requests.post(orderURL, headers=headers, json=sell)

    #When there is a position opened either buy or sell we are looking to exit            
    else:

        #exit strategy for buy orders
        if (price_at_higher_band or macd_bearish_cross) and buy_trade == True:
            #API request to exit buy order
            buy_exit = requests.post(orderURL, headers=headers, json=buyExit)

        #exit strategy for sell orders
        elif (price_at_lower_band or macd_bullish_cross) and sell_trade == True:
            #API request to exit sell order
            sell_exit = requests.post(orderURL, headers=headers, json=sellExit)

    #set past macd to current macd so that in the next iteration after current macd is recalculated it can be compared to past macd 1 iteration before it
    pmacd = cmacd
    psignal = csignal
    print(closing_price)
    time.sleep(14400)
