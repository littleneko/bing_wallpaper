#!/usr/bin/python3
# -*- coding: utf8 -*-

import logging
import os
import time
import json
import re
import sqlite3
import requests
import argparse
from requests import Timeout, RequestException

from log import init_logging
from notify import notify
from config import *

ZONE_CN = "CN"
ZONE_EN = "EN"

BING_BASE_URL = "https://www.bing.com"
BING_ARCHIVE_RUL = BING_BASE_URL + "/HPImageArchive.aspx"
FILE_NAME_PATTERN = re.compile(r"^/th\?id=(.*)&rf=.*", re.I)


def get_img_info(idx: int, num: int, en: int) -> dict:
    """

    :param idx:
    :param num: number of images to get, max is 8
    :param en: EN or ZH
    :return:
    {
        "images": [
            {
                "startdate": "20200229",
                "fullstartdate": "202002290800",
                "enddate": "20200301",
                "url": "/th?id=OHR.WallaceFF_EN-CN6550155171_UHD.jpg&rf=LaDigue_UHD.jpg&pid=hp&w=3840&h=2160&rs=1&c=4",
                "urlbase": "/th?id=OHR.WallaceFF_EN-CN6550155171",
                "copyright": "A Wallace's flying frog glides to the forest floor (© Stephen Dalton/Minden Pictures)",
                "copyrightlink": "/search?q=wallace%27s+flying+frog&form=hpcapt&filters=HpDate%3a%2220200229_0800%22",
                "title": "It's leap day!",
                "caption": "It's leap day!",
                "copyrightonly": "© Stephen Dalton/Minden Pictures",
                "desc": "For leap day (the extra day added to February every four years), we're looking at a Wallace's flying frog. Also known as parachute frogs, these critters live in the tropical jungles of Malaysia and Borneo. They spend most of their time in trees, gliding down to the ground to mate and lay eggs. They 'fly' by leaping and using their webbed fingers and toes to glide as far as 50 feet.",
                "date": "Feb 29, 2020",
                "bsTitle": "It's leap day!",
                "quiz": "/search?q=Bing+homepage+quiz&filters=WQOskey:%22HPQuiz_20200229_WallaceFF%22&FORM=HPQUIZ",
                "wp": true,
                "hsh": "f12d92fa7c1da6fa876d4e9fb67a5104",
                "drk": 1,
                "top": 1,
                "bot": 1,
                "hs": [],
                "og": {
                    "img": "https://www.bing.com/th?id=OHR.WallaceFF_EN-CN6550155171_tmb.jpg",
                    "title": "It's leap day!",
                    "desc": "For leap day (the extra day added to February every four years), we're looking at a Wallace's flying frog. Also known as parachute frogs…",
                    "hash": "rIV/nHYEvgH2ITMK5WgAA99XRLLTyTHeGJiIMDKsyI0="
                }
            }
        ],
        "tooltips": {
            "loading": "Loading...",
            "previous": "Previous image",
            "next": "Next image",
            "walle": "This image is not available to download as wallpaper.",
            "walls": "Download this image. Use of this image is restricted to wallpaper only."
        },
        "quiz": {
            "question": "Who first introduced the concept of a leap year?",
            "id": "HPQuiz_20200229_WallaceFF",
            "url": "/search?q=Bing+homepage+quiz&filters=WQOskey%3A%22HPQuiz_20200229_WallaceFF%22&FORM=HPQUIZ",
            "options": [
                {
                    "text": "Julius Caesar",
                    "url": "/search?q=julius+caesar&filters=IsConversation%3A%22True%22+btrequestsource%3A%22homepage%22+WQOskey%3A%22HPQuiz_20200229_WallaceFF%22+WQId%3A%221%22+WQQI%3A%220%22+WQCI%3A%220%22+ShowTimesTaskPaneTrigger%3A%22false%22+WQSCORE%3A%221%22&FORM=HPQUIZ"
                },
                {
                    "text": "Lanny Poffo",
                    "url": "/search?q=julius+caesar&filters=IsConversation%3A%22True%22+btrequestsource%3A%22homepage%22+WQOskey%3A%22HPQuiz_20200229_WallaceFF%22+WQId%3A%221%22+WQQI%3A%220%22+WQCI%3A%221%22+ShowTimesTaskPaneTrigger%3A%22false%22+WQSCORE%3A%220%22&FORM=HPQUIZ"
                },
                {
                    "text": "Pope Gregory XIII",
                    "url": "/search?q=julius+caesar&filters=IsConversation%3A%22True%22+btrequestsource%3A%22homepage%22+WQOskey%3A%22HPQuiz_20200229_WallaceFF%22+WQId%3A%221%22+WQQI%3A%220%22+WQCI%3A%222%22+ShowTimesTaskPaneTrigger%3A%22false%22+WQSCORE%3A%220%22&FORM=HPQUIZ"
                }
            ]
        }
    }
    """
    success = False
    retry_times = 3
    while not success and retry_times > 0:
        try:
            response = requests.get(BING_ARCHIVE_RUL, params={
                "format": "js",
                "idx": idx,
                "n": num,
                "nc": int(time.time() / 1000),
                "pid": "hp",
                "ensearch": en,
                "quiz": 1,
                "og": 1,
                "uhd": 1,
                "uhdwidth": 3840,
                "uhdheight": 2160
            }, timeout=5)
            if response.status_code != 200:
                logging.info("[Bing] failed to get image, status code = %d", response.status_code)
                retry_times -= 1
            else:
                data = response.json()
                return data
        except Timeout:
            retry_times -= 1
            logging.info("[Bing] timeout to get image, retry = %d", retry_times)
        except RequestException as e:
            logging.error("[Bing] failed to get image, error info", e)
            raise e


