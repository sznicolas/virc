""" 
RSI (rsi) and Bollingers bands (bollinger) are based on :
https://github.com/mvirag2000/Indicators

"""

import pandas as pd


def bollinger(df, window=20, devs=2):
    """Returns bands as three new columns"""
    tmp = pd.DataFrame()
    tmp['MA'] = df.rolling(window).mean()
    tmp['STD'] = df.rolling(window).std()
    tmp['BBUp'] = tmp['MA'] + (tmp['STD'] * devs)
    tmp['BBLow'] = tmp['MA'] - (tmp['STD'] * devs)
    return tmp['MA'], tmp['BBUp'], tmp['BBLow']

def rsi(df, w=14):
    """Returns RSI as new column"""
    tmp = pd.DataFrame(index=df.index, columns=['Delta', 'Gain','Loss', 'MeanG', 'MeanL', 'RS'])
    tmp['Delta'] = df - df.shift(1, axis=0)
    tmp['Gain'] = tmp['Delta'][tmp['Delta'] > 0] 
    tmp['Loss'] = -1 * tmp['Delta'][tmp['Delta'] < 0]
    tmp = tmp.fillna(0)
    tmp['MeanG'] = tmp['Gain'].ewm(span=(2*w-1)).mean()
    tmp['MeanL'] = tmp['Loss'].ewm(span=(2*w-1)).mean()
    tmp['RS'] = tmp['MeanG'] / tmp['MeanL'] 
    return 100 - 100 / (1 + tmp['RS'])
