# -*- coding: utf-8 -*-
"""PythonAnywhere WSGI 配置（把 USERNAME 换成你的用户名）"""
import os
import sys

PROJECT = "/home/USERNAME/campus-wall"
if PROJECT not in sys.path:
    sys.path.insert(0, PROJECT)

# 固定 session 密钥（已为你随机生成，可自行更换）
os.environ.setdefault("FLEA_SECRET", "Q86-Qx1k1m7fC2hmuWLFJpEUmzRcbv3YNtCzfknaZJQ")
os.environ.setdefault("FLEA_DB", os.path.join(PROJECT, "instance", "campus_flea.db"))

from app import app as application, init_db

# 首次启动时建表（不写入演示数据）
init_db(seed=False)
