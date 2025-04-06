import yfinance as yf
import pandas as pd
import mplfinance as mpf
from datetime import datetime
import os
import requests
from bs4 import BeautifulSoup
import time

class SymbolScraper:
    def __init__(self, retries=3, delay=2):
        self.retries = retries
        self.delay = delay

    def scrape(self, url, max_items=10):
        symbols = []
        attempt = 0
        while attempt < self.retries:
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                rows = soup.find_all('tr', class_='simpTblRow')
                for row in rows[:max_items]:
                    try:
                        symbol = row.find('td').text.strip()
                        if symbol:
                            symbols.append(symbol)
                    except AttributeError:
                        continue
                if symbols:
                    return symbols
            except requests.RequestException as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                time.sleep(self.delay)
            attempt += 1
        return symbols

class PatternDetector:
    @staticmethod
    def detect(df):
        patterns = []
        for i in range(len(df)):
            row = df.iloc[i]
            o, h, l, c = row['Open'], row['High'], row['Low'], row['Close']
            body = abs(c - o)
            range_ = h - l

            if body < 0.03 and range_ > 0.1:
                patterns.append((df.index[i], 'Doji'))
            elif (c > o) and (o - l) > 2 * body and (h - c) < body:
                patterns.append((df.index[i], 'Hammer'))
            if i > 0:
                prev = df.iloc[i - 1]
                if (prev['Close'] < prev['Open']) and (c > o) and (c > prev['Open']) and (o < prev['Close']):
                    patterns.append((df.index[i], 'Engulfing'))
        return patterns

class ChartGenerator:
    def __init__(self, charts_dir='./charts', patterns_dir='./patterns'):
        os.makedirs(charts_dir, exist_ok=True)
        os.makedirs(patterns_dir, exist_ok=True)
        self.charts_dir = charts_dir
        self.patterns_dir = patterns_dir

    def run(self):
        stock_url = 'https://finance.yahoo.com/gainers'
        mf_url = 'https://finance.yahoo.com/mutualfunds'

        print("Choose a category:")
        print("1. Stock")
        print("2. Mutual Fund")
        category = input("Enter 1 or 2: ").strip()

        scraper = SymbolScraper()

        if category == '1':
            count = input("\nHow many top stocks do you want to view? ").strip()
            try:
                count = int(count)
                stocks = scraper.scrape(stock_url, max_items=count)
                if not stocks:
                    raise ValueError("Fallback to default")
            except Exception as e:
                print(f"Failed to fetch live stocks. Using default list. ({e})")
                stocks = ['AAPL', 'MSFT', 'GOOG', 'AMZN', 'TSLA']
            print("\nTop Stocks:")
            for i, stock in enumerate(stocks, 1):
                print(f"{i}. {stock}")
            choice = input("Enter the number of the stock you want to chart: ").strip()
            ticker_list = stocks
            tag = 'Stock'
        elif category == '2':
            try:
                mutual_funds = scraper.scrape(mf_url, max_items=10)
                if not mutual_funds:
                    raise ValueError("Fallback to default")
            except Exception as e:
                print(f"Failed to fetch live mutual funds. Using default list. ({e})")
                mutual_funds = ['VFIAX', 'SWPPX', 'FXAIX', 'VTSAX', 'SPY']
            print("\nTop Mutual Funds:")
            for i, mf in enumerate(mutual_funds, 1):
                print(f"{i}. {mf}")
            choice = input("Enter the number of the mutual fund you want to chart: ").strip()
            ticker_list = mutual_funds
            tag = 'MF'
        else:
            print("Invalid selection. Please enter 1 or 2.")
            return

        try:
            ticker = ticker_list[int(choice) - 1]
        except (IndexError, ValueError):
            print("Invalid option selected.")
            return

        print(f"\nFetching data for: {ticker}...")
        interval = "1m" if category == '1' else "1d"
        data = yf.download(ticker, period="1d", interval=interval)

        if data.empty:
            print("No data available for this ticker and interval.")
            return

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        data.index = data.index.tz_localize(None)
        last_dt = data.index[-1]
        formatted_dt = last_dt.strftime("%b %d, %Y - %H:%M")
        timestamp = last_dt.strftime("%Y%m%d_%H%M")
        chart_title = f"{ticker} - Intraday Price Movement\nAs of {formatted_dt}"
        filename = f"{self.charts_dir}/{ticker}_{tag}_{timestamp}_intraday_chart.png"

        # Detect patterns
        patterns = PatternDetector.detect(data)
        apdict = []
        for dt, label in patterns:
            price = data.loc[dt]['High'] + 0.5
            apdict.append(mpf.make_addplot(
                [price if d == dt else float('nan') for d in data.index],
                scatter=True, markersize=80, marker='^', color='red'
            ))

        mpf.plot(data,
                 type='candle',
                 style='charles',
                 title=chart_title,
                 volume=True,
                 mav=(5, 10),
                 addplot=apdict,
                 tight_layout=True,
                 savefig=filename)

        print(f"Chart saved as: {filename}")

        if patterns:
            csv_filename = f"{self.patterns_dir}/{ticker}_{tag}_{timestamp}_patterns.csv"
            df_patterns = pd.DataFrame(patterns, columns=["Time", "Pattern"])
            df_patterns.to_csv(csv_filename, index=False)
            print(f"Patterns saved to CSV: {csv_filename}")
        else:
            print("No reversal patterns detected.")

if __name__ == '__main__':
    ChartGenerator().run()