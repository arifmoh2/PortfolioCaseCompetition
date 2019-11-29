"""
This is a template algorithm on Quantopian for you to adapt and fill in.
"""
import quantopian.algorithm as algo
from quantopian.pipeline.data.morningstar import Fundamentals
from quantopian.pipeline import Pipeline, CustomFactor
from quantopian.pipeline.data.builtin import USEquityPricing
from quantopian.pipeline.filters import QTradableStocksUS
from quantopian.pipeline.factors import SimpleMovingAverage
import pandas as pd
import numpy as np
#from quantopian.pipeline.data.quandl import yahoo_index_vix
from quantopian.pipeline.data.quandl import yahoo_index_vix, cboe_vix
from quantopian.pipeline.data.sentdex import sentiment



def initialize(context):
    """
    Called once at the start of the algorithm.
    """
    # Rebalance every day, 1 hour after market open.
    algo.schedule_function(
        rebalance,
        algo.date_rules.month_start(),
        algo.time_rules.market_open(hours=5),
    )

    # Record tracking variables at the end of each day.
    algo.schedule_function(
        record_vars,
        algo.date_rules.month_start(),
        algo.time_rules.market_close(),
    )

    # Create our dynamic stock selector.
    algo.attach_pipeline(make_pipeline(), 'pipeline')

    #set_max_order_count(5)
    set_long_only()

#compares symbol with the SPY
#### this needs to be updated to compare returns, rather than just ratio
####
class Ratio(CustomFactor):
    window_safe = True
    def compute(self, today, assets, out, close):
        market_idx = assets.get_loc(8554)
        idx_close = close[-1,market_idx]
        ratio = close / idx_close
        out[:] = ratio

#adds the VIX for volitility
class VIXFactor(CustomFactor):
    def compute(self, today, assets, out, vix):
        out[:] = vix

# Pipeline definition
def make_pipeline():

    pe = Fundamentals.forward_pe_ratio.latest
    pe_demean = pe.demean(mask= pe < 100)
    pe_factor = -pe_demean.abs()
    pe_quantiles = pe_factor.quantiles(10)

    sentiment_factor = sentiment.sentiment_signal.latest
    ratio = Ratio(inputs=[USEquityPricing.close], window_length=1)

    base_universe = (QTradableStocksUS()
                     & sentiment_factor.notnull()
                     & pe_factor.notnull())

    #symbol vs index
    smaSymVIndexF = SimpleMovingAverage(
        inputs=[ratio],
        window_length=10
    )

    smaSymVIndexS = SimpleMovingAverage(
        inputs=[ratio],
        window_length=100
    )

    #adds VIX
    vix_close = VIXFactor(inputs=[cboe_vix.vix_close], window_length=1)

    close_price = USEquityPricing.close.latest

    smaF = SimpleMovingAverage(
        inputs=[USEquityPricing.close],
        window_length=10,
    )
    smaS = SimpleMovingAverage(
        inputs=[USEquityPricing.close],
        window_length=200,
    )

    smaC = SimpleMovingAverage(
        inputs=[USEquityPricing.close],
        window_length=3,
    )

    #go long signal
    buy = ((smaF > smaS)
           & (close_price > 1)
           & (vix_close < 25)
          ) or ((smaC > smaF)
           & (close_price > 1)
           & (vix_close < 25)
          ) #or (pe_quantiles.eq(9)) or (pe_quantiles.eq(8))

    #sell any longs
    sell = (smaF < smaS*0.9) or (sentiment_factor <= -2) #or (pe_quantiles.eq(0))

    return Pipeline(
        columns={
            'close_price': close_price,
            'sma10':smaF,
            'sma130':smaS,
            'smaSymVIndexF':smaSymVIndexF,
            'smaSymVIndexS':smaSymVIndexS,
            'vix_close':vix_close,
            'buy': buy,
            'sell':sell,
        },
        screen=(base_universe),
    )



def before_trading_start(context, data):
    """
    Called every day before market open.
    """
    context.output = algo.pipeline_output('pipeline')

    # These are the securities that we are interested in trading each day.
    context.security_list = context.output.index
    #print len(context.security_list)


def rebalance(context, data):
    """
    Execute orders according to our schedule_function() timing.
    """

    #not sure if this is best way to get longs, copied someones code
    open_rules = 'buy == True'
    open_these = context.output.query(open_rules).index.tolist()
    current_positions = context.portfolio.positions

    #naive way of tracking open positions, not sure if better way
    positions_now = len(current_positions)

    for stock in open_these:
        #i use a naive way to constrain to under 11 positions
        if stock not in current_positions and data.can_trade(stock) and (positions_now < 11):
            order_percent(stock, 0.1)
            positions_now = positions_now +1
            log.info("Buying %s" % (stock.symbol))

    #again this was just copied from someone else
    close_rules = 'sell == True'
    close_these = context.output.query(close_rules).index.tolist()

    for stock in close_these:
        if stock in current_positions and data.can_trade(stock):
            order_target(stock, 0)
            log.info("Selling %s" % (stock.symbol))


    pass


def record_vars(context, data):
    """
    Plot variables at the end of each day.
    """
    pass