def run(sqlite: str):
    while True:
        conn = sqlite3.connect(sqlite)
        c = conn.cursor()
        img_info = get_img_info(0, 8, 0)
        images = img_info['images']
        for img in images:
            hsh = img['hsh']
            url = img['url']
            date = img['startdate']
            cursor = c.execute("SELECT `hsh`, `url` from `bing.bing` WHERE `hsh` = ? LIMIT 1", (hsh,))
            rows = cursor.fetchall()
            if rows is None or len(rows) == 0:
                logging.info("[Bing] success get img, date: %s, hsh: %s, url: %s", date, hsh, url)
                if not download_img(ZONE_CN, date, url):
                    logging.error("[Bing] failed to download '%s'", img)
                    notify(conf.notify_mail, "Bing Wallpaper Download ERROR", img)
                    continue
                c.execute(
                    "INSERT INTO `bing.bing` VALUES(NULL, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                    (date, url, img['copyright'], hsh, ZONE_CN, json.dumps(img, ensure_ascii=False)))
                conn.commit()
                logging.info("[Bing] success save image info to db, date: %s, hash: %s, url: %s", date, hsh, url)
                notify(conf.notify_mail, "Bing Wallpaper Download SUCCESS", json.dumps(img, ensure_ascii=False))
            else:
                logging.info("[Bing] image exist: date=%s, hsh=%s, url=%s", date, hsh, url)
        conn.close()
        logging.info("[Bing] wait for next round after %s second", conf.scan_sec)
        try:
            time.sleep(conf.scan_sec)
        except KeyboardInterrupt:
            break


def download_img(zone: str, date: str, url: str) -> bool:
    match = FILE_NAME_PATTERN.match(url)
    if not match:
        logging.error("[Download] can't get file name, url: %s", url)
        return False
    file_name = date + '_' + match.group(1)
    month = date[:-2]
    file_dir = os.path.join(conf.download_dir, zone, month)
    file_path = os.path.join(file_dir, file_name)
    logging.info("[Download] file path: %s", file_path)
    if not os.path.exists(file_dir):
        logging.info("[Download] create dir: %s", file_dir)
        os.mkdir(file_dir)

    try:
        r = requests.get(BING_BASE_URL + url, timeout=10)
        if r.status_code != 200:
            logging.error("[Download] failed to download, status_code: %d, resp: %s" % (r.status_code, r.text))
            return False
        with open(file_path, "w+b") as code:
            code.write(r.content)
        return True
    except RequestException as e:
        logging.error("[Download] failed to download", e)
        return False
    except Exception as e:
        logging.error("[Download] failed to download", e)
        return False


def init_db(file: str):
    conn = sqlite3.connect(file)
    create_table = """
    CREATE TABLE IF NOT EXISTS `bing.bing` (
        `id` INTEGER PRIMARY KEY,
        `date` varchar(16) NOT NULL DEFAULT '',
        `url` varchar(255) NOT NULL DEFAULT '',
        `copyright` text NOT NULL DEFAULT '',
        `hsh` varchar(64) NOT NULL DEFAULT '' UNIQUE,
        `zone` varchar(8) NOT NULL DEFAULT 'cn',
        `detail` text DEFAULT '',
        `_create_time` datetime DEFAULT CURRENT_TIMESTAMP,
        `_update_time` datetime DEFAULT CURRENT_TIMESTAMP
    )"""
    c = conn.cursor()
    c.execute(create_table)
    conn.commit()
    conn.close()


def clean_db(file: str):
    if not os.path.exists(file):
        return
    conn = sqlite3.connect(file)
    c = conn.cursor()
    c.execute("DELETE FROM `bing.bing`")
    conn.commit()
    conn.close()


parser = argparse.ArgumentParser(description='bing-dl')
parser.add_argument('--config', '-c', default="config/bing.ini", help='config file name')
parser.add_argument('--cleandb', action='store_true')

if __name__ == '__main__':
    args = parser.parse_args()
    conf.read_conf(args.config)

    init_logging(conf.file_log, conf.log_dir)

    if not os.path.exists(conf.database_dir):
        os.makedirs(conf.database_dir)
    db_file = os.path.join(conf.database_dir, "bing.db")

    if args.cleandb:
        clean_db(db_file)
    file_paths = [os.path.join(conf.download_dir, ZONE_CN), os.path.join(conf.download_dir, ZONE_EN)]
    for path in file_paths:
        if not os.path.exists(path):
            os.makedirs(path)
    init_db(db_file)
    run(db_file)