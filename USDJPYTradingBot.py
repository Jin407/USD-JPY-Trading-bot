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

# Define query parameters
params = {
    #instrument we will be trading in
    "instrument": "USD_JPY",
    #Time chart we will be trading in, minute chart in this instance
    "granularity":"M1",
    "count":1
}

#json object for buy orders
buy = {
    "order": {
        #number of units we want to trade
        "units": 10000,
        #instrument we want to trade
        "instrument": "USD_JPY",
        #Fill or kill order, either order gets filled entirely or cancelled
        "timeInForce": "FOK",
        "type": "MARKET",
        "positionFill": "DEFAULT",
        #stop loss is defined based on market price later on in the algorithm
        "stopLossOnFill": {
            "price": ""
        },
        #take profit is defined based on market price later on in the algorithm
        "takeProfitOnFill":{
            "price": ""
        }
    }
}

#json object to exit buy orders
buyExit = {
    "order": {
        #units should be opposigte of what we bought, to sell in the market
        "units": -10000,
        #instrument we are trading in
        "instrument": "USD_JPY",
        #Fill or kill order
        "timeInForce": "FOK",
        "type": "MARKET",
        "positionFill": "DEFAULT" 
    }
}

#json object to enter into sell orders
sell = {
    "order": {
        #number of units we are short selling
        "units": -10000,
        #instrument we are trading
        "instrument": "USD_JPY",
        #Fill or kill order
        "timeInForce": "FOK",
        "type": "MARKET",
        "positionFill": "DEFAULT",
        #Stop loss will be defined based on market price later on
         "stopLossOnFill": {
            "price": ""
        },
        #Take profit will be defined based on market price later on
        "takeProfitOnFill":{
            "price": ""
        }   
    }
}

#json object to exit sell orders
sellExit = {
    "order": {
        #number of units should be opposite to our sell orders to exit the position, buy back instruments we short sold previously
        "units": 10000,
        #instrument we are trading in
        "instrument": "USD_JPY",
        #Fill or kill order
        "timeInForce": "FOK",
        "type": "MARKET",
        "positionFill": "DEFAULT"
    }
}

#method to calculate macd
def calculate_macd(instrument):
    MACDparams ={
        #Time chart we are looking at, in this case, minute chart
        "granularity":"M1"
    }
    #request to OANDA's rest api for recent candlestick data in the minute chart
    request = oandapyV20.endpoints.instruments.InstrumentsCandles(instrument=instrument, params=MACDparams)
    response = api.request(request)

    #store the recent prices of USDJPY in a dictionary
    prices = [float(candle['mid']['c']) for candle in response['candles']]

    #using talib to calculate MACD based on recent USD JPY prices, fast, slow and signal period are default settings and can be adjusted
    macd, signal, _ = talib.MACD(np.array(prices), fastperiod=12, slowperiod=26, signalperiod=9)

    #return most recent macd
    return macd[-1]

#method to calculate bollinger bands
def calculate_bollinger_bands(instrument):
    bbparams ={
        #Time chart we are looking at, in this case, minute chart
        "granularity":"M1"
    }
    #request to OANDA's rest api for recent candlestick data in the minute chart
    request = oandapyV20.endpoints.instruments.InstrumentsCandles(instrument=instrument, params=bbparams)
    response = api.request(request)

    #store the recent prices of USDJPY in a dictionary
    prices = [float(candle['mid']['c']) for candle in response['candles']]

    #using talib to calculate bollinger bands, settings for time period to look at and standard deviation from middle band is set to 2 for both upper and lower band by default
    #matype=0 means we are using simple moving average to calculate bollinger bands
    upper_band, middle_band, lower_band = talib.BBANDS(np.array(prices), timeperiod=14, nbdevup=2, nbdevdn=2, matype=0)
    
    #return most recent bollinger band data
    return upper_band[-1], middle_band[-1], lower_band[-1]


instrument = "USD_JPY"
buy_trade = False
sell_trade = False
pmacd = 0
cmacd = 0
closing_price = 0
file = open("error.txt",'a')
current_time = time.localtime()
#this would ensure algorithm runs at the start of the minute and data is syncronized with the market
time.sleep(60-current_time.tm_sec)


