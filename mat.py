#!/usr/bin/python3
import requests
import importlib.machinery
import datetime
from datetime import timedelta
import argparse
import os
import re
import sys
from mats.print_stream import PrintStream
import traceback
from collections import namedtuple

try:
    from bs4 import BeautifulSoup
except:
    BeautifulSoup = None

try:
    import fitz
except:
    fitz = None

try:
    import json
except:
    json = None

MAT_DIR = '.mat'
INFERRED_TITLE_MAX_LENGTH = 50

def truncate(max_length, str):
    if len(str) > max_length:
        return str[:max_length] + '...'
    else:
        return str

class Food:
    def __init__(self, title, description):
        self.title = truncate(100, title.strip().replace('\n', ' ')) if title else title
        self.description = description.strip() if description else description

    def pretty(self):
        return f"{self.title}\n  {self.description}"

class Restaurant:
    def __init__(self, name, dishes=[], error=None, errorTrace=None):
        self.name = name
        self.dishes = dishes
        self.error = error
        self.errorTrace = errorTrace

class FoodAPI:
    soup = BeautifulSoup
    requests = requests
    pdf = fitz
    json = json
    food = Food

    def week_of(self, date):
        return date.isocalendar()[1]

    def week_is_odd(self, date):
        return not self.week_is_even(date)

    def week_is_even(self, date):
        return self.week_of(date) % 2 == 0

    def is_today(self, date):
        return date == datetime.date.today()

    def is_current_week(self, date):
        return self.week_of(date) == self.week_of(datetime.date.today())

    def is_weekday(self, date):
        return date.isoweekday() <= 5

foodAPI = FoodAPI()

def plugin_directory():
    home_directory = os.getenv('HOME')
    dot_mat = os.path.join(home_directory, MAT_DIR)
    if os.path.isdir(dot_mat):
        return dot_mat
    else:
        return "plugins"

def color_codes(use_color):
    Color = namedtuple('Color', 'heading subheading body reset error')
    if use_color:
        return Color("\033[1m\033[95m", "\033[4m\033[94m", "", "\033[0m", "\033[91m")
    else:
        return Color("", "", "", "", "")

class Mat:
    def __init__(self, settings):
        self.settings = settings
        self._plugins = None
        self.stream = PrintStream(settings.color_codes.reset)

    def __print_date_heading(self, date):
        if not self.settings.print_markdown:
            c = self.settings.color_codes
            day = date.strftime("%A")
            datestr = date.strftime("%d-%m-%Y")
            print(f"{c.subheading}Menu for {c.heading}{day}{c.reset} ({datestr})\n")

    def _load_plugins(self):
        directory = self.settings.plugin_directory
        for file in sorted(os.listdir(directory)):
            if file[-3:] == ".py":
                module = file[0:-3]
                path = os.path.join(directory, file)
                loader = importlib.machinery.SourceFileLoader(module, path)
                yield loader.load_module(module)

    def infer_title(self, description):
        if len(description) > INFERRED_TITLE_MAX_LENGTH:
            truncated_description = description[:INFERRED_TITLE_MAX_LENGTH-3].strip()
            if description[INFERRED_TITLE_MAX_LENGTH-2] == " ":
                return (truncated_description + "...")
            return re.sub(r"[ .,-:;!]+[^ ]+$", "", truncated_description) + "..."
        else:
            return description

    def make_resturant(self, plugin, date):
        name = plugin.name()
        try:
            return Restaurant(name, plugin.food(foodAPI, date))
        except Exception as e:
            return Restaurant(name, error=e, errorTrace=traceback.format_exc())

    def describe_dish(self, dish):
        title = dish.title if dish.title else self.infer_title(dish.description)

        c = self.settings.color_codes
        prefix = "* " if self.settings.print_markdown else ""
        self.stream.line(f"{prefix}{title}", c.subheading)

        if self.settings.verbose and dish.description:
            self.stream.with_indent(lambda s: s.line(f"{prefix}{dish.description}", c.body))

    def describe_error(self, restaurant):
        self.stream.with_indent(lambda s: 
            s.line(f"Plugin Error ({type(restaurant.error).__name__}):"
            ).with_indent(lambda s1:
                s1.line(str(restaurant.error))
            ).conditional(self.settings.with_stacktrace, lambda s1:
                s1.error("\n" + restaurant.errorTrace)
            )
        )

    def describe_menu(self, restaurant, date):
        c = self.settings.color_codes
        prefix = "## " if self.settings.print_markdown else ""
        self.stream.line(f"{prefix}{restaurant.name}", c.heading)

        if(restaurant.error == None):
            self.stream.with_indent(lambda s: 
                list(map(self.describe_dish, restaurant.dishes)))
        else: 
            self.describe_error(restaurant)
        self.stream.newline()

    def get_dishes(self, date):
        if not self._plugins:
            self._plugins = self._load_plugins()
        restaurants = map(lambda p: self.make_resturant(p, date), self._plugins)
        filtered_restaurants = filter(
            lambda r: r.dishes or (not self.settings.quiet and r.error != None),
            restaurants
        )
        return sorted(filtered_restaurants, key = lambda r: r.name)

    def print_menu(self, date):
        if self.settings.tomorrow:
            date += timedelta(days=1)

        self.__print_date_heading(date)
        for r in self.get_dishes(date):
            self.describe_menu(r, date)
        self.stream.print()

def parse_args():
    parser = argparse.ArgumentParser(description="Show today's food options.")
    parser.add_argument(
        '--tomorrow', '-t',
        dest = 'tomorrow',
        action = 'store_const',
        const = True,
        default = False,
        help = 'show menu for tomorrow instead of today'
    )
    parser.add_argument(
        '--verbose', '-v',
        dest = 'verbose',
        action = 'store_const',
        const = True,
        default = False,
        help = 'show detailed information about food alternatives'
    )
    parser.add_argument(
        '--quiet', '-q',
        dest = 'quiet',
        action = 'store_const',
        const = True,
        default = False,
        help = 'Squelch errors'
    )
    parser.add_argument(
        '--color', '-c',
        dest = 'color_codes',
        action = 'store_const',
        const = color_codes(True),
        default = color_codes(False),
        help='colorize restaurant names, dishes, and descriptions'
    )
    parser.add_argument(
        '--with-stacktrace', '-s',
        dest = 'with_stacktrace',
        action = 'store_const',
        const = True,
        default = False,
        help = 'show stacktrace on errors'
    )
    parser.add_argument(
        '--plugin-directory', '-p',
        dest = 'plugin_directory',
        action = 'store',
        default = plugin_directory(),
        help='load restaurant plugins from this directory'
    )
    parser.add_argument(
        '--markdown', '-m',
        dest = 'print_markdown',
        action = 'store_const',
        const = True,
        default = False,
        help='print menus as markdown'
    )
    return parser.parse_args()

mat = Mat(parse_args())
mat.print_menu(datetime.date.today())
