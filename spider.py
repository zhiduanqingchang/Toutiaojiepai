#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2018/4/18 0:15
# @Author  : ChenHuan
# @Site    : 
# @File    : spider.py
# @Desc    :
# @Software: PyCharm

# json 模块提供了一种很简单的方式来编码和解码JSON数据
import json
# Python的os模块封装了常见的文件和目录操作
import os
# re 模块使Python 语言拥有全部的正则表达式功能
# 正则表达式（或 RE）是一种小型的、高度专业化的编程语言，（在Python中）它内嵌在Python中，并通过 re 模块实现
import re
# pymongo是Python中用来操作MongoDB的一个库
import pymongo
# Python的hashlib提供了常见的摘要算法，如MD5，SHA1等等。什么是摘要算法呢？摘要算法又称哈希算法、散列算法。它通过一个函数，把任意长度的数据转换为一个长度固定的数据串（通常用16进制的字符串表示）。
# 引入MD5来判断文件是否相同,
# MD5的全称是Message-Digest Algorithm 5（信息-摘要算法）。128位长度。目前MD5是一种不可逆算法。具有很高的安全性。它对应任何字符串都可以加密成一段唯一的固定长度的代码。
from hashlib import md5
# Beautiful Soup 是一个可以从HTML或XML文件中提取数据的Python库
from bs4 import BeautifulSoup
# 引入urllib库提供的URL编码方法
# 当url地址含有中文，或者参数有中文的时候，这个算是很正常了，但是把这样的url作为参数传递的时候（最常见的callback），需要把一些中文甚至'/'做一下编码转换。
# urllib库里面有个urlencode函数，可以把key-value这样的键值对转换成我们想要的格式，返回的是a=1&b=2这样的字符串
from urllib.parse import urlencode
# 引入进程池
# Python提供了非常好用的多进程包multiprocessing，你只需要定义一个函数，Python会替你完成其他所有事情。借助这个包，可以轻松完成从单进程到并发执行的转换。
from multiprocessing import Pool
# 引入异常处理
from requests.exceptions import RequestException
# 引入配置信息
from config import *
# 引入HTTP库
import requests
# 对于无效的JSON格式数据,利用json.loads()将JSON编码的字符串转换为一个Python数据结构对象时将会报错,则引入JSONDecodeError进行处理
from json.decoder import JSONDecodeError

# 声明一个MongoDB对象,连接MongoClient
client = pymongo.MongoClient(MONGO_URL, connect=False)
# 获取数据库（database）
db = client[MONGO_DB]

def get_page_index(offset, keyword):
    """获取索引页内容"""
    # 为请求添加查询字符串参数,Query String Parameters(Ajax请求)
    data = {
        'offset': offset,
        'format': 'json',
        'keyword': keyword,
        'autoload': 'true',
        'count': 20,
        'cur_tab': 3,
        'from':'gallery'
    }
    # 构造完整的URL,利用urlencode()将data进行编码,将字典类型转换为URL的请求参数,是urllib库提供的编码方法
    url = 'https://www.toutiao.com/search_content/?' + urlencode(data)
    # 进行URL请求
    try:
        response = requests.get(url)
        # 判断返回的状态码
        if response.status_code == 200:
            return response.text
        return None
    except RequestException:
        print('请求索引页出错')
        return None

def parse_page_index(html):
    """对返回结果进行解析"""
    try:
        # 返回结果为JSON格式的数据,利用json.loads()将JSON编码的字符串转换为一个Python数据结构对象
        data = json.loads(html)
        # 判断返回的JSON数据中是否含有data信息,data.keys()返回JSON数据的所有键名
        if data and 'data' in data.keys():
            for item in data.get('data'):
                yield item.get('article_url')
                # if 'display' in item.keys():
                #     if 'search_url' in item.get('display'):
                #         search_url = item['display'].get('search_url')
                #         yield search_url
    except JSONDecodeError:
        pass

def get_page_detail(url):
    """获取详情页内容"""
    try:
        # 为了完全模拟浏览器的工作,我们需要设置一些 Headers 的属性,heardes参数用来为请求添加HTTP 头部
        # User-Agent : 有些服务器或 Proxy 会通过该值来判断是否是浏览器发出的请求
        heardes = {
            'user-agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.186 Safari/537.36'
        }
        response = requests.get(url, headers = heardes)
        # 判断返回的状态码
        if response.status_code == 200:
            return response.text
        return None
    except RequestException:
        print('请求详情页出错',url)
        return None

def parse_page_detail(html, url):
    """解析详情页内容"""
    # 解析title,BeautifulSoup 是一个可以从HTML或XML文件中提取数据的Python库,使用lxml作为解析器
    soup = BeautifulSoup(html, 'lxml')
    # BeautifulSoup支持大部分的CSS选择器,在 Tag 或 BeautifulSoup 对象的 .select() 方法中传入字符串参数,即可使用CSS选择器的语法找到tag
    title = soup.select('title')[0].get_text()
    images_pattern = re.compile('gallery:.*?"(.*?)"\)\,', re.S)
    result = re.search(images_pattern, html)
    if result:
        # 遇到报错:json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)
        # 是因为JSON格式数据中含有反斜杠(\\),则将其替换掉:result.group(1).replace('\\','')
        data = json.loads(result.group(1).replace('\\',''))
        if data and 'sub_images' in data.keys():
            sub_images = data.get('sub_images')
            images = [item.get('url') for item in sub_images]
            for image in images : download_image(image)
            return {
                'title': title,
                'url': url,
                'images': images
            }

def save_to_mangon(result):
    """将数据存储到MongoDB"""
    if db[MONGO_TABLE].insert(result):
        print('存储到MongoDB成功', result)
        return True
    return False

def download_image(url):
    """下载图片"""
    try:
        response = requests.get(url)
        if response.status_code == 200:
            save_image(response.content)
        return None
    except RequestException:
        print('请求图片出错', url)
        return None

def save_image(content):
    """保存图片"""
    # os.getcwd()当前路径,md5()避免下载重复的图片,如果内容相同,则md5值是相同的
    file_path = '{0}/{1}.{2}'.format(os.getcwd()+'\image', md5(content).hexdigest(), 'jpg')
    if not os._exists(file_path):
        with open(file_path, 'wb') as f:
            f.write(content)
            f.close()

def main(offset):
    # 利用方法传递一些可变的参数
    html= get_page_index(offset, KEYWORD)
    for url in parse_page_index(html):
        html = get_page_detail(url)
        if html:
            result = parse_page_detail(html, url)
            if result: save_to_mangon(result)

if __name__ == '__main__':
    groups = [x * 20 for x in range(GROUP_START, GROUP_END + 1)]
    # Pool类可以提供指定数量的进程供用户调用，当有新的请求提交到Pool中时，如果池还没有满，就会创建一个新的进程来执行请求。如果池满，请求就会告知先等待，直到池中有进程结束，才会创建新的进程来执行这些请求。
    pool = Pool()
    # map(func, iterable[, chunksize=None]),Pool类中的map方法，与内置的map函数用法行为基本一致，它会使进程阻塞直到返回结果。
    # 注意，虽然第二个参数是一个迭代器，但在实际使用中，必须在整个队列都就绪后，程序才会运行子进程。
    pool.map(main, groups)
