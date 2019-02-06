import pandas as pd
import numpy as np

from bokeh.plotting import figure, show, output_file #, output_notebook
#from bokeh.layouts import column
from bokeh.models import ColumnDataSource, BoxAnnotation, Band
#from bokeh.models import LinearAxis, Range1d, DatetimeTickFormatter
from bokeh.embed import components
#from bokeh.resources import CDN
from bokeh.palettes import Dark2_5 as palette
import itertools


def calc_elem_width(tmin, tmax, tlen):
    """ returns a width in --pixel-- timesomething ?? for candlesticks and bars, according to the time scale 'offset' """
    return (tmax - tmin).total_seconds() * 1000 * 0.8 / tlen

def draw_maingraph(df, offset, title):
    """ Draws Candlesticks and Bollinger's Bands
      returns plot_script, plot_div """
#    df = d15.iloc[-50:]
    inc = df.close > df.open
    dec = df.open > df.close
    w = calc_elem_width(df.index.min(), df.index.max(), len(df))
    # fill NaN:
    df.fillna(df.mean())
    """
    TOOLS = "pan,wheel_zoom,box_zoom,reset,save"
    TOOLTIPS = [
        ('index', "$index"),
        ('date', '@index'),
        ("open", "@open"),
        ("close", "@close"),
        ("volume", "@vol"),
        ('squared', '@squared')
    ] """


    p = figure(x_axis_type="datetime", plot_width=800, plot_height=500,
           y_range=(df['BBLow'].min()*0.99, df['BBUp'].max()*1.01),
           title = title) #, tools=TOOLS, tooltips=TOOLTIPS )

    p.segment(df.index, df.high, df.index, df.low, color="black")
    p.vbar(df.index[inc], w, df.open[inc], df.close[inc], fill_color="green", line_color="black")
    p.vbar(df.index[dec], w, df.open[dec], df.close[dec], fill_color="red", line_color="black")
    source = ColumnDataSource(df)
    p.line(df.index, df['MA'], line_dash='dotted', legend="MA")

    source = ColumnDataSource(df)
    band = Band(base='index', lower='BBLow', upper='BBUp', source=source, level='underlay',
        line_width=1, line_color='mediumslateblue', fill_color='mediumslateblue', fill_alpha=0.05)
    p.add_layout(band)
    
    return components(p)

def draw_rsi(rsi, title):
    """ Draws RSI
      returns plot_script, plot_div """
    colors = itertools.cycle(palette)
    prsi = figure(x_axis_type="datetime", plot_width=800, plot_height=150, 
              y_range=(0,100), title = title  )
    for l in list(rsi):
        prsi.line(rsi.index, rsi[l], legend=l, line_color=next(colors))
    prsi.line(rsi.index, [50]*rsi.shape[0], line_color='grey', line_dash='dotted')
    prsi.add_layout(BoxAnnotation(top=20, fill_alpha=0.1, fill_color='red', line_color='red'))
    prsi.add_layout(BoxAnnotation(bottom=80, fill_alpha=0.1, fill_color='red', line_color='red'))
    prsi.legend.location = "top_left"

    return components(prsi)

def draw_vol(df, offset, title):
    """ Draws volume as barchart 
      returns plot_script, plot_div """
    w = calc_elem_width(df.index.min(), df.index.max(), len(df))
    p = figure(x_axis_type="datetime", plot_width=800, plot_height=150, title = title  )
              #y_range=(0,100)
    source = ColumnDataSource(df)
    p.vbar('index', top='vol', width=w, source=source,  bottom=0,  color="firebrick")

    return components(p)