while True:
    #API request to get candlestick data 
    response = requests.get(url, headers=headers, params=params)
    candle_data = response.json()

    #writing errors to file
    if(response.status_code != 200):
        file.write(response.status_code)
        file.write(response.content)

    #using candlestick data from above to determine opening, closing price, candle_data is structured 
    opening_price = float(candle_data['candles'][0]['mid']['o'])
    closing_price = float(candle_data['candles'][0]['mid']['c'])

    #API request to get positions data
    position = requests.get(positions_url, headers=headers)
    position_data = position.json()

    if(position.status_code != 200):
        file.write(str(position.status_code))
        file.write(str(position.content))

    #calculating macd and bollinger band
    upper_band, middle_band, lower_band = calculate_bollinger_bands(instrument)
    cmacd = calculate_macd(instrument)

    #determine if there are open buy positions
    if int(position_data['position']['long']['units']) > 0:
        buy_trade = True
    else:
        buy_trade = False

    #determine if there are any open sell positions
    if int(position_data['position']['short']['units']) < 0:
        sell_trade = True
    else:
        sell_trade = False
    
    #if there are no positions opened, we are looking to enter into a position
    if(buy_trade == False and sell_trade == False):
        #sell entry strategy being candlestick that opens above the upper band and closes back into the bollinger range when macd is below 0 we are looking to sell
        if closing_price > upper_band and cmacd < 0:
            #define stop loss 5 pips above the selling price
            sell["order"]["stopLossOnFill"]["price"]= str(round(closing_price + 0.05,3))
            #define take profit 70 pips below selling price
            sell["order"]["takeProfitOnFill"]["price"]= str(round(closing_price - 0.7))
            #API request to sell order
            sell_entry = requests.post(orderURL, headers=headers, json=sell)

            if(sell_entry.status_code == 201):
                #sell trade successfully placed
                print("Sell trade successfully placed")
            else:
                #error handling for sell trade unsuccessful
                file.write("Sell_entry ", str(sell_entry.status_code))
                file.write(str(sell_entry.content))

        #buy entry strategy being candlestick that opens below the lower band and closes back into the bollinger range when macd is above 0 we are looking to buy
        elif closing_price > lower_band and cmacd > 0:
            #define stop loss 5 pips below the buying price, note USD JPY pip is on 2 decimal place instead of 4
            buy["order"]["stopLossOnFill"]["price"]= str(round(closing_price - 0.05,3))
            #define take profit 70 pips above the buying price, note USD JPY pip is on 2 decimal place instead of 4
            buy["order"]["takeProfitOnFill"]["price"]= str(round(closing_price + 0.7,3))
            #API request to buy order
            buy_entry = requests.post(orderURL, headers=headers, json=buy)
            if(buy_entry.status_code == 201):
                #buy trade successfully place
                print("Buy trade successfully placed")
            else:
                #error handling for buy trade unsuccessful
                file.write("buy_entry ", str(buy_entry.status_code))
                file.write(str(buy_entry.content))
    #When there is a position opened either buy or sell we are looking to exit            
    else:
        #exit strategy for sell orders being macd crossing above 0 signifying a potential change in trend from bearish to bullish
        if (pmacd < 0 and cmacd > 0) and sell_trade == True:
            #API request to exit sell order
            sell_exit = requests.post(orderURL, headers=headers, json=sellExit)
            if(sell_exit.status_code == 201):
                #sell trade successfully exited
                print("Sell trade successfully exited")
            else:
                #error handling for sell trade exit
                file.write("sell_exit ", str(sell_exit.status_code))
                file.write(str(sell_exit.content))
        #exit strategy for sell orders being macd crossing below 0 signifying a potential change in trend from bullish to bearish
        elif (pmacd > 0 and cmacd < 0) and buy_trade == True:
            #API request to exit buy order
            buy_exit = requests.post(orderURL, headers=headers, json=buyExit)
            if(buy_exit.status_code == 201):
                #buy trade successfully exited
                print("Buy trade successfully exited")
            else:
                #error handling for buy trade exit
                file.write("buy_exit ", str(buy_exit.status_code))
                file.write(str(buy_exit.content))

    #set past macd to current macd so that in the next iteration after current macd is recalculated it can be compared to past macd 1 iteration before it
    pmacd = cmacd
    #buffer to ensure our algorithm is still running
    print(closing_price)

    #API request takes up to 2 seconds to execute as such we let the algorithm sleep for only 58 seconds to ensure each iteration begins with a new minute
    time.sleep(58)

